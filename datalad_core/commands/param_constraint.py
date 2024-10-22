from __future__ import annotations

from abc import abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

from datalad_core.commands.exceptions import ParamConstraintContext
from datalad_core.constraints import Constraint


class ParamSetConstraint(Constraint):
    """Base class for constraints of command parameter sets

    A parameter set is a mapping of parameter names (``str``) to arbitrary
    values.

    This :class:`Constraint` type can be used to implement arbitrary
    validation, and/or transformation of values in a parameters set.
    This includes changing the set of returned parameters compared to
    those passed to the constraint (e.g., adding parameters, moving
    values from one to another). This flexibility allows for implementing
    parameter deprecation and transitions with this constraint type.

    In additions to a basic :class:`Constraint`, this type supports
    reporting more complex context information via its :attr:`context`
    property. This context includes the parameter names, given to the
    constructor. In addition it includes a custom "aspect" description,
    which can further identify which particular facet of the parameter
    set is the subject of a particular constraint implementation,
    such as "identity", "range", or "type".
    """

    def __init__(
        self,
        param_names: tuple[str, ...],
        *,
        aspect: str | None = None,
    ):
        self._context = ParamConstraintContext(
            param_names=param_names,
            description=aspect,
        )

    @property
    def param_names(self) -> tuple[str, ...]:
        """Names of parameters processed by the constraint"""
        return self._context.param_names

    @property
    def context(self) -> ParamConstraintContext:
        """:class:`ParamConstraintContext` with names and aspect description"""
        return self._context

    @abstractmethod
    def __call__(self, val: Mapping[str, Any]) -> Mapping[str, Any]:
        """To be implemented by subclasses to perform parameter set processing

        An implementation must return a mapping of parameter names to their
        processed values.

        On error, implementation should call :meth:`raise_for`.
        """
