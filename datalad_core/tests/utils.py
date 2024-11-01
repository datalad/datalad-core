from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import (
        Path,
        PurePath,
    )

from shutil import rmtree as shutil_rmtree

from datalad_core.repo import Worktree
from datalad_core.runners import (
    call_git,
)


def call_git_addcommit(
    cwd: Path,
    paths: list[str | PurePath] | None = None,
    *,
    msg: str | None = None,
):
    if paths is None:
        paths = ['.']

    if msg is None:
        msg = 'done by call_git_addcommit()'

    call_git(['add'] + [str(p) for p in paths], cwd=cwd, capture_output=True)
    call_git(['commit', '-m', msg], cwd=cwd, capture_output=True)


# Target `git status -uall --porcelain=v1` of `modify_dataset()` result
modify_dataset_promise = """\
 D dir_d/file_d
A  dir_m/file_a
 D dir_m/file_d
 M dir_m/file_m
 D dir_sm/sm_d
 M dir_sm/sm_m
 M dir_sm/sm_mu
 M dir_sm/sm_n
 M dir_sm/sm_nm
 M dir_sm/sm_nmu
 M dir_sm/sm_u
A  file_a
AM file_am
 D file_d
 M file_m
?? dir_m/dir_u/file_u
?? dir_m/file_u
?? dir_u/file_u
?? file_u
"""


def modify_dataset(path: Path) -> str:
    """Applies the modification for the ``modified_dataset`` fixture

    ``path`` is a directory in an existing Git repository.

    This is provided as a separate function for the case where the
    modification themselves need to be modified. The fixture checks
    that this does not happen.

    The function returns the ``git status -uall --porcelain=v1``
    report that it aimed to create. This is not a status report
    queried after this function ran, but a "promise" that can be used
    to inspect the state of a repository.
    """
    ds_dir = path / 'dir_m'
    ds_dir_d = path / 'dir_d'
    dirsm = path / 'dir_sm'
    for d in (ds_dir, ds_dir_d, dirsm):
        d.mkdir()
    (ds_dir / 'file_m').touch()
    (path / 'file_m').touch()
    dss: dict[str, Path] = {}
    smnames = (
        'sm_d',
        'sm_c',
        'sm_n',
        'sm_m',
        'sm_nm',
        'sm_u',
        'sm_mu',
        'sm_nmu',
        'droppedsm_c',
    )
    for smname in smnames:
        sds_path = dirsm / smname
        sds_path.mkdir()
        sds = Worktree.init_at(sds_path)
        # we need some content for a commit
        (sds_path / '.gitkeep').touch()
        # for the plain modification, commit the reference right here
        if smname in ('sm_m', 'sm_nm', 'sm_mu', 'sm_nmu'):
            (sds_path / 'file_m').touch()
        call_git_addcommit(sds_path)
        dss[smname] = sds.path
        call_git(
            ['submodule', 'add', f'./{sds_path}', f'{sds_path.relative_to(path)}'],
            cwd=path,
            capture_output=True,
        )
    # files in superdataset to be deleted
    for d in (ds_dir_d, ds_dir, path):
        (d / 'file_d').touch()
    dss['.'] = path
    dss['dir'] = ds_dir
    call_git_addcommit(path)
    call_git(
        ['submodule', 'deinit', '--force', str(dirsm / 'droppedsm_c')],
        cwd=path,
        capture_output=True,
    )
    # a new commit
    for smname in ('.', 'sm_n', 'sm_nm', 'sm_nmu'):
        sub = dss[smname]
        (sub / 'file_c').touch()
        call_git_addcommit(sub)
    # modified file
    for smname in ('.', 'dir', 'sm_m', 'sm_nm', 'sm_mu', 'sm_nmu'):
        pobj = dss[smname]
        (pobj / 'file_m').write_text('modify!')
    # untracked
    for smname in ('.', 'dir', 'sm_u', 'sm_mu', 'sm_nmu'):
        pobj = dss[smname]
        (pobj / 'file_u').touch()
        (pobj / 'dirempty_u').mkdir()
        (pobj / 'dir_u').mkdir()
        (pobj / 'dir_u' / 'file_u').touch()
    # delete items
    rmtree(dss['sm_d'])
    rmtree(ds_dir_d)
    (ds_dir / 'file_d').unlink()
    (path / 'file_d').unlink()
    # added items
    for smname in ('.', 'dir', 'sm_m', 'sm_nm', 'sm_mu', 'sm_nmu'):
        pobj = dss[smname]
        (pobj / 'file_a').write_text('added')
        call_git(['add', 'file_a'], cwd=pobj, capture_output=True)
    # added and then modified file
    file_am_obj = path / 'file_am'
    file_am_obj.write_text('added')
    call_git(['add', 'file_am'], cwd=path, capture_output=True)
    file_am_obj.write_text('modified')

    return modify_dataset_promise


def _rmtree_onerror(func, path, exc_info):  # noqa: ARG001
    """
    Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.

    If the error is for another reason it re-raises the error.
    """
    import stat

    # Is the error an access error?
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise


def rmtree(path: Path) -> None:
    """``shutil.rmtree()`` with an error handler that sets write permissions"""
    shutil_rmtree(
        path,
        # deprecated with PY3.12 -> onexc=
        onerror=_rmtree_onerror,
    )
