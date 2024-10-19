from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from datalad_core.constraints.constraint import Constraint


class NoConstraint(Constraint):
    """A constraint that represents no constraints"""

    @property
    def input_synopsis(self):
        return ''

    def __call__(self, value):
        return value


class EnsureMappingtHasKeys(Constraint):
    """Ensure a mapping has all given keys"""

    def __init__(self, required_keys: tuple | list):
        self._required_keys = required_keys

    @property
    def input_synopsis(self):
        return (
            'mapping with required keys {self._required_keys!r}'
            if self._required_keys
            else 'mapping'
        )

    def __call__(self, value: Any) -> dict:
        if not isinstance(value, Mapping):
            self.raise_for(
                value,
                'not a mapping',
            )
        missing = tuple(a for a in self._required_keys if a not in value)
        if missing:
            self.raise_for(
                value,
                'missing keys {missing!r}',
                missing=missing,
            )
        return value
