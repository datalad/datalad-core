from __future__ import annotations

import logging
import re
from abc import abstractmethod
from os import name as os_name
from pathlib import Path
from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from collections.abc import Hashable
    from os import PathLike

    from datasalad.settings import Setting

from datasalad.itertools import (
    decode_bytes,
    itemize,
)
from datasalad.settings import CachingSource

from datalad_core.config.item import ConfigItem
from datalad_core.consts import DATALAD_BRANCH_CONFIG_RELPATH
from datalad_core.runners import (
    CommandError,
    call_git,
    call_git_oneline,
    iter_git_subproc,
)

lgr = logging.getLogger('datalad.config')


class GitConfig(CachingSource):
    """Abstract base class for sources using git-config to read and write

    Derived classes must implement :meth:`GitConfig._get_git_config_cmd`
    and :meth:`GitConfig._get_git_config_cmd` to support the generic
    :meth:`GitConfig._load` implementation that reads configuration
    items from ``git config``.
    """

    # Unfortunately there is no known way to tell git to ignore possible local
    # git repository, and unsetting of --git-dir could cause other problems.
    # See https://lore.kernel.org/git/YscCKuoDPBbs4iPX@lena.dartmouth.edu/T/ .
    # Setting the git directory to /dev/null or on Windows analogous nul file
    # (could be anywhere, see https://stackoverflow.com/a/27773642/1265472) see
    # allow to achieve the goal to prevent a repository in the current working
    # directory from leaking configuration into the output.
    _nul = 'b:\\nul' if os_name == 'nt' else '/dev/null'

    def __str__(self) -> str:
        if not self._sources:
            return self.__class__.__name__
        return (
            f'{self.__class__.__name__}['
            f'{",".join(str(s) for s in self._sources)}'
            ']'
        )

    @abstractmethod
    def _get_git_config_cmd(self) -> list[str]:
        """Return git-config base command for a particular config"""

    @abstractmethod
    def _get_git_config_cwd(self) -> Path | None:
        """Return path the git-config command should run in"""

    def _reinit(self) -> None:
        super()._reinit()
        self._sources: set[str | Path] = set()

    def _load(self) -> None:
        cwd = self._get_git_config_cwd() or Path.cwd()
        dct: dict[str, str | tuple[str, ...]] = {}
        fileset: set[str] = set()

        try:
            with iter_git_subproc(
                [*self._get_git_config_cmd(), '--show-origin', '--list', '-z'],
                inputs=None,
                cwd=cwd,
            ) as gitcfg:
                for line in itemize(
                    decode_bytes(gitcfg),
                    sep='\0',
                    keep_ends=False,
                ):
                    _proc_dump_line(line, fileset, dct)
        except CommandError:
            # TODO: only pass for the case where no corresponding
            # source is found. E.g., it fails with --system whenever
            # there is no /etc/gitconfig
            pass

        # take blobs with verbatim markup
        origin_blobs = {f for f in fileset if f.startswith('blob:')}
        # convert file specifications to Path objects with absolute paths
        origin_paths = {Path(f[5:]) for f in fileset if f.startswith('file:')}
        origin_paths = {f if f.is_absolute() else cwd / f for f in origin_paths}
        # TODO: add "version" tracking. The legacy config manager used mtimes
        # and we might too. but we also need to ensure that the version for
        # the "blobs" is known
        self._sources = origin_paths.union(origin_blobs)

        for k, v in dct.items():
            vals = (v,) if not isinstance(v, tuple) else v
            self.setall(
                k,
                tuple(ConfigItem(val) for val in vals),
            )

    #
    # we have to wrap most accessors to ensure the key normalization imposed
    # by git-config, otherwise we might breed effective duplicates,
    # or mismatches
    #
    def __contains__(self, key: Hashable) -> bool:
        return _normalize_key(key) in self.keys()

    def _get_item(self, key: Hashable) -> Setting:
        return super()._get_item(_normalize_key(key))

    def _getall(self, key: Hashable) -> tuple[Setting, ...]:
        return super()._getall(_normalize_key(key))

    def _del_item(self, key: Hashable):
        return super()._del_item(_normalize_key(key))

    def _setall(self, key: Hashable, values: tuple[Setting, ...]) -> None:
        super()._setall(_normalize_key(key), values)

    def _set_item(self, key: Hashable, value: Setting) -> None:
        key = _normalize_key(key)
        call_git(
            [*self._get_git_config_cmd(), '--replace-all', str(key), str(value.value)],
            capture_output=True,
        )
        super()._set_item(key, value)

    def _add(self, key: Hashable, value: Setting) -> None:
        key = _normalize_key(key)
        call_git(
            [*self._get_git_config_cmd(), '--add', str(key), str(value.value)],
            capture_output=True,
        )
        super()._add(key, value)


