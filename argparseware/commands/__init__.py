"""
This package provides middleware that can be used to provide subcommands to
an argument parser.
"""

import typing
import sys
import argparse
from argparseware import ArgumentParser
from argparseware import IMiddleware


class Argument():
    """
    This class is used to proxy arguments to parser commands.
    """

    def __init__(self, *args, **kwargs) -> None:
        """
        The *args* and *kwargs* arguments are the same that `add_parser_argument()`
        accepts.
        """
        self.args = args
        self.kwargs = kwargs

    def apply(self, parser: argparse.ArgumentParser) -> None:
        """
        Add the argument to the specified parser.
        """
        parser.add_argument(*self.args, **self.kwargs)


class Command():
    """
    This class is used to define commands for parsers.
    """

    TEMP_PREFIX = '__cmd_'
    """ The temporary argument prefix. """

    def __init__(self, command: str, handler: typing.Callable = None,  # pylint:disable=keyword-arg-before-vararg
                 *args: typing.List[Argument], **kwargs) -> None:
        """
        The *command* argument is the name of the command. The *handler* argument
        is a callable that is executed when the user specifies the command. The *args*
        argument is the list of `Argument` objects to add to the command. The *kwargs*
        arguments are passed to `add_parser()` and mostly mirrors `add_argument()`.
        """
        self.command = command
        self.handler = handler
        self.args = list(args)
        self.kwargs = kwargs
        self.kwargs['help'] = self.kwargs.get('help', '')

    def add_argument(self, *args, **kwargs) -> Argument:
        """
        Add an argument to the parser. The *args* and *kwargs* arguments are the same
        that `ArgumentParser.add_argument()`.
        """
        arg = Argument(*args, **kwargs)
        self.args.append(arg)
        return arg

    @classmethod
    def get_subparser_action(cls, parser: argparse.ArgumentParser, dest: str, *,
                             add: bool = False) -> argparse._SubParsersAction:
        """
        Get the subparser action from an argument parser. If *add* is specified and the
        subparser does not exist, one is created and returned.
        """
        # pylint:disable=protected-access

        action = next(iter([x for x in parser._actions
                            if isinstance(x, argparse._SubParsersAction)]), None)

        if not action and add:
            action = parser.add_subparsers(metavar='command')

        action.dest = dest
        return action

    def apply(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """
        Apply the command to a parser.
        """
        action = self.get_subparser_action(parser, self.TEMP_PREFIX, add=True)

        parts = self.command.split(' ')
        for index, command in enumerate(parts):
            try:
                subparser = action.choices[command]
            except KeyError:
                kwargs = {'help': ''} if index < self.command.count(' ') else self.kwargs
                subparser = action.add_parser(command, **kwargs)

            if index < self.command.count(' '):
                dest = '{}{}'.format(self.TEMP_PREFIX, '_'.join(parts[:index + 1]))
                action = self.get_subparser_action(subparser, dest, add=True)

        for arg in self.args:
            arg.apply(subparser)

        return subparser


class CommandsMiddleware(IMiddleware):
    """
    This middleware is used to simply add commands and subcommands to an argument parser.
    """

    def __init__(self, *args: typing.List[Command], dest: str = 'command') -> None:
        """
        The *args* argument is a list of `Command` objects to add.
        """
        self.commands = list(args)
        self.dest = dest
        self.argparser = None

    def add_command(self, *args, **kwargs) -> Command:
        """
        Register a command. The arguments are passed to the `Command` constructor and
        the resulting object is returned.
        """
        cmd = Command(*args, **kwargs)
        self.commands.append(cmd)
        return cmd

    def configure(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """
        Configure the middleware.
        """
        if self.argparser is parser:
            return parser

        self.argparser = parser
        for command in sorted(self.commands, key=lambda x: x.command):
            command.apply(parser)

        return parser

    def run(self, args: argparse.Namespace) -> None:
        """
        Run the middleware.
        """
        parts = []
        while True:
            try:
                key = '{}{}'.format(Command.TEMP_PREFIX, '_'.join(parts))
                value = getattr(args, key)
                delattr(args, key)
                if value is None:
                    break
                parts.append(value)
            except AttributeError:
                break

        name = ' '.join(parts)
        if self.dest:
            setattr(args, self.dest, name)

        for command in self.commands:
            if command.command != name:
                continue
            if command.handler:
                command.handler(args)
            return None

        if self.argparser:
            sys.argv.append('--help')
            self.argparser.run()


class CommandsArgumentParser(ArgumentParser):
    """
    This class extends the default parser class and provides an `add_command()` method.
    """

    def __init__(self, *args, **kwargs):
        """
        Accepts the same arguments as a regular `ArgumentParser`.
        """
        super().__init__(*args, **kwargs)
        self.commands = CommandsMiddleware()
        self.add_middleware(self.commands)

    def add_command(self, *args, **kwargs) -> Command:
        """
        Mirrors the functionality of `Command.add_command()` on the current parser.
        """
        return self.commands.add_command(*args, **kwargs)
