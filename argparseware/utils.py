"""
This module provides utility functions that can be used in middleware.
"""

import os


def merge_dicts(data: dict, *args, overwrite: bool = True, recurse: bool = True) -> dict:
    """
    Merge dictionaries recursively and return the result.

    If *recurse* is true, the dictionaries are merged recursively. When *overwrite*
    is true, any value that exist in previous dictionaries will be overwritten with the
    latest (until that value is also a dictionary and *recurse* is true).

    >>> merge_dicts({'foo': {'hello': 'world'}}, {'foo': {'bar': 'baz'}})
    {'foo': {'hello': 'world', 'bar': 'baz'}}
    >>> merge_dicts({'foo': {'hello': 'world'}}, {'foo': {'bar': 'baz'}}, recurse=False)
    {'foo': {'bar': 'baz'}}
    >>> merge_dicts({'foo': {'hello': 'world'}}, {'foo': {'hello': 'test'}}, overwrite=False)
    {'foo': {'hello': 'world'}}
    >>> merge_dicts({'foo': {'hello': 'world'}}, {'foo': 'bar'})
    {'foo': 'bar'}
    """
    result = dict(data)

    for item in args:
        for key, value in item.items():
            data_value = data.get(key)

            if isinstance(value, dict) and isinstance(data_value, dict) and recurse:
                result[key] = merge_dicts(data_value, value, overwrite=overwrite)
            elif key in data:
                if overwrite:
                    result[key] = value
                else:
                    result[key] = data_value
            else:
                result[key] = value

    return result


def which(program: str) -> str:
    """
    Find the path to an exectable.
    """
    def is_executable(filename):
        """ Test if a file is executable. """
        return os.path.isfile(filename) and os.access(filename, os.X_OK)

    path = os.path.split(program)[0]
    if path:
        if is_executable(program):
            return program

    for path in os.environ['PATH'].split(os.pathsep):
        filename = os.path.join(path, program)
        if is_executable(filename):
            return filename

    return None
