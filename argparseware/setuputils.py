"""
This module provides integration with setuptools.
"""

import typing
import os
import re
import sys
import pkg_resources
import argparse
import subprocess
from setuptools import setup as setuptools_setup

from . import IMiddleware


class ConsoleScriptsMiddleware(IMiddleware):
    """
    This middleware scans the path for "nested" console scripts and make
    them available through a "global" parent script.
    """

    def __init__(self, pkg_name: str, *,
                 separator: str = '-', prefix: str = None) -> None:
        """
        The *pkg_name* argument is the name of the package to scan for entry points.
        The *separator* argument defines what separator to use when parsing script names,
        so that in `foo-bar`, `bar` becomes a possible command of `foo`.

        The *prefix* argument defines the prefix to ignore when parsing commands and defaults
        to the package name, with dot separators replaced by the *separator*.
        """
        self.pkg_name = pkg_name
        self.separator = separator
        self.prefix = prefix or pkg_name.replace('.', '-')
        self.parsers = {}

    @classmethod
    def get_command_desc(cls, command: str) -> str:
        """
        Get a command description by running it and parsing the output.
        """
        proc = subprocess.Popen([command, '--help'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        proc.wait(1)
        proc.terminate()
        output = proc.communicate()[0].decode('utf-8')

        matches = re.match(r'^usage: .*\n\n([^\n]*)\n\n.*', output, flags=re.MULTILINE | re.DOTALL)
        if matches:
            return re.sub(' +', ' ', matches.groups()[0].replace('\n', ' '))

        return None

    @property
    def commands_map(self) -> dict:
        """
        Get a map of commands from the path specification.

        The value returned is a map with the key as the command, and the value as the
        description of the command, if applicable.
        """
        iter_items = pkg_resources.get_entry_map(self.pkg_name)['console_scripts']
        result = {}
        tree = {}

        for entrypoint in iter_items.values():
            prefix = '{}{}'.format(self.prefix, self.separator)
            if not entrypoint.name.startswith(prefix):
                continue

            names = entrypoint.name[len(prefix):].split(self.separator)
            cmd = ' '.join(names)
            ref = tree
            desc = None

            for name in names:
                if names[-1] == name:
                    ref[name] = self.get_command_desc(entrypoint.name)
                    desc = ref[name]
                    continue
                elif name not in ref:
                    ref[name] = {}
                ref = ref[name]

            result[cmd] = desc

        return (result, tree)

    def configure(self, parser: argparse.ArgumentParser) -> None:
        """
        Configure the middleware arguments.
        """
        commands, tree = self.commands_map
        subparsers = parser.add_subparsers(metavar='command', dest='entrypoint')
        self.parsers[''] = parser

        def add_parsers(data, subparser, parent=None):
            if parent:
                node = subparser.add_subparsers(
                    metavar='command',
                    dest='entrypoint_{}'.format(parent.replace(' ', '_')),
                )
            else:
                node = subparsers

            for name, items in data.items():
                parent_name = '{} {}'.format(parent, name) if parent else name
                if not isinstance(items, dict):
                    subparser = node.add_parser(name, help=items, add_help=False, prefix_chars='+')
                    subparser.add_argument('entrypoint_nargs', nargs=argparse.REMAINDER)

                    if parent:
                        subparsers.add_parser(parent_name, help=commands[parent_name])

                else:
                    subparser = self.parsers[parent_name] = node.add_parser(name)
                    add_parsers(items, subparser, parent_name)

        add_parsers(tree, parser)

        return parser

    def run(self, args: argparse.Namespace) -> None:
        """
        Run the middleware.
        """
        command = []
        entrypoint = args.entrypoint

        if not entrypoint:
            self.parsers[''].print_help()
            sys.exit(0)

        while True:
            command.append(entrypoint)

            name = 'entrypoint_{}'.format('_'.join(command))
            if not hasattr(args, name):
                break

            entrypoint = getattr(args, name)
            if not entrypoint:
                break

        name = ' '.join(command)

        if name in self.commands_map[0]:
            script = '-'.join([self.prefix] + command)
            proc = subprocess.Popen([script] + args.entrypoint_nargs)
            proc.communicate()
            sys.exit(proc.returncode)
        else:
            self.parsers[name].print_help()
            sys.exit(0)
