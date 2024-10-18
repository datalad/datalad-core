"""Components for implementing DataLad commands

At the very core, a DataLad command is function that documents and validates
its parameters in a particular way, and yields return values that follow
particular conventions.

In its simplest form, a DataLad command can be created like this:

    >>> @datalad_command()
    ... def my_command(some_arg):
    ...     # do processing ...
    ...     return  # typically one or more results are returned/yielded

The :func:`datalad_command` decorator wraps a function, and automatically
establishes the conventions expected for a DataLad command (see its
documentation for details).

Beyond this simplest use, the decorator can be used to customize parameter
validation, and result handling. Both aspects are handled by customizable
classes.

.. currentmodule:: datalad_core.commands
.. autosummary::
   :toctree: generated

   datalad_command
   Dataset
   ResultHandler
   StandardResultHandler
   PassthroughHandler
   get_default_result_handler
   set_default_result_handler
"""

__all__ = [
    'Dataset',
    'StandardResultHandler',
    'ResultHandler',
    'PassthroughHandler',
    'datalad_command',
    'get_default_result_handler',
    'set_default_result_handler',
]


from .dataset import Dataset
from .decorator import datalad_command
from .default_result_handler import (
    StandardResultHandler,
    get_default_result_handler,
    set_default_result_handler,
)
from .result_handler import (
    PassthroughHandler,
    ResultHandler,
)