class SystemGitConfig(GitConfig):
    """Source for Git's ``system`` configuration scope"""

    def _get_git_config_cmd(self) -> list[str]:
        return [f'--git-dir={self._nul}', 'config', '--system']

    def _get_git_config_cwd(self) -> Path | None:
        return Path.cwd()


class GlobalGitConfig(GitConfig):
    """Source for Git's ``global`` configuration scope"""

    def _get_git_config_cmd(self) -> list[str]:
        return [f'--git-dir={self._nul}', 'config', '--global']

    def _get_git_config_cwd(self) -> Path | None:
        return Path.cwd()


class LocalGitConfig(GitConfig):
    """Source for Git's ``local`` configuration scope"""

    def __init__(self, path: PathLike):
        super().__init__()
        # this is the path where the repository (checkout/worktree)
        # is located. this may be identical to self._gitdir
        # that is determined below (bare repo)
        self._path = Path(path)

        try:
            self._in_worktree = (
                call_git_oneline(
                    ['rev-parse', '--is-inside-work-tree'],
                    cwd=self._path,
                    force_c_locale=True,
                )
                == 'true'
            )
        except CommandError as e:
            from os import environ

            msg = f"no Git repository at {path}: {e!r} {environ.get('GIT_DIR')}"
            raise ValueError(msg) from e

        self._gitdir = Path(
            path
            if not self._in_worktree
            else call_git_oneline(
                ['rev-parse', '--path-format=absolute', '--git-dir'],
                cwd=self._path,
                force_c_locale=True,
            )
        )

    def _get_git_config_cmd(self) -> list[str]:
        return ['--git-dir', str(self._gitdir), 'config', '--local']

    def _get_git_config_cwd(self) -> Path | None:
        # we set --git-dir, CWD does not matter
        return None


class WorktreeGitConfig(GitConfig):
    """Source for Git's ``worktree`` configuration scope

    This class requires that the configuration ``extensions.worktreeConfig``
    is enabled.
    """

    def __init__(self, path: PathLike):
        super().__init__()
        # this is the path where the checkout/worktree is located
        self._path = Path(path)

        self._gitdir = Path(
            call_git_oneline(
                ['rev-parse', '--path-format=absolute', '--git-dir'],
                cwd=self._path,
                force_c_locale=True,
            )
        )

    def _get_git_config_cmd(self) -> list[str]:
        return ['--git-dir', str(self._gitdir), 'config', '--worktree']

    def _get_git_config_cwd(self) -> Path | None:
        # we set --git-dir, CWD does not matter
        return None


