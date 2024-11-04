from pathlib import (
    PurePosixPath,
)

import pytest

from datalad_core.consts import PRE_INIT_COMMIT_SHA
from datalad_core.runners import CommandError
from datalad_core.tests import (
    call_git_addcommit,
)

from ..gittree import (
    GitTreeItem,
    GitTreeItemType,
    iter_gittree,
)


def test_iter_gittree(gitrepo):
    # an initial commit
    (gitrepo / '.gitkeep').touch()
    call_git_addcommit(gitrepo)

    # we add a new file and test its expected properties
    probe_name = 'probe.txt'
    # on crippled FS we are testing the managed branch which contains
    # pointer files, not symlinks
    expected_probe_sha = '24ae15ce9741d53115a9fc71c2b761790ca47995'
    probe = gitrepo / 'subdir' / probe_name
    probe.parent.mkdir()
    probe.write_text('probe')
    call_git_addcommit(gitrepo)

    tracked_items = list(iter_gittree(gitrepo, 'HEAD'))
    # without untracked's and no link resolution this is plain and fast
    assert all(
        isinstance(i, GitTreeItem) and i.gitsha and i.gittype for i in tracked_items
    )
    assert any(
        # let's query a Path instance here, to get that covered too
        i.relpath == PurePosixPath(f'subdir/{probe_name}')
        and i.gitsha == expected_probe_sha
        and i.gittype == GitTreeItemType.file
        for i in iter_gittree(gitrepo, 'HEAD')
    )
    # if we check the prior version, we do not see it (hence the
    # tree-ish passing is working
    assert not any(
        i.relpath == PurePosixPath(f'subdir/{probe_name}')
        for i in iter_gittree(gitrepo, 'HEAD~1')
    )

    # if we disable recursion, the probe is not listed, but its
    # parent dir is
    tracked_toplevel_items = list(iter_gittree(gitrepo, 'HEAD', recursion='none'))
    assert not any(i.relpath == f'subdir/{probe_name}' for i in tracked_toplevel_items)
    assert any(
        i.relpath == PurePosixPath('subdir')
        and i.gitsha == '0dd69202ba4657a5d9c37d5716d5b27127c4b57b'
        and i.gittype == GitTreeItemType.directory
        for i in tracked_toplevel_items
    )
    # iterating on a subdir does constrain the report
    tracked_subdir_items = list(iter_gittree(probe.parent, 'HEAD'))
    assert len(tracked_subdir_items) == 1
    probe_item = tracked_subdir_items[0]
    assert probe_item.relpath.name == probe_name
    assert probe_item.gitsha == expected_probe_sha


def test_name_starting_with_tab(gitrepo):
    tabbed_file_name = '\ttab.txt'
    tabbed_file = gitrepo / tabbed_file_name
    try:
        tabbed_file.write_text('name of this file starts with a tab')
    except OSError:
        pytest.skip('not applicable on crippled filesystems')

    call_git_addcommit(gitrepo)
    iter_names = [item.relpath for item in iter_gittree(gitrepo, 'HEAD')]
    assert PurePosixPath(tabbed_file_name) in iter_names


def test_iter_gittree_empty(gitrepo):
    with pytest.raises(CommandError, match='Not a valid object name HEAD'):
        list(iter_gittree(gitrepo, 'HEAD'))

    all_items = list(iter_gittree(gitrepo, PRE_INIT_COMMIT_SHA))
    assert len(all_items) == 0
