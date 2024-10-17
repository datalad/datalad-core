from __future__ import annotations

from typing import Any

from datalad_core.constraints.constraint import Constraint
from datalad_core.constraints.exceptions import ConstraintError


class WithDescription(Constraint):
    """Constraint that wraps another constraint and replaces its description

    Whenever a constraint's self-description does not fit an application
    context, it can be wrapped with this class. The given synopsis and
    description of valid inputs replaces those of the wrapped constraint.
    """

    def __init__(
        self,
        constraint: Constraint,
        *,
        input_synopsis: str | None = None,
        input_description: str | None = None,
        error_message: str | None = None,
        # input_synopsis_for_ds: str | None = None,
        # input_description_for_ds: str | None = None,
        # error_message_for_ds: str | None = None,
    ):
        """
        ``constraint`` can be any :class:`Constraint` subclass instance, and
        it will be used to perform the actual processing.

        If any of ``input_synopsis`` or ``input_description`` are given, they
        replace the respective property of the wrapped ``constraint``.

        If given, ``error_message`` replaces the error message of a
        :class:`ConstraintError` raised by the wrapped ``Constraint``. Only the
        message (template) is replaced, not the error context dictionary.
        """
        # input_synopsis_for_ds: optional
        #   If either this, or ``input_description_for_ds``, or
        #   ``error_message_for_ds`` are given, the result of tailoring a
        #   constraint for a particular dataset (``for_dataset()``) will
        #   also be wrapped with this custom synopsis.
        # input_description_for_ds: optional
        #   If either this, or ``input_synopsis_for_ds``, or
        #   ``error_message_for_ds`` are given, the result of tailoring a
        #   constraint for a particular dataset (``for_dataset()``) will
        #   also be wrapped with this custom description.
        # error_message: optional
        #   If either this, or ``input_synopsis_for_ds``, or
        #   ``input_description_for_ds`` are given, the result of tailoring a
        #   constraint for a particular dataset (``for_dataset()``) will
        #   also be wrapped with this custom error message (template).
        super().__init__()
        self._constraint = constraint
        self._synopsis = input_synopsis
        self._description = input_description
        self._error_message = error_message
        # self._synopsis_for_ds = input_synopsis_for_ds
        # self._description_for_ds = input_description_for_ds
        # self._error_message_for_ds = error_message_for_ds

    @property
    def constraint(self) -> Constraint:
        """Returns the wrapped constraint instance"""
        return self._constraint

    def __call__(self, value: Any) -> Any:
        try:
            return self._constraint(value)
        except ConstraintError as e:
            # rewrap the error to get access to the top-level
            # self-description.
            msg, cnstr, value, ctx = e.args
            raise ConstraintError(
                self,
                value,
                self._error_message or msg,
                ctx,
            ) from e

    def __repr__(self) -> str:
        return (
            f'{self.__class__.__name__}'
            f'({self._constraint!r}, '
            f'input_synopsis={self._synopsis!r}, '
            f'input_description={self._description!r}, '
            # f'input_synopsis_for_ds={self._synopsis_for_ds!r}, '
            # f'input_description_for_ds={self._description_for_ds!r}, '
            f'error_message={self._error_message!r}'
            # f'error_message_for_ds={self._error_message_for_ds!r})'
            ')'
        )

    # def for_dataset(self, dataset: DatasetParameter) -> Constraint:
    #    """Wrap the wrapped constraint again after tailoring it for the dataset
    #    """
    #    if any(x is not None for x in (
    #            self._synopsis_for_ds,
    #            self._description_for_ds,
    #            self._error_message_for_ds)):
    #        # we also want to wrap the tailored constraint
    #        return self.__class__(
    #            self._constraint.for_dataset(dataset),
    #            input_synopsis=self._synopsis_for_ds,
    #            input_description=self._description_for_ds,
    #            error_message=self._error_message_for_ds,
    #        )
    #    else:
    #        return self._constraint.for_dataset(dataset)

    @property
    def input_synopsis(self) -> str:
        return self._synopsis or self.constraint.input_synopsis

    @property
    def input_description(self) -> str:
        return self._description or self.constraint.input_description