class DataladBranchConfig(LocalGitConfig):
    """Source for configuration committed to a branch's ``.datalad/config``"""

    def __init__(self, path: PathLike):
        super().__init__(path)

    @property
    def is_writable(self):
        return self._in_worktree

    def _get_git_config_cmd(self) -> list[str]:
        return [
            '--git-dir',
            str(self._gitdir),
            'config',
            *(
                ('--file', str(self._path / DATALAD_BRANCH_CONFIG_RELPATH))
                if self._in_worktree
                else ('--blob', f'HEAD:{DATALAD_BRANCH_CONFIG_RELPATH}')
            ),
        ]

    def _ensure_target_dir(self):
        cmd = self._get_git_config_cmd()
        # disable coverage error below. Under normal circumstances this cannot
        # be reached, because `is_writable` would say False and disable
        # all setters
        if '--file' not in cmd:  # pragma: no cover
            return
        custom_file = Path(cmd[cmd.index('--file') + 1])
        custom_file.parent.mkdir(exist_ok=True)

    def _set_item(self, key: Hashable, value: Setting) -> None:
        self._ensure_target_dir()
        super()._set_item(key, value)

    def _add(self, key: Hashable, value: Setting) -> None:
        self._ensure_target_dir()
        super()._add(key, value)


def _proc_dump_line(
    line: str,
    fileset: set[str],
    dct: dict[str, str | tuple[str, ...]],
) -> None:
    # line is a null-delimited chunk
    k = None
    # in anticipation of output contamination, process within a loop
    # where we can reject non syntax compliant pieces
    # we disable the coverage error for this while loop. It is in fact
    # tested. Likely caused by something like
    # https://github.com/nedbat/coveragepy/issues/772
    while line:  # pragma: no cover
        if line.startswith(('file:', 'blob:')):
            fileset.add(line)
            break
        if line.startswith('command line:'):
            # no origin that we could as a pathobj
            break
        # try getting key/value pair from the present chunk
        k, v = _gitcfg_rec_to_keyvalue(line)
        if k is not None:
            # we are done with this chunk when there is a good key
            break
        # discard the first line and start over
        ignore, line = line.split('\n', maxsplit=1)
        lgr.debug('Non-standard git-config output, ignoring: %s', ignore)
    if not k:
        # nothing else to log, all ignored dump was reported before
        return
    if TYPE_CHECKING:
        assert k is not None
    if v is None:
        # man git-config:
        # just name, which is a short-hand to say that the variable is
        # the boolean
        v = 'true'
    # multi-value reporting
    present_v = dct.get(k)
    if present_v is None:
        dct[k] = v
    elif isinstance(present_v, tuple):
        dct[k] = (*present_v, v)
    else:
        dct[k] = (present_v, v)


# git-config key syntax with a section and a subsection
# see git-config(1) for syntax details
cfg_k_regex = re.compile(r'([a-zA-Z0-9-.]+\.[^\0\n]+)$', flags=re.MULTILINE)
# identical to the key regex, but with an additional group for a
# value in a null-delimited git-config dump
cfg_kv_regex = re.compile(
    r'([a-zA-Z0-9-.]+\.[^\0\n]+)\n(.*)$', flags=re.MULTILINE | re.DOTALL
)


def _gitcfg_rec_to_keyvalue(rec: str) -> tuple[str | None, str | None]:
    """Helper for parse_gitconfig_dump()

    Parameters
    ----------
    rec: str
      Key/value specification string

    Returns
    -------
    str, str
      Parsed key and value. Key and/or value could be None
      if not syntax-compliant (former) or absent (latter).
    """
    kv_match = cfg_kv_regex.match(rec)
    if kv_match:
        k, v = kv_match.groups()
    elif cfg_k_regex.match(rec):
        # could be just a key without = value, which git treats as True
        # if asked for a bool
        k, v = rec, None
    else:
        # no value, no good key
        k = v = None
    return k, v


def _normalize_key(key: Hashable) -> str:
    key_l = str(key).split('.')
    section = key_l[0]
    name = key_l[-1]
    # length of the component list when we have no subsection(s)
    no_sub_len = 2
    # section name and variable name are case-insensitive, the subsection(s)
    # not
    # TODO: probably a good idea to also implement the rest of the
    # rules, such that writing to the CachingSource actually yields the
    # same content as that written to Git config effectively
    return (
        f"{section.lower()}."
        f"{'.'.join(key_l[1:-1])}{'.' if len(key_l) > no_sub_len else ''}"
        f"{name.lower()}"
    )
