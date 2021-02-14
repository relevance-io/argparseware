import abc
import typing
import sys
import json
import argparse
from flask import url_for
from flask import got_request_exception
from flask import Flask
from flask import Blueprint
from werkzeug.routing import Rule
from werkzeug.exceptions import InternalServerError

from . import Command
from . import CommandsMiddleware


class CommandError(RuntimeError):
    """
    Raised when a command throws an error.
    """


class ICommandParser(metaclass=abc.ABCMeta):
    """
    This abstract class can be implemented to parse routes into commands.
    """

    def get_url(self, app: Flask, rule: Rule, args: dict) -> str:
        """
        Build the URL for a specific set of arguments.
        """
        server_name = app.config.get('SERVER_NAME')
        app.config['SERVER_NAME'] = '.'

        try:
            with app.app_context():
                url = url_for(rule.endpoint, **args)
                return url[8:]
        finally:
            app.config['SERVER_NAME'] = server_name

    def get_endpoints(self, app: Flask) -> typing.Tuple[Rule, typing.Callable]:
        """
        Parse the endpoints from a given application.
        """
        results = []
        for rule in app.url_map.iter_rules():
            func = app.view_functions[rule.endpoint]  # func
            item = (rule, func)
            results.append(item)

        return results

    @abc.abstractmethod
    def parse(self, app: Flask):
        """
        Parse the application into commands.
        """


class RouteCommandParser(ICommandParser):
    # The method to command mapping
    METHOD_MAP = {
        'get': 'get',
        'post': 'create',
        'put': 'set',
        'patch': 'update',
        'delete': 'delete',
    }

    def __init__(self, *, use_method: bool = False) -> None:
        self.use_method = False

    def parse(self, app: Flask):
        def command_handler(rule, method, body_params=None):
            def error_handler(_):
                raise CommandError()

            def error_handler_signal(_, exception):
                raise exception from None

            def handler(args):
                url = self.get_url(app, rule, args.__dict__)
                client = app.test_client()
                app.errorhandler(InternalServerError)(error_handler)

                with app.app_context():
                    func = getattr(client, method)
                    response = func(url)
                    if response.json:
                        content = response.json
                    else:
                        try:
                            content = response.data.decode('utf-8')
                        except AttributeError:
                            content = None

                    if response.status_code >= 400:
                        raise CommandError(content)

                    if isinstance(content, (list, dict)):
                        print(json.dumps(content, indent=2))
                    else:
                        print(content)

            return handler

        results = []

        endpoints = self.get_endpoints(app)
        for rule, func in endpoints:
            parts = []

            for part in rule.rule.strip('/').split('/'):
                if part[0] == '<' and part[-1] == '>':
                    pass
                else:
                    parts.append(part)

            types = typing.get_type_hints(func)
            defaults = typing._get_defaults(func)  # pylint:disable=protected-access
            defaults.update(rule.defaults or {})
            name = ' '.join(parts)

            for method in rule.methods:
                if method.lower() not in self.METHOD_MAP:
                    continue

                method = method.lower()
                method_name = method.lower() if self.use_method else self.METHOD_MAP[method]

                command = Command('{} {}'.format(name, method_name), command_handler(rule, method))

                for arg in rule.arguments:
                    default = defaults.get(arg)
                    data_type = types.get(arg, str)
                    command.add_argument('--{}'.format(arg), type=data_type, default=default,
                                         required=default is None)
                results.append(command)

        return results


class FlaskCommandsMiddleware(CommandsMiddleware):
    def __init__(self, app: Flask, parser: ICommandParser = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.app = app
        self.parser = parser or RouteCommandParser()

    def configure(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """
        Configure the middleware arguments.
        """
        self.commands = self.parser.parse(self.app)
        return super().configure(parser)

    def run(self, args: argparse.Namespace) -> None:
        """
        Run the middleware.
        """
        try:
            super().run(args)
        except CommandError as ex:
            msg = str(ex)
            if msg:
                print(msg)
            sys.exit(1)
