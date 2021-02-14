"""
This module provides integration with setuptools.
"""

import os
import io
import re
import sys
import argparse
import pkg_resources

from .commands import CommandsMiddleware


class ConsoleScriptsMiddleware(CommandsMiddleware):
    """
    This middleware scans the path for "nested" console scripts and make
    them available through a "global" parent script.
    """

    def __init__(self, pkg_name: str, *, separator: str = '-', prefix: str = None) -> None:
        """
        The *pkg_name* argument is the name of the package to scan for entry points.
        The *separator* argument defines what separator to use when parsing script names,
        so that in `foo-bar`, `bar` becomes a possible command of `foo`.

        The *prefix* argument defines the prefix to ignore when parsing commands and defaults
        to the package name, with dot separators replaced by the *separator*.
        """
        super().__init__()
        self.pkg_name = pkg_name
        self.separator = separator
        self.prefix = prefix or pkg_name.replace('.', separator)

    @classmethod
    def get_command_desc(cls, entrypoint: pkg_resources.EntryPoint) -> str:
        """
        Get a command description by running it and parsing the output.
        """
        with open(os.devnull, 'a') as devnull:
            stdout, stderr, stdin, argv = sys.stdout, sys.stderr, sys.stdin, sys.argv
            sys.stdout = io.StringIO()
            sys.stderr, sys.stdin = (devnull, devnull)
            sys.argv = [entrypoint.name, '--help']
            output = sys.stdout

            try:
                func = entrypoint.load()
                func()
            except BaseException:
                pass

            sys.stdout, sys.stderr, sys.stdin, sys.argv  = stdout, stderr, stdin, argv

            output = output.getvalue()
            matches = re.match(r'^usage: .*\n\n([^\n]*)\n\n.*', output,
                               flags=re.MULTILINE | re.DOTALL)
            if matches:
                desc = re.sub(' +', ' ', matches.groups()[0].replace('\n', ' '))
                return desc

        return None

    def configure(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """
        Configure the parser.
        """
        iter_items = pkg_resources.get_entry_map(self.pkg_name)['console_scripts']

        def command_handler(entrypoint):
            """ Handler function wrapper for a specific entrypoint. """
            def handler(args):
                sys.argv = [entrypoint.name] + getattr(args, '__nargs')
                entrypoint.load()()
            return handler

        for entrypoint in iter_items.values():
            if not entrypoint.name.startswith(self.prefix) or entrypoint.name == sys.argv[0]:
                continue

            ep_name = entrypoint.name[len(self.prefix) + 1:]
            if not ep_name:
                continue

            name = ' '.join(ep_name.split(self.separator))
            desc = self.get_command_desc(entrypoint)
            command = self.add_command(name, command_handler(entrypoint), help=desc, add_help=False,
                                       prefix_chars=r'\0')
            command.add_argument('__nargs', nargs=argparse.REMAINDER)

        return super().configure(parser)
