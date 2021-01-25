# argparseware

The **argparseware** library is a simple to use, extensible library that complements the
`argparse` package from the standard library. It provides the same interfaces - with
some additions - allowing developers to work quickly with tools they already know and
are well documented, while promoting code reusability.

More specifically, **argparseware** extends the default argument parser of `argparse`
by providing a quick and clean interface to define and use middleware components for
command-line applications, for such things as logging, loading configurations or
serving WSGI applications.

Its interface is reliant on `argparse` with only some minor additions to improve
code reusability.

## Getting started

### Requirements

These are the general requirements for using this package:

- Python 3.6 or higher

No other dependencies are required for the base package and interfaces to work.

#### Optional dependencies

Some bundled middleware require optional dependencies:

- `ConfigMiddleware` requires `anyconfig`
- `FlaskServerMiddleware` requires `flask`
- `GunicornServerMiddleware` requires `gunicorn`
- `GeventServerMiddleware` requires `gevent`

### Installation

Since this is a standard Python package, install with:

```shell
pip install argparseware
```

#### Development mode

Again, as this is a standard Python package, install in development (editable) mode with:

```shell
pip install -e .
```

## Usage

This package can be used the same way as you would `argparse`:

```python
import argparseware

parser = argparseware.ArgumentParser(
    prog='myprog',
    description='Some test program',
)
parser.add_argument('--arg', help='some arg')

namespace = parser.parse_args()
```

...then run with:

```python
python3 your-script.py --arg foo
```

### What is middleware?

Where `argparseware` really shines is by using the bundled or custom middleware. Middleware
have two phases: execution and configuration.

Execution is the step that is executed after all arguments have been parsed. It is essentially
a function that accepts the `Namespace` object from argparse as its first argument and does
something with it:

```python
parser = argparseware.ArgumentParser()
parser.add_argument('--some-arg', 'some generic argument')

@parser.middleware
def my_middleware(args):
    print('some_arg value is:', args.some_arg)

parser.run()
```

It's useful for executing and reusing code that is run *after* the arguments are parsed.

While it's pretty useful in itself, this is an argparse extension, so you probably will want
to be able to define your own arguments:

```python
parser = argparseware.ArgumentParser()

@parser.middleware
def my_middleware(args):
    print('some_arg value is:', args.some_arg)

@my_middleware.configure
def config_my_middleware(parser):
    parser.add_argument('--some-arg', help='some arg as a string')

parser.run()
```

The `configure` step is executed *before* the arguments are parsed, so this is where you'll
want to add your custom arguments or perform validation on other defined arguments.

This is the easiest form of middleware definition, but it doesn't stop there! Keep reading
for more useful ways of using **argparseware**.

### Loading middleware

If you already have existing middleware in a common library, or if you want to use
some of the bundled middleware, for example, the logging middleware:

```python
import argparseware
from argparseware.common import LoggingMiddleware

parser = argparseware.ArgumentParser()
parser.add_middleware(LoggingMiddleware())
parser.run()
```

...then run with:

```shell
python3 your-script.py --verbose
```

The above will automatically configure logging after the arguments are parsed.

### Defining middleware

The easiest way to define your own reusable middleware component is to use the
`middleware` decorator:

```python
import argparseware

@argparseware.middleware
def my_middleware(args):
    print('some_arg value is "foo":', args.some_arg == 'foo')

@my_middleware.configure
def config_my_middleware(parser):
    parser.add_argument('--some-arg', 'some argument, try value: foo')

parser = argparseware.ArgumentParser(prog='testprog')
parser.add_middleware(my_middleware)
parser.run()
```

### Complex middleware

With some middleware, you'll want to be able to customize it and pass arguments
to it. This can be done with the `IMiddleware` abstract class:

```
from argparseware.core import IMiddleware

class MyMiddleware(IMiddleware):
    def __init__(self, default_value):
        self.default_value = default_value

    def configure(self, parser):
        parser.add_argument('--some-arg', default=self.default, help='some arg')

    def run(self, args):
        print('you passed', args.some_arg, 'default was', self.default_value)

parser = argparseware.ArgumentParser()
parser.add_middleware(MyMiddleware(42))
parser.run()
```

### Adapting existing codebases

While it's great to have code reuse, sometimes you want the best of both worlds. In
**argparseware**, the parser's `run` method returns the same thing as the argparse
`parse_args` method would, so you can easily adapt existing code:

```python
import argparseware
from argparseware.common import LoggingMiddleware

parser = argparseware.ArgumentParser()
parser.add_argument('--test')
parser.add_middleware(LoggingMiddleware())
args = parser.run()

if args.test == 'hello world':
    print('hello world')
```

## License

This code and its documentation is provided under the MIT License, bundled as the `LICENSE`
file. All original rights are reserved to Relevance.io 2020-.
