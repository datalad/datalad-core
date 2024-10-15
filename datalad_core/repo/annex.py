from __future__ import annotations

from pathlib import Path

from datalad_core.runners import (
    CommandError,
    call_annex_json_lines,
    call_git_lines,
)


class AnnexBase:
    """Base class for annex handler

    This class should not be used directyly, but any of its subclasses.

    Methods of this class implement operations that work with annexes
    in bare and non-bare repositories.
    """

    def __init__(self, path: Path):
        self._path = path
        self._uuid: str | None = None

    @property
    def path(self) -> Path:
        """Path used by git-annex commands as PWD"""
        return self._path

    # not using a cached_property, because it would not prevent write-access
    @property
    def uuid(self) -> str:
        """UUID identifier of the local ("here") annex

        Once accessed, the value is cached for the lifetime of the instance.
        """

        if self._uuid is None:
            for ax in self.list_annexes():
                if ax['here'] is True:
                    self._uuid = str(ax['uuid'])
                    return self._uuid
            if self._uuid is None:  # pragma: no cover
                msg = 'annex unexpectedly has no UUID'
                raise RuntimeError(msg)
        return self._uuid

    def list_annexes(self) -> list[dict[str, str | bool]]:
        """Returns a list with information on known annexed for a repository

        Each item in the list corresponds to an annex and is a dictionary
        with annex properties. Dictionary ``str`` keys are

        - ``uuid``: annex UUID identifier
        - ``description``: a custom or generated description of that annex
        - ``here``: a boolean flag whether that annex is local to this
          repository
        - ``trust``: a label (``trusted``, ``semitrusted``, ``untrusted``)
          indication the trust assignment for that annex
        """
        res = list(call_annex_json_lines(['info', '--fast'], cwd=self.path))
        if len(res) != 1:  # pragma: no cover
            msg = 'unexpected output from git-annex-info'
            raise RuntimeError(msg)
        info = res[0]
        annexes: list[dict[str, str | bool]] = []
        for rt in (
            'untrusted repositories',
            'semitrusted repositories',
            'trusted repositories',
        ):
            for r in info[rt]:
                # TODO: make ENUM?
                r.update(trust=rt.split(' ')[0])
                annexes.append(r)
        return annexes


class BareRepoAnnex(AnnexBase):
    # ATTN: This class should not get (many) additional methods. Instead, they
    # should all go into AnnexBase, if they can work with bare and non-bare
    # repositories. The purpose of this class is mainly to enforce use with a
    # bare repository in its __init__()
    """Interface for an annex in a bare Git repository

    Annex operations are executed in the context of a Git repository.
    This repository must be a bare repository. An exception is raised,
    if this class is used with a non-bare repository.
    """

    def __init__(self, path: Path):
        """
        The given ``path`` must point to a bare Git repository and is used
        to resolve and confirm the presence of an annex.
        """
        bare, annex_loc = call_git_lines(
            [
                '-C',
                str(path),
                'rev-parse',
                '--path-format=absolute',
                '--is-bare-repository',
                '--git-path',
                'annex',
            ],
        )
        if bare != 'true':
            msg = f'not a bare repository at {path}'
            raise ValueError(msg)
        # this simple test is also what is done in legacy AnnexRepo
        annex_path = Path(annex_loc)
        if not annex_path.exists():
            msg = f'no repository annex found at {annex_path}'
            raise ValueError(msg)
        super().__init__(annex_path.parent)


class Annex(AnnexBase):
    """Interface for an annex in a non-bare Git repository

    Annex operations are executed in the context of a Git worktree.
    """

    def __init__(self, path: Path):
        """
        The given ``path`` must point to a Git repository worktree
        and is used to resolve and confirm the presence of an annex.
        """
        try:
            annex_loc, worktree_loc = call_git_lines(
                [
                    '-C',
                    str(path),
                    'rev-parse',
                    '--path-format=absolute',
                    '--git-path',
                    'annex',
                    '--show-toplevel',
                ],
            )
        except CommandError as e:
            msg = f'cannot resolve paths for a worktree with an annex at {path}'
            raise ValueError(msg) from e
        # this simple test is also what is done in legacy AnnexRepo
        annex_path = Path(annex_loc)
        if not annex_path.exists():
            msg = f'no repository annex found at {annex_path}'
            raise ValueError(msg)
        super().__init__(Path(worktree_loc))
