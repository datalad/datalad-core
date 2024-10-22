"""Components for implementing DataLad commands

.. currentmodule:: datalad_core.commands
.. autosummary::
   :toctree: generated

   datalad_command
   Dataset
   ResultHandler
   DefaultHandler
   ParamProcessor
   ParamErrors
   ParamSetConstraint
   PassthroughHandler
   get_default_result_handler
   set_default_result_handler
"""

__all__ = [
    'Dataset',
    'DefaultHandler',
    'ResultHandler',
    'ParamProcessor',
    'ParamErrors',
    'ParamSetConstraint',
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
from .exceptions import ParamErrors
from .param_constraint import ParamSetConstraint
from .preproc import ParamProcessor
from .result_handler import (
    PassthroughHandler,
    ResultHandler,
)
