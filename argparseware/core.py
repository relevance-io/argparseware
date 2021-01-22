"""
This package provides interfaces to enhance the `argparse` module allowing
for custom middleware to be injected during parsing and at run time.
"""

import abc
import argparse
import typing


def middleware(func: typing.Callable):
    """
    This method is an alias for `WrapperMiddleware` to be used
    as a decorator.
    """
    return WrapperMiddleware(func)


class IMiddleware(metaclass=abc.ABCMeta):
    """
    This class is the base interface for all middleware.
    """

    def configure(self, parser: argparse.ArgumentParser) -> None:
        """
        This method is invoked before the arguments are parsed and is passed the parser
        instance.

        It's in this method that a subclass can add custom parser arguments.
        """

    def run(self, args: argparse.Namespace) -> None:
        """
        This method is invoked the the parser's `run` method is invoked, after all
        the middlewares have been configured and the arguments have been parsed. The
        first argument is the namespace object containing the parsed arguments.
        """


class WrapperMiddleware(IMiddleware):
    """
    Wrapper middlware, typically used by decorators.
    """

    def __init__(self, func: typing.Callable, conf: typing.Callable = None) -> None:
        """
        This middleware is typically used by decorators to create custom middleware
        on the fly.

        The *func* argument is a callable that will be executed, with the extracted
        arguments as the first paramter.

        The *conf* argument is a callable that will be executed before the arguments
        are parsed, usually to define custom arguments. Alternatively, the `configure`
        method also acts as a decorator that can be used for this same purpose.
        """
        self.func = func
        self.conf = conf or (lambda parser: None)

    def configure(self, arg: typing.Union[typing.Callable, argparse.ArgumentParser]) \
            -> typing.Union['WrapperMiddleware', None]:  # pylint: disable=arguments-differ
        """
        Configure the middleware.
        """
        if isinstance(arg, ArgumentParser):
            self.conf(arg)
            return None

        self.conf = arg
        return self

    def run(self, args):
        self.func(args)


class ArgumentParser(argparse.ArgumentParser):
    """
    Argument parser class override.
    """

    def __init__(self, *args, **kwargs) -> None:
        """
        This special argument parser class works the same way as the original,
        except that it adds the `add_middleware` and `run` methods.
        """
        super().__init__(*args, **kwargs)
        self.middlewares = []

    def add_middleware(self, item: IMiddleware) -> None:
        """
        Add a middleware to the parser.

        Middleware objects are first configured prior to parsing arguments,
        then run when the parser's `run` method is invoked.

        It is possible to add middleware within another middleware `configure`
        or `run` implementations using this method.
        """
        self.middlewares.append(item)

    def middleware(self, func: typing.Callable) -> WrapperMiddleware:
        """
        This method allows to easily add a custom middleware function to an
        argument parser.
        """
        item = WrapperMiddleware(func)
        self.add_middleware(item)
        return item

    def parse_args(self, *args, **kwargs) -> argparse.Namespace:  # pylint: disable=arguments-differ,signature-differs
        """
        Override the parent method to automatically configure middleware.
        """
        # NOTE: the reason we're not using a for-loop here is to allow middleware to
        # add other middleware within their configure method.
        index = 0
        while True:
            try:
                item = self.middlewares[index]
                index += 1
            except IndexError:
                break
            item.configure(self)

        return super().parse_args(*args, **kwargs)

    def run(self, *args, **kwargs) -> argparse.Namespace:
        """
        Run the argument parser.

        This method works the same way as `parse_args` returning a `Namespace`
        object with the arguments. However, unlike the former, once the arguments
        have been parsed, each registered middleware will have its `run` method
        invoked and the resulting namespace object will be returned.
        """
        namespace = self.parse_args(*args, **kwargs)

        index = 0
        while True:
            try:
                item = self.middlewares[index]
                index += 1
            except IndexError:
                break
            item.run(namespace)

        return namespace
