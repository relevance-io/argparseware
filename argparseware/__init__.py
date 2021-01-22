"""
Middleware library for argparse.

argparseware is designed as a turnkey library for developers who like the
standard library, most specifically argparse. It extends the built-in argparse
library by simply allowing one to define middleware components in a very
simple syntax, improving reusability, while not compromising or reinventing
the programming interfaces they already know.
"""

from .core import middleware
from .core import IMiddleware
from .core import WrapperMiddleware
from .core import ArgumentParser
