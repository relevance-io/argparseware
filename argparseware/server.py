"""
This module provides middleware definitions for use with WSGI servers and
applications like Flask and gunicorn.
"""

import os
import abc
import sys
import argparse
import signal
import typing
import logging

from .core import IMiddleware
from .common import LoggingMiddleware


class ServerMiddleware(IMiddleware, metaclass=abc.ABCMeta):
    """
    WSGI server middleware.
    """

    def __init__(self, app: typing.Callable, addr: typing.Union[int, str]) -> None:
        """
        This middleware interface can be used by sub-implementations to configure
        a WSGI server to listen on a specific address.

        The first *app* argument is the WSGI callable object.

        The *addr* argument should be either an integer with a port number, or a string
        in the format of `addr:port`. If an int is supplied, the listen address
        is assumed to be `0.0.0.0` (listening on all interfaces).
        """
        self.app = app
        self.addr = addr

    def parse_addr(self, addr: typing.Union[int, str]) -> typing.Tuple[str, int]:
        """
        Parse an address string into a tuple of host, port.
        """
        if isinstance(addr, str) and ':' in addr:
            host, port = addr.split(addr)
            host = host or '0.0.0.0'
            return (host, int(port))

        return ('0.0.0.0', int(addr))

    def configure(self, parser: argparse.ArgumentParser) -> None:
        """
        Configure the middleware arguments.
        """
        parser.add_argument('-L', '--listen-addr', default=str(self.addr),
                            help='the address and/or port to listen on '
                                 '(e.g.: 8080 or localhost:1234')

    @abc.abstractmethod
    def run(self, args: argparse.Namespace) -> None:
        """
        This method should be implemented by subclasses to actually run a server
        based on the source arguments.
        """

    @abc.abstractmethod
    def stop(self) -> None:
        """
        Stop the server.
        """


class FlaskServerMiddleware(ServerMiddleware, metaclass=abc.ABCMeta):
    """
    Server middleware to run Flask applications integrated server.
    """

    def __init__(self, app: typing.Union['Flask', ServerMiddleware],
                 addr: typing.Union[int, str] = None, *, debug: bool = False) -> None:
        """
        This middleware allows to run Flask applications through the
        command line.

        The first argument should be a `Flask` instance to run. Alternatively,
        it can be a instance of a `ServerMiddleware` subclass. When that is the
        case, the server will be started using this middleware object instead,
        unless the debug switch (`--debug`) is passed at runtime.

        Before the server is run, the passed arguments are also assigned to
        application object's `Flask.args` attribute.
        """
        if not isinstance(app, ServerMiddleware):
            if not addr:
                raise ValueError('addr argument is mandatory')
            super().__init__(app, addr)
        else:
            super().__init__(app, app.addr)
        self.debug = debug

    def configure(self, parser: argparse.ArgumentParser) -> None:
        """
        Configure the middleware arguments.
        """
        if isinstance(self.app, ServerMiddleware):
            self.app.configure(parser)
        else:
            super().configure(parser)

        parser.add_argument('--debug', action='store_true', dest='flask_debug',
                            help='enable the server debug mode')

    def run(self, args: argparse.Namespace) -> None:
        """
        Run the middleware.
        """
        host, port = self.parse_addr(args.listen_addr)
        if isinstance(self.app, ServerMiddleware):
            self.app.app.args = args
            if args.flask_debug:
                self.app.app.run(host=host, port=port, debug=True)
            else:
                self.app.run(args)
        else:
            self.app.args = args
            self.app.run(host=host, port=port, debug=args.flask_debug)

    def stop(self) -> None:
        """
        Stop the server.
        """
        raise NotImplementedError()



