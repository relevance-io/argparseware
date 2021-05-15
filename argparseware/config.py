"""
This module contains middleware definitions for handling configuration data, such as
configuration files, environment variables and the like.
"""

import os
import sys
import json
import argparse
import typing

from .core import IMiddleware
from .utils import merge_dicts


class ConfigMiddleware(IMiddleware):
    """
    Configuration file middleware.
    """

    def __init__(self, defaults: typing.List[str] = None, *, allow_multi: bool = False,
                 ignore_missing: bool = False, node: typing.Union[str, typing.List[str]] = None,
                 overwrite: bool = False, merge: bool = True,
                 search_paths: typing.List[str] = sys.path) -> None:
        """
        This middleware loads configuration files and merge their contents into the
        parser's namespace object.

        The *defaults* argument is a list of default configuration files to load.

        If *allow_multi* is enabled, the argument can be specified multiple times, with
        each loaded configuration file being merged to the previous ones.

        If *ignore_missing* is enabled, configuration files that do not exist will not
        cause exceptions to be raised.

        The *node* argument is the path of the node to extract. If omitted, the root
        document is used.

        When *overwrite* is true, values that already exist in the parser's namespace
        will be overwritten by values in the configuration files. Otherwise, if a duplicate
        occurs, the namespace value has precedence, unless it's a dict and merging is enabled.

        When *merge* is enabled, if a value is a dictionary and exists both in the namespace
        and configuration file, it will be merged into the resulting object, complying with
        the *overwrite* parameter for duplicate values. If *merge* is false and *overwrite*
        is true, a value that is a dict that exists in both source and destination will be
        completely overwritten by the configuration file value.

        The *search_path* is a list of paths to search into when the path is relative.
        """
        self.defaults = defaults or []
        self.allow_multi = allow_multi
        self.ignore_missing = ignore_missing
        self.node = node
        self.overwrite = overwrite
        self.merge = merge
        self.search_paths = search_paths or []

    def configure(self, parser: argparse.ArgumentParser) -> None:
        """
        Configure the middleware arguments.
        """
        parser.add_argument('-c', '--config', action='append' if self.allow_multi else None,
                            dest='config_file',
                            help='the path to the configuration file')

    def run(self, args: argparse.Namespace) -> None:
        """
        Run the middleware.
        """
        import anyconfig  # pylint: disable=import-outside-toplevel

        files = args.config_file or self.defaults

        for filename in list(files):
            if os.path.isabs(filename):
                continue
            for path in self.search_paths:
                pathname = os.path.join(path, filename)
                if os.path.isfile(pathname) or os.path.islink(pathname):
                    files.append(pathname)
                    if filename in files:
                        files.remove(filename)

        data = anyconfig.load(files, ignore_missing=self.ignore_missing)
        result = merge_dicts(
            args.__dict__, data,
            overwrite=self.overwrite,
            recurse=self.merge,
        )

        if self.node:
            ref = result
            node = [self.node] if isinstance(self.node, str) else self.node
            for item in node:
                ref = result.get(item, {})
            result = ref

        args.__dict__.update(result)


class ConfigListMiddleware(IMiddleware):
    """
    Configuration file list middleware.
    """

    def __init__(self, defaults: typing.Union[bool, dict] = None, *, allow_multi: bool = True,
                 ignore_missing: bool = False, merge: bool = True) -> None:
        """
        This middleware loads configuration files and adds a variable list to the argument
        parser namespace, with each entry being the parsed configuration data in the
        order it was declared.

        The *defaults* argument is a dictionary of data that will be set as the base data
        dictionary for each loaded configuration file. If *defaults* is the `True` boolean,
        the arguments from the namespace are used as defaults.

        If *allow_multi* is disabled, the argument can be only be specified once.

        If *ignore_missing* is enabled, configuration files that do not exist will not
        cause exceptions to be raised.

        When *merge* is enabled, if a value is a dictionary and exists both in the namespace
        and configuration file, it will be merged into the resulting object. If *merge* is false,
        a value that is a dict that exists in both source and destination will be
        completely overwritten by the configuration file value.
        """
        self.defaults = defaults or {}
        self.allow_multi = allow_multi
        self.ignore_missing = ignore_missing
        self.merge = merge

    def configure(self, parser: argparse.ArgumentParser) -> None:
        """
        Configure the middleware arguments.
        """
        parser.add_argument('-c', '--config', action='append' if self.allow_multi else None,
                            dest='config_files',
                            help='the path to the configuration file')

    def run(self, args: argparse.Namespace) -> None:
        """
        Run the middleware.
        """
        import anyconfig  # pylint: disable=import-outside-toplevel

        defaults = args.__dict__ if self.defaults is True else self.defaults

        results = []
        for filename in args.config_files or []:
            if filename == '-':
                result = dict(defaults)
            else:
                data = anyconfig.load(filename, ignore_missing=self.ignore_missing)
                result = merge_dicts(
                    defaults, data,
                    overwrite=True,
                    recurse=self.merge,
                )
            results.append(result)

        args.__dict__.update({'config_data': results})


