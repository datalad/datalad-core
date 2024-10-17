"""Parameter validation, coercion, and documentation

For (validation/coercion) errors, a :class:`ConstraintError` class is provided.
This class supports error reporting in a structure fashion with standard (yet
customizable) error messages, and is capable of communicating the underlying
causes of an error in full detail without the need to generate long textual
descriptions.

.. currentmodule:: datalad_core.constraints
.. autosummary::
   :toctree: generated

   ConstraintError
"""

__all__ = [
    'ConstraintError',
]


from .exceptions import (
    ConstraintError,
)
