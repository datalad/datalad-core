from pathlib import PurePosixPath

import pytest

from datalad_core.repo.tree_item import GitTreeItem
from datalad_core.repo.worktree_item import (
    WorktreeDirectory,
    WorktreeItem,
)
from datalad_core.runners import call_git_oneline
from datalad_core.tests import call_git_addcommit


def test_worktreeitem_noworktree(tmp_path):
    with pytest.raises(ValueError, match='not point to an existing Git'):
        WorktreeDirectory.from_path(tmp_path)


def test_worktreeitem(gitrepo):
    # we add a new file and test its expected properties
    probe_content = 'probe'
    probe_relpath = PurePosixPath('probe.txt')
    subdir_relpath = PurePosixPath('subdir')
    expected_probe_sha = '24ae15ce9741d53115a9fc71c2b761790ca47995'
    probe = gitrepo / subdir_relpath / probe_relpath
    probe.parent.mkdir()
    probe.write_text(probe_content)
    call_git_addcommit(gitrepo)

    for item in (
        # just based on a revision
        WorktreeItem(
            basedir=WorktreeDirectory.from_path(gitrepo),
            relpath=PurePosixPath(probe.relative_to(gitrepo)),
        ),
        # based on a subdir
        WorktreeItem(
            basedir=WorktreeDirectory.from_path(gitrepo / subdir_relpath),
            relpath=probe_relpath,
        ),
        # subtree with optional props
        WorktreeItem(
            basedir=WorktreeDirectory.from_path(gitrepo / subdir_relpath),
            relpath=probe_relpath,
            gitsha=expected_probe_sha,
            gittype=GitTreeItem.mode2type('100644'),
        ),
        #
    ):
        assert item.path.read_text() == probe_content
        if not item.gitsha:
            assert item.gitsha is None
            assert item.gittype is None
            continue

        assert expected_probe_sha in call_git_oneline(
            ['ls-files', '--stage', item.path],
            cwd=item.basedir.worktree.path,
        )