class InlineOptionMiddleware(IMiddleware):
    """
    Inline option middleware.
    """

    def __init__(self, *args, dest: str = None, merge: bool = False,
                 help: str = None) -> None:  # pylint:disable=redefined-builtin
        """
        This middleware registers an argument that allows to specify configuration
        values/arguments using a string syntax, which can be used mutiple times.

        If *merge* is enabled, a dictionary is returned rather than a list of dictionaries.

        The *dest* and *help* arguments works like the `ArgumentParser` equivalents.

        Each argument should be in the form of `KEY=VALUE`. The VALUE will be parsed
        as a JSON string. If it's not valid JSON, it will be assumed to be a string.//

        Example values:
            - `foo=42`: int
            - `foo=42.0`: float
            - `foo=null`: None
            - `foo=bar`: str
            - `foo=[1,2,3]`: list
            - `foo={"hello": "world"}`: dict
            - `foo=true`: bool
            - `foo="null"`: str
        """
        self.args = args
        self.dest = dest
        self.merge = merge
        self.help = help

    def configure(self, parser: argparse.ArgumentParser) -> None:
        """
        Configure the middleware arguments.
        """
        kwargs = {}
        if self.dest:
            kwargs['dest'] = self.dest
        if self.help:
            kwargs['help'] = self.help

        arg = parser.add_argument(*self.args, action='append', **kwargs)
        self.dest = arg.dest

    def run(self, args: argparse.Namespace) -> None:
        """
        Run the middleware.
        """
        data = getattr(args, self.dest)

        items = []
        for item in data or []:
            if '=' in item:
                key, value = item.split('=', 1)
                try:
                    value = json.loads(value)
                except json.decoder.JSONDecodeError:
                    pass
                items.append({key: value})

        if self.merge:
            result = {}
            for item in items:
                result.update(item)
            args.__dict__.update({self.dest: result})
        else:
            args.__dict__.update({self.dest: list(items)})


class InlineConfigMiddleware(IMiddleware):
    """
    Inline configuration middleware.
    """

    def __init__(self, *, overwrite: bool = True, merge: bool = True) -> None:
        """
        This middleware registers an argument - that can be specified multiple times -
        that allows to override configuration values/arguments using a string syntax.

        The *overwrite* and *merge* arguments work the same as the `ConfigMiddleware`.

        The parsing rules are the same as the `InlineConfigMiddleware`.
        """
        self.overwrite = overwrite
        self.merge = merge

    def configure(self, parser: argparse.ArgumentParser) -> None:
        """
        Configure the middleware arguments.
        """
        parser.add_argument('-e', '--env', action='append',
                            dest='config_env',
                            help='additional configuration values to pass, as JSON strings')

    def run(self, args: argparse.Namespace) -> None:
        """
        Run the middleware.
        """
        items = []
        for item in args.config_env or []:
            if '=' in item:
                key, value = item.split('=', 1)
                try:
                    value = json.loads(value)
                except json.decoder.JSONDecodeError:
                    pass
                items.append({key: value})

        result = merge_dicts(
            args.__dict__, *items,
            overwrite=self.overwrite,
            recurse=self.merge,
        )

        args.__dict__.update(result)
        del args.__dict__['config_env']


class EnvironmentConfigMiddleware(IMiddleware):
    """
    Environment variables middleware.
    """

    def __init__(self, prefix: str, *, lower: bool = True, overwrite: bool = False,
                 merge: bool = True) -> None:
        """
        This middleware allows for configuration values/arguments to be overriden using
        environment variables.

        The *prefix* is a string argument that defines the prefix (case sensitive) to
        look for in environment variables. Per example, with a prefix of `TEST_`, the
        variables `TEST_FOO` and `TEST_BAR` will be matched.

        The `lower` argument defines whether to lower case the variable key - everything
        after the prefix - when storing it. If enabled, in `TEST_FOO=1`, the resulting
        argument key will be `foo` rather than `FOO`.

        The values parsing rules, *overwrite* and *merge* arguments work the same way as
        the `InlineConfigMiddleware`.
        """
        self.lower = lower
        self.prefix = prefix
        self.overwrite = overwrite
        self.merge = merge

    def run(self, args: argparse.Namespace) -> None:
        """
        Run the middleware.
        """
        data = {}
        for key, value in os.environ.items():
            if not key.startswith(self.prefix):
                continue

            if self.lower:
                key = key[len(self.prefix):].lower()

            try:
                value = json.loads(value)
                data[key] = value
            except json.decoder.JSONDecodeError:
                data[key] = value

        result = merge_dicts(
            args.__dict__, data,
            overwrite=self.overwrite,
            recurse=self.merge,
        )
        args.__dict__.update(result)


class InjectMiddleware(IMiddleware):
    """
    Default arguments injection middleware.
    """

    def __init__(self, defaults: dict) -> None:
        """
        This middleware injects defaults for any parameter that wasn't specified at
        runtime.
        """
        self.defaults = defaults

    def run(self, args: argparse.Namespace) -> None:
        """
        Run the middleware.
        """
        result = merge_dicts(
            args.__dict__, self.defaults,
            overwrite=False, recurse=True,
        )

        args.__dict__.update(result)
