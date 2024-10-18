"""Base classes for constraints and their logical connectives"""

from __future__ import annotations

from abc import (
    ABC,
    abstractmethod,
)
from typing import Any

from datalad_core.constraints.exceptions import ConstraintError


class Constraint(ABC):
    """Base class for value coercion/validation.

    These classes are also meant to be able to generate appropriate
    documentation on an appropriate parameter value.
    """

    def __str__(self) -> str:
        """Rudimentary self-description"""
        return f'Constraint[{self.input_synopsis}]'

    def __repr__(self) -> str:
        """Rudimentary repr to avoid default scary to the user Python repr"""
        return f'{self.__class__.__name__}()'

    def raise_for(self, value: Any, msg: str, **ctx: Any) -> None:
        """Convenience method for raising a ``ConstraintError``

        The parameters are identical to those of ``ConstraintError``. This
        method merely passes the ``Constraint`` instance as ``self`` to the
        constructor.
        """
        if ctx:
            raise ConstraintError(self, value, msg, ctx)
        raise ConstraintError(self, value, msg)

    def __and__(self, other: Constraint) -> Constraint:
        return AllOf(self, other)

    def __or__(self, other: Constraint) -> Constraint:
        return AnyOf(self, other)

    @property
    @abstractmethod
    def input_synopsis(self) -> str:
        """Returns brief, single line summary of valid input for a constraint

        This information is user-facing, and to be used in any place where
        space is limited (tooltips, usage summaries, etc).

        If possible, the synopsis should be written in a UI/API-agnostic
        fashion. However, if this is impossible or leads to imprecisions or
        confusion, it should focus on use within Python code and with Python
        data types. Tailored documentation can be provided via the
        ``WithDescription`` wrapper.
        """

    @property
    def input_description(self) -> str:
        """Returns full description of valid input for a constraint

        Like ``input_synopsis`` this information is user-facing. In contrast,
        to the synopsis there is length/line limit. Nevertheless, the
        information should be presented in a compact fashion that avoids
        needless verbosity. If possible, a single paragraph is a good format.
        If multiple paragraphs are necessary, they should be separated by
        a single, empty line.

        Rendering code may indent, or rewrap the text, so no line-by-line
        formatting will be preserved.

        If possible, the synopsis should be written in a UI/API-agnostic
        fashion. However, if this is impossible or leads to imprecisions or
        confusion, it should focus on use within Python code and with Python
        data types. Tailored documentation can be provided via the
        ``WithDescription`` wrapper.
        """
        return self.input_synopsis

    # TODO: also have these for AnyOf and AllOf
    #    def for_dataset(self, dataset: DatasetParameter) -> Constraint:
    #        """Return a constraint-variant for a specific dataset context
    #
    #        The default implementation returns the unmodified, identical
    #        constraint. However, subclasses can implement different behaviors.
    #        """
    #        return self

    @abstractmethod
    def __call__(self, value: Any):
        """ """
        # do any necessary checks or conversions, potentially catch exceptions
        # and generate a meaningful error message


class _MultiConstraint(Constraint):
    """Helper class to override the description methods to reported
    multiple constraints
    """

    def __init__(self, *constraints: Constraint):
        self._constraints = constraints

    def __repr__(self) -> str:
        creprs = ', '.join(f'{c!r}' for c in self.constraints)
        return f'{self.__class__.__name__}({creprs})'

    @property
    def constraints(self) -> tuple[Constraint, ...]:
        return self._constraints

    def _get_description(self, attr: str, operation: str) -> str:
        cs = [getattr(c, attr) for c in self.constraints if hasattr(c, attr)]
        cs = [c for c in cs if c is not None]
        doc = f' {operation} '.join(cs)
        if len(cs) > 1:
            return f'{doc}'
        # dont fiddle with the single item, just take it
        return doc


class AnyOf(_MultiConstraint):
    """Logical OR for constraints.

    An arbitrary number of constraints can be given. They are evaluated in the
    order in which they were specified. The value returned by the first
    constraint that does not raise an exception is the global return value.

    Documentation is aggregated for all alternative constraints.
    """

    def __or__(self, other: Constraint) -> Constraint:
        constraints = list(self.constraints)
        if isinstance(other, AnyOf):
            constraints.extend(other.constraints)
        else:
            constraints.append(other)
        return AnyOf(*constraints)

    def __call__(self, value: Any) -> Any:
        e_list = []
        for c in self.constraints:
            try:
                return c(value)
            except Exception as e:  # noqa: BLE001
                e_list.append(e)
        self.raise_for(  # noqa: RET503
            value,
            # plural OK, no sense in having 1 "alternative"
            'does not match any of {n_alternatives} alternatives\n'
            '{__itemized_causes__}',
            # if any exception would be a ConstraintError
            # this would not be needed, because they
            # know the underlying constraint
            constraints=self.constraints,
            n_alternatives=len(self.constraints),
            __caused_by__=e_list,
        )

    @property
    def input_synopsis(self) -> str:
        return self._get_description('input_synopsis', 'or')

    @property
    def input_description(self) -> str:
        return self._get_description('input_description', 'or')


class AllOf(_MultiConstraint):
    """Logical AND for constraints.

    An arbitrary number of constraints can be given. They are evaluated in the
    order in which they were specified. The return value of each constraint is
    passed an input into the next. The return value of the last constraint
    is the global return value. No intermediate exceptions are caught.

    Documentation is aggregated for all constraints.
    """

    def __and__(self, other: Constraint) -> Constraint:
        constraints = list(self.constraints)
        if isinstance(other, AllOf):
            constraints.extend(other.constraints)
        else:
            constraints.append(other)
        return AllOf(*constraints)

    def __call__(self, value: Any) -> Any:
        for c in self.constraints:
            value = c(value)
        return value

    @property
    def input_synopsis(self) -> str:
        return self._get_description('input_synopsis', 'and')

    @property
    def input_description(self) -> str:
        return self._get_description('input_description', 'and')
