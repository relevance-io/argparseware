import os
import sys
import distutils.cmd


class CleanCommand(distutils.cmd.Command):
    description = 'clean the directory from build files'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        from shutil import rmtree

        package_name = self.distribution.packages[0]
        dirs = [
            '.mypy_cache/',
            'docs/apidoc',
            'build/', 'dist/', '{0}.egg-info/'.format(package_name), '.eggs',
        ]

        for item in dirs:
            rmtree(item, ignore_errors=True)
        for root, _, _ in os.walk('.'):
            rmtree('{0}/__pycache__/'.format(root), ignore_errors=True)


class BuildApidocCommand(distutils.cmd.Command):
    description = 'build the api documentation'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        from sphinx.apidoc import main as apidoc
        package_name = self.distribution.packages[0]
        if apidoc(['-f', '-e', '-o', 'docs/apidoc', package_name]):
            sys.exit(1)


class BuildSphinxCommand(distutils.cmd.Command):
    description = 'build the Sphinx documentation'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        from sphinx import main as sphinx
        if sphinx(['sphinx', 'docs/', 'build/docs/']) > 0:
            sys.exit(1)


class LintCommand(distutils.cmd.Command):
    description = 'check source files for errors and warnings'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        from pylint.lint import Run as pylint
        package_name = self.distribution.packages[0]
        pylint([package_name])

