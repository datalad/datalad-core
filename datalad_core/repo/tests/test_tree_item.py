from pathlib import PurePosixPath

from datalad_core.repo.repo import Repo
from datalad_core.repo.tree_item import (
    GitTreeItem,
    Treeish,
)
from datalad_core.runners import call_git_oneline
from datalad_core.tests import call_git_addcommit


def test_gittreeitem(gitrepo):
    # we add a new file and test its expected properties
    probe_content = 'probe'
    probe_relpath = PurePosixPath('probe.txt')
    expected_probe_sha = '24ae15ce9741d53115a9fc71c2b761790ca47995'
    probe = gitrepo / 'subdir' / probe_relpath
    probe.parent.mkdir()
    probe.write_text(probe_content)
    call_git_addcommit(gitrepo)

    repo = Repo(gitrepo / '.git')
    for item in (
        # just based on a revision
        GitTreeItem(
            tree=Treeish(repo, 'HEAD'),
            relpath=PurePosixPath(probe.relative_to(gitrepo)),
        ),
        # based on a subtree
        GitTreeItem(
            tree=Treeish(repo, 'HEAD:subdir'),
            relpath=probe_relpath,
        ),
        # subtree with optional props
        GitTreeItem(
            tree=Treeish(repo, 'HEAD:subdir'),
            relpath=probe_relpath,
            gitsha=expected_probe_sha,
            gittype=GitTreeItem.mode2type('100644'),
        ),
        #
    ):
        assert (
            call_git_oneline(
                ['cat-file', '-p', item.object_id],
                cwd=item.tree.repo.path,
            )
            == probe_content
        )
        if not item.gitsha:
            assert item.gitsha is None
            assert item.gittype is None
            continue

        assert (
            call_git_oneline(
                ['rev-parse', item.object_id],
                cwd=item.tree.repo.path,
            )
            == expected_probe_sha
        )