class GunicornServerMiddleware(ServerMiddleware, metaclass=abc.ABCMeta):
    """
    Server middleware that wraps gunicorn for WSGI applicications.
    """
    # pylint: disable=import-outside-toplevel

    def __init__(self, *args, count: int = None, timeout: int = 120,
                 worker_class: str = 'sync', **kwargs) -> None:
        """
        This middleware wraps a WSGI application callable to run through
        a gunicorn server.

        The *count* is the default count of workers to pre-fork or the number of threads
        if using gthread. If omitted, it defaults to the number of available CPUs.

        The *timeout* is the default count for a request timeout, after which
        the pre-fork worker will bail and terminate a pending request.
        """
        super().__init__(*args)
        import multiprocessing
        self.count = count or multiprocessing.cpu_count()
        self.worker_class = worker_class
        self.timeout = timeout
        self.kwargs = kwargs
        self.server = None

    def configure(self, parser: argparse.ArgumentParser) -> None:
        """
        Configure the middleware arguments.
        """
        super().configure(parser)

        parser.add_argument('-j', '--prefork-count', type=int, default=self.count,
                            help='the number of workers to pre-fork')
        parser.add_argument('-T', '--request-timeout', type=int, default=self.timeout,
                            help='the amount of time before a worker times out')
        parser.add_argument('-l', '--prefork-preload', action='store_true',
                            help='preload the workers on startup')

        found = False
        for item in parser.middlewares:
            if isinstance(item, LoggingMiddleware):
                found = True
                break

        if not found:
            parser.add_middleware(LoggingMiddleware())

    def run(self, args: argparse.Namespace) -> None:
        """
        Run the middleware.
        """
        try:
            log_level = args.log_level
        except AttributeError:
            log_level = 'info'

        self.server = self.create_server(
            args.listen_addr,
            count=args.prefork_count,
            timeout=args.request_timeout,
            preload=args.prefork_preload,
            log_level=log_level,
        )
        self.server.run()

    def create_server(self, addr, *, count: int, timeout: int, preload: bool,
                   log_level: int) -> 'WSGIApplication':
        """
        Create the application server through gunicorn.

        This function creates and runs the application server for the *app* WSGI application.
        It will listen bind to *host* on *port*.

        Since it is backed by gunicorn and uses a pre-fork model, it can be passed the *count*
        number of workers to create on startup. It defaults to the number of CPUs on the
        machine.

        The *timeout* defines, in seconds, the amount of time after which a worker is
        considered to have timed out and will be forcefully restarted.

        If *preload* is switched on, the code is pre-loaded in the workers at startup
        rather than lazy loaded at runtime.

        The *log_level* can be changed to a specific verbosity level, using the `logging`
        package values.
        """
        from gunicorn.app.wsgiapp import WSGIApplication
        from gunicorn.arbiter import Arbiter

        wsgi_app = self.app
        class WSGIServer(WSGIApplication):
            """The WSGI Server implementation."""

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.arbiter = Arbiter(self)

            def init(self, parser, opts, args):
                pass

            def load(self):
                return wsgi_app

            def run(self):
                self.arbiter.run()

            def stop(self):
                """ Allows the server to be stopped on demand. """
                self.arbiter.signal(signal.SIGINT, None)

        host, port = self.parse_addr(addr)

        args = [
            '--bind', '{0}:{1}'.format(host, port),
            '--log-level', logging.getLevelName(log_level).lower(),
            '--workers' if self.worker_class != 'gthread' else '--threads', str(count),
            '--timeout', str(timeout),
            '--preload' if preload else '',
            '--access-logfile', '-',
        ]

        if self.worker_class == 'gthread':
            args += ['--workers', '1']

        for key, value in self.kwargs.items():
            key = key.replace('_', '-')
            args += ['--{0}'.format(key), value]

        sys.argv = [sys.argv[0]]
        os.environ['GUNICORN_CMD_ARGS'] = ' '.join(args)
        return WSGIServer('')

    def stop(self) -> None:
        """
        Stop the server.
        """
        if self.server:
            self.server.stop()
            self.server = None


class GeventServerMiddleware(ServerMiddleware, metaclass=abc.ABCMeta):
    """
    Server middleware that wraps gevent for WSGI applicications.
    """
    # pylint: disable=import-outside-toplevel

    def __init__(self, *args, **kwargs):
        """
        Initialize the middleware.
        """
        super().__init__(*args, **kwargs)
        self.server = None

    def run(self, args: argparse.Namespace) -> None:
        """
        Run the middleware.
        """
        from gevent.pywsgi import WSGIServer
        host, port = self.parse_addr(args.listen_addr)

        def shutdown_server(_signum, _frame):
            """ Handle the shutdown signal. """
            self.stop()

        signal.signal(signal.SIGINT, shutdown_server)
        self.server = WSGIServer((host, port), self.app)
        self.server.serve_forever()

    def stop(self) -> None:
        """
        Stop the server.
        """
        if self.server:
            self.server.stop()
            try:
                self.server.close()
            except Exception:
                pass
            finally:
                self.server = None
