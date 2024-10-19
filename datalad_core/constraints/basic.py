from __future__ import annotations

from datalad_core.constraints.constraint import Constraint


class NoConstraint(Constraint):
    """A constraint that represents no constraints"""

    @property
    def input_synopsis(self):
        return ''

    def __call__(self, value):
        return value
