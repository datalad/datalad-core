from __future__ import annotations

from datalad_core.commands.exceptions import ParamConstraintContext
from datalad_core.constraints import Constraint


class ParamSetConstraint(Constraint):
    """Base class for constraints of parameter sets

    A parameter set is a mapping of parameter names (``str``) to arbitrary
    values.

    This default implementation only checks that a given value is a
    mapping, and return it as-is.
    """

    def __init__(
        self,
        param_names: tuple[str, ...],
        *,
        aspect: str | None = None,
    ):
        self._context = ParamConstraintContext(
            # TODO: make `param_names`
            parameters=param_names,
            description=aspect,
        )

    @property
    def param_names(self) -> tuple[str, ...]:
        # TODO: make `param_names`
        return self._context.parameters

    @property
    def context(self) -> ParamConstraintContext:
        return self._context
