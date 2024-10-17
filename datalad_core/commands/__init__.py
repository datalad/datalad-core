"""Components for implementing DataLad commands

.. currentmodule:: datalad_core.commands
.. autosummary::
   :toctree: generated

   datalad_command
   ResultHandler
   DefaultHandler
   PassthroughHandler
   get_default_result_handler
   set_default_result_handler
"""

__all__ = [
    'DefaultHandler',
    'ResultHandler',
    'PassthroughHandler',
    'datalad_command',
    'get_default_result_handler',
    'set_default_result_handler',
]


from .decorator import datalad_command
from .default_result_handler import (
    DefaultHandler,
    get_default_result_handler,
    set_default_result_handler,
)
from .result_handler import (
    PassthroughHandler,
    ResultHandler,
)
