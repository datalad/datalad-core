from __future__ import annotations

import contextlib
from pathlib import (
    Path,
    PurePath,
)
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
)

if TYPE_CHECKING:
    from datalad_core.commands import Dataset

from datalad_core.constraints.constraint import Constraint
from datalad_core.consts import UnsetValue
from datalad_core.repo import Worktree


class EnsurePath(Constraint):
    """Convert input to a (platform) path and ensures select properties

    Optionally, the path can be tested for existence and whether it is absolute
    or relative.
    """

    def __init__(
        self,
        *,
        path_type: type = Path,
        is_format: str | None = None,
        lexists: bool | None = None,
        is_mode: Callable | None = None,
        ref: Path | None = None,
        ref_is: str = 'parent-or-same-as',
    ) -> None:
        """
        Parameters
        ----------
        path_type:
          Specific pathlib type to convert the input to. The default is `Path`,
          i.e. the platform's path type. Not all pathlib Path types can be
          instantiated on all platforms, and not all checks are possible with
          all path types.
        is_format: {'absolute', 'relative'} or None
          If not None, the path is tested whether it matches being relative or
          absolute.
        lexists:
          If not None, the path is tested to confirmed exists or not. A symlink
          need not point to an existing path to fulfil the "exists" condition.
        is_mode:
          If set, this callable will receive the path's `.lstat().st_mode`,
          and an exception is raised, if the return value does not evaluate
          to `True`. Typical callables for this feature are provided by the
          `stat` module, e.g. `S_ISDIR()`
        ref:
          If set, defines a reference Path any given path is compared to. The
          comparison operation is given by `ref_is`.
        ref_is: {'parent-or-same-as', 'parent-of'}
          Comparison operation to perform when `ref` is given.
        """
        super().__init__()
        self._path_type = path_type
        self._is_format = is_format
        self._lexists = lexists
        self._is_mode = is_mode
        self._ref = ref
        self._ref_is = ref_is
        if self._ref_is not in ('parent-or-same-as', 'parent-of'):
            msg = f'unrecognized `ref_is` operation label: {self._ref_is}'
            raise ValueError(msg)

    def __call__(self, value: Any) -> PurePath | Path:
        # turn it into the target type to make everything below
        # more straightforward
        path = get_path_instance(self, value)

        # we are testing the format first, because resolve_path()
        # will always turn things into absolute paths
        if self._is_format is not None:
            is_abs = path.is_absolute()
            if self._is_format == 'absolute' and not is_abs:
                self.raise_for(path, 'is not an absolute path')
            elif self._is_format == 'relative' and is_abs:
                self.raise_for(path, 'is not a relative path')

        mode = None
        if self._lexists is not None or self._is_mode is not None:
            with contextlib.suppress(FileNotFoundError):
                # error would be OK, handled below
                mode = path.lstat().st_mode if hasattr(path, 'lstat') else UnsetValue
        if self._lexists is not None:
            if self._lexists and mode is None:
                self.raise_for(path, 'does not exist')
            elif not self._lexists and mode is not None:
                self.raise_for(path, 'does (already) exist')
        if self._is_mode is not None:
            if mode is UnsetValue:
                self.raise_for(path, 'cannot check mode, PurePath given')
            elif not self._is_mode(mode):
                self.raise_for(path, 'does not match desired mode')
        if self._ref:
            ok = True
            if self._ref_is == 'parent-or-same-as':
                ok = path == self._ref or self._ref in path.parents
            elif self._ref_is == 'parent-of':
                ok = self._ref in path.parents
            else:  # pragma: no cover
                # this code cannot be reached with normal usage.
                # it is prevented by an assertion in __init__()
                msg = f'unknown `ref_is` operation label {self._ref_is!r}'
                raise RuntimeError(msg)

            if not ok:
                self.raise_for(
                    path,
                    '{ref} is not {ref_is} {path}',
                    ref=self._ref,
                    ref_is=self._ref_is,
                )
        return path

    @property
    def input_synopsis(self):
        return '{}{}path{}'.format(
            'existing ' if self._lexists else 'non-existing ' if self._lexists else '',
            'absolute '
            if self._is_format == 'absolute'
            else 'relative'
            if self._is_format == 'relative'
            else '',
            f' that is {self._ref_is} {self._ref}' if self._ref else '',
        )

    def for_dataset(self, dataset: Dataset) -> Constraint:
        """Return an identically parametrized variant that resolves
        paths against a given dataset.
        """
        return EnsureDatasetPath(self, dataset)


class EnsureDatasetPath(Constraint):
    def __init__(
        self,
        path_constraint: EnsurePath,
        dataset: Dataset,
    ):
        """Resolves a path in the context of a particular dataset

        This constraint behaves exactly like the :class:`EnsurePath`
        constraint it is parameterized with, except for two conditions:

        1. When called with ``None``, it will process the path associated
           with the :class:`Dataset` instance given to the ``dataset``
           parameter.
        2. When called with a relative path and the :class:`Dataset`
           was created from a :class:`Worktree` instance, the relative
           path will be considered relative to the worktree root.

        Otherwise, all given paths are interpreted as-is, or relative to
        the current working directory (CWD).
        """
        self._path_constraint = path_constraint
        self._dataset = dataset

    def __call__(self, value: Any) -> PurePath | Path:
        # only if the Dataset instance was created from a Worktree
        # instance we deviate from EnsurePath()
        if value is not None and not isinstance(self._dataset.pristine_spec, Worktree):
            return self._path_constraint(value)

        path = (
            self._dataset.path
            if value is None
            else get_path_instance(self._path_constraint, value)
        )
        # when dataset is based on a Worktree instance and we received
        # a relative path, only then interpret the path as relative
        # to the worktree. Always relative to CWD otherwise.
        if not path.is_absolute():
            path = self._dataset.path / path
        return self._path_constraint(path)

    @property
    def input_synopsis(self):
        return self._path_constraint.input_synopsis


def get_path_instance(
    origin_constraint: EnsurePath,
    value: Any,
) -> PurePath | Path:
    try:
        path = origin_constraint._path_type(value)  # noqa: SLF001
    except (ValueError, TypeError) as e:
        origin_constraint.raise_for(
            value,
            str(e),
        )
    return path
