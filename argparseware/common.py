"""
This module contains common middleware definitions for thing such as logging.
"""

import sys
import argparse
import logging

from .core import IMiddleware


class LoggingMiddleware(IMiddleware):
    """
    Logging middleware.
    """

    def __init__(self, name: str = None, *, formatter: logging.Formatter = None,
                 handler: logging.Handler = None) -> None:
        """
        This middleware registers a few arguments that allow to automatically configure
        and control the logging output.

        The *name* argument is the name of the logger to configure. By default, the
        root logger is used.

        The *formatter* argument is an instance of `Formatter` that will be used.
        If omitted, it is automatically configured.

        The *handler* argument is an instance of a `Handler` that will be used for
        output. If omitted, it will log messages to stderr.
        """
        self.name = name
        self.formatter = formatter
        self.handler = handler

    def configure(self, parser: argparse.ArgumentParser) -> None:
        """
        Configure the middleware arguments.
        """
        parser.add_argument('--log-std', action='store_true',
                            help='the whether to enable standard logging when logging to files')
        parser.add_argument('--log-file',
                            help='the log file to use')

        group = parser.add_mutually_exclusive_group()
        group.add_argument('--log-level',
                           help='the log level to use')
        group.add_argument('-q', '--quiet', action='store_true',
                           help='suppress the output except warnings and errors')
        group.add_argument('-v', '--verbose', action='store_true',
                           help='enable additional debug output')

    def run(self, args: argparse.Namespace) -> None:
        """
        Run the middleware.
        """
        log_level = args.log_level or \
                ('debug' if args.verbose else 'warning' if args.quiet else 'info')
        formatter = self.formatter or \
                logging.Formatter('%(asctime)-25s %(levelname)-10s %(name)-20s: %(message)s')

        logger = logging.getLogger(self.name)

        if not args.log_file or args.log_std:
            handler = self.handler or logging.StreamHandler(sys.stderr)
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(log_level.upper())

        if args.log_file:
            handler = logging.FileHandler(args.log_file)
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(log_level.upper())

        args.__dict__.update({'log_level': log_level})
        del args.__dict__['quiet']
        del args.__dict__['verbose']
