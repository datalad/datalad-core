""" """

from pathlib import Path

from datalad_core.repo.flyweight import (
    Flyweighted,
    PathBasedFlyweight,
)
from datalad_core.runners import (
    call_git_lines,
    call_git_success,
)


class GitManaged(Flyweighted, metaclass=PathBasedFlyweight):
    """Base class for more specialized Git-managed entities

    This class is primarily a technical helper for hosting common
    implementations.
    """

    def __init__(self, path: Path):
        self.reset()
        self._path = path.absolute()

    def reset(self) -> None:
        """Reset instance, drop all cached properties"""
        self._git_dir = None
        self._git_common_dir = None

    def __str__(self):
        return f'{self.__class__.__name__}({self._path})'

    def __repr__(self):
        return f'{self.__class__.__name__}({self._path!r})'

    def flyweight_valid(self):
        """Test continued validity is an instance

        The test is performed by running ``git rev-parse --git-dir``, which
        would fail if the location is not (or no longer) managed by Git.

        If the instance is found to be invalid the :meth:`reset` method
        will be called.
        """
        # the ideas being that as long as Git itself can report a GITDIR, we
        # can assume to continue to be in a location managed by Git.
        # Derived classes may want to override this implementation with
        # something more specific (e.g., worktree did not move, etc)
        try:
            valid = call_git_success(
                ['rev-parse', '--git-dir'],
                cwd=self.path,
                capture_output=True,
            )
        except (FileNotFoundError, NotADirectoryError):
            valid = False

        if valid is True:
            return True

        # this instance is no longer valid.
        # loose all references to linked objects/properties, these
        # might also be invalid and could be garbage collected.
        self.reset()
        return False

    @property
    def path(self) -> Path:
        """Absolute path of the Git-managed location"""
        # this is a property wrapper, because we may want to introduce
        # some invalidation tests at some point
        return self._path

    @property
    def git_dir(self):
        """Path to the associated ``.git`` directory"""
        if self._git_dir is None:
            self._get_git_props()
        return self._git_dir

    @property
    def git_common_dir(self):
        """Path to the associated common ``.git`` directory

        This will be identical to :attr:`git_dir`, except for a linked
        worktree with enabled ``extensions.worktreeConfig`` flag.
        """
        if self._git_common_dir is None:
            self._get_git_props()
        return self._git_common_dir

    def _get_git_props(self):
        # pull a set of properties at once, assuming that one call is cheaper
        # than multiple
        prop_specs = (
            ('--git-dir', '_git_dir', Path),
            ('--git-common-dir', '_git_common_dir', Path),
        )
        for spec, val in zip(
            prop_specs,
            call_git_lines(
                [
                    '-C',
                    str(self._path),
                    'rev-parse',
                    '--path-format=absolute',
                    *(p[0] for p in prop_specs),
                ]
            ),
            strict=False,
        ):
            setattr(self, spec[1], spec[2](val))
