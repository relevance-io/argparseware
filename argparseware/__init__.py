"""
argparse middleware library.

argparseware is designed as a turnkey library for developers who like the
standard library, most specifically argparse. It extends the built-in argparse
library by simply allowing one to define middleware components in a very
simple syntax, improving reusability, while not compromising or reinventing
the programming interfaces they already know.
"""

from .core import ArgumentParser


# Package version
__version__ = '0.9.1'
__versiont__ = (0, 9, 1)

# Author information
__author__ = 'Francis Lacroix'
__author_email__ = 'f@relevance.io'

# License information
__license__ = 'TBD'
__copyright__ = 'Relevance.io 2019-'
