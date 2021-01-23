"""
This module provides integration with setuptools.
"""

import os
import re
import sys
import tempfile
import signal
import pickle
import argparse
import subprocess
import pkg_resources

from . import IMiddleware


class ConsoleScriptsMiddleware(IMiddleware):
    """
    This middleware scans the path for "nested" console scripts and make
    them available through a "global" parent script.
    """

    def __init__(self, pkg_name: str, *, wait: float = 5, cache: bool = True,
                 separator: str = '-', prefix: str = None) -> None:
        """
        The *pkg_name* argument is the name of the package to scan for entry points.
        The *separator* argument defines what separator to use when parsing script names,
        so that in `foo-bar`, `bar` becomes a possible command of `foo`.

        The *wait* argument defines the amount of time to wait for subprocesses to
        complete when gathering help. The *cache* argument defines whether or not to cache
        the results of the subcommands for faster subsequent executions.

        The *prefix* argument defines the prefix to ignore when parsing commands and defaults
        to the package name, with dot separators replaced by the *separator*.
        """
        self.pkg_name = pkg_name
        self.wait = wait
        self.cache = cache
        self.separator = separator
        self.prefix = prefix or pkg_name.replace('.', '-')
        self.parsers = {}

    @classmethod
    def get_command_desc(cls, command: str, *, wait: float = 5) -> str:
        """
        Get a command description by running it and parsing the output.
        """
        proc = subprocess.Popen([command, '--help'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        proc.wait(wait)
        proc.terminate()
        output = proc.communicate()[0].decode('utf-8')

        matches = re.match(r'^usage: .*\n\n([^\n]*)\n\n.*', output, flags=re.MULTILINE | re.DOTALL)
        if matches:
            return re.sub(' +', ' ', matches.groups()[0].replace('\n', ' '))

        return None

    @property
    def cache_file(self) -> str:
        """
        Get the cache filename.
        """
        if not self.cache:
            return None

        filename = '.argparseware-cscache-{}-{}.pickle'.format(
            self.pkg_name, self.prefix,
        )
        return os.path.join(tempfile.gettempdir(), filename)

    @property
    def commands_map(self) -> dict:
        """
        Get a map of commands from the path specification.

        The value returned is a map with the key as the command, and the value as the
        description of the command, if applicable.
        """
        try:
            with open(self.cache_file, 'rb') as fpp:
                data = pickle.load(fpp)
                return data['commands_map']
        except Exception:
            pass

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
                    ref[name] = self.get_command_desc(entrypoint.name, wait=self.wait)
                    desc = ref[name]
                    continue
                if name not in ref:
                    ref[name] = {}
                ref = ref[name]

            result[cmd] = desc

        try:
            with open(self.cache_file, 'wb') as fpp:
                pickle.dump({
                    'commands_map': (result, tree),
                }, fpp, protocol=3)
        except Exception:
            pass

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

            def forward_signal(signum, _frame):
                """ Forward a signal to the child process. """
                proc.send_signal(signum)

            for signum in set(signal.Signals) - {signal.SIGKILL, signal.SIGSTOP}:
                signal.signal(signum, forward_signal)

            try:
                proc.communicate()
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass

            sys.exit(proc.returncode)
        else:
            self.parsers[name].print_help()
            sys.exit(0)
