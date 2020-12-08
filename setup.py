#!/usr/bin/env python3

from setuptools import setup


# Optional dependencies
extras_require = {
    'config': [
        'anyconfig>=0.9.1,<0.10',
        'PyYAML>=3.12,<4',
    ],
    'wsgi': [
        'Flask>=1.1.1,<2',
        'gunicorn>=20.0.4,<21',
        'gevent>=20.6.2,<21',
    ],
}

# All dependencies
extras_require['all'] = []
for key in extras_require:
    if key != 'all':
        extras_require['all'] += extras_require[key]


# Setup script
setup(
    extras_require=extras_require,
)
