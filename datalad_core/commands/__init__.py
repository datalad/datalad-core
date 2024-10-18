"""Components for implementing DataLad commands

.. currentmodule:: datalad_core.commands
.. autosummary::
   :toctree: generated

   datalad_command
   Dataset
   ResultHandler
   DefaultHandler
   PassthroughHandler
   get_default_result_handler
   set_default_result_handler
"""

__all__ = [
    'Dataset',
    'DefaultHandler',
    'ResultHandler',
    'PassthroughHandler',
    'datalad_command',
    'get_default_result_handler',
    'set_default_result_handler',
]


from .dataset import Dataset
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
