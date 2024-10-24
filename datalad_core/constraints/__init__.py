"""Parameter validation, coercion, and documentation

This module provides a set of classes to validate and document
parameters. In a nutshell, each of these
:class:`Constraint` classes:

- focuses on a specific aspect, such as type coercion,
  or checking particular input properties
- is instantiated with a set of parameters to customize
  such an instance for a particular task
- performs its task by receiving an input via its ``__call__()``
  method
- provides default auto-documentation

Individual :class:`Constraint` instances can be combined with logical ``and``
(:class:`AllOf`) and ``or`` (:class:`AnyOf`) operations to form arbitrarily
complex constructs.

For (validation/coercion) errors, a :class:`ConstraintError` class is provided.
This class supports error reporting in a structure fashion with standard (yet
customizable) error messages, and is capable of communicating the underlying
causes of an error in full detail without the need to generate long textual
descriptions.

If the provided input descriptions and error messages of a particular
constraint are not an optimal fit for a particular context, they can be replace
by wrapping a constraint instance into :class:`WithDescription`. This creates a
new constraint instance that maintains the exact same validation/coercion
behavior, but has a targeted description (input synopsis and description,
and/or error message template).


.. currentmodule:: datalad_core.constraints
.. autosummary::
   :toctree: generated

   Constraint
   AllOf
   AnyOf
   ConstraintError
   WithDescription
   NoConstraint
"""

__all__ = [
    'Constraint',
    'AllOf',
    'AnyOf',
    'ConstraintError',
    'WithDescription',
    'NoConstraint',
]


from .basic import (
    NoConstraint,
)
from .constraint import (
    AllOf,
    AnyOf,
    Constraint,
)
from .exceptions import (
    ConstraintError,
)
from .wrapper import WithDescription
