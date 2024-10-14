from datalad_core.config import ConfigItem
from datalad_core.runners import call_git

from ..worktree import Worktree


def test_worktree(gitrepo):
    wt = Worktree(gitrepo)
    assert str(wt) == f'Worktree({gitrepo})'
    assert repr(wt) == f'Worktree({gitrepo!r})'
    assert str(gitrepo / '.git' / 'config') in str(wt.config)
    assert str(gitrepo / '.git' / 'config') in repr(wt.config)
    # sources without content are not reported
    assert 'DataladBranchConfig' not in str(wt.config)
    # only in repr()
    assert 'DataladBranchConfig' in repr(wt.config)

    # main worktree shares config manager with repo
    assert wt.config is wt.repo.config
    assert wt.config['core.bare'].value is False
    assert wt.path is gitrepo
    assert wt.repo.path != wt.path


def test_secondary_worktree(gitrepo):
    test_key = 'brand.new.key'
    test_key2 = 'other.brand.new.key'
    branch = 'dummy'
    wt_path = gitrepo.parent / branch
    call_git(
        [
            '-C',
            str(gitrepo),
            'worktree',
            'add',
            str(wt_path),
        ]
    )
    wt1 = Worktree(gitrepo)
    wt2 = Worktree(wt_path)
    # and the repo is represented by the very same instance
    assert wt1.repo is wt2.repo
    assert wt1.config is wt2.config is wt1.repo.config

    # now enable a dedicated worktree config
    wt1.config.sources['git-local'][
        # we use snake casing here. the section/variable
        # name is case-insensitive, and it must not matter
        'extensions.worktreeConfig'
    ] = ConfigItem('true')
    wt1.enable_worktree_config()
    # we have to enable it for all linked worktrees manually.
    # the alternative would be a complex search/tracking of
    # related worktree instances, or a continuous on-access
    # reevalutation. Both are not worth the trouble, given that
    # such setup changes are presumbably rare
    wt2.enable_worktree_config()
    # and run it again, just to see that it does no harm
    wt2.enable_worktree_config()
    # and the repo is represented by the very same instance
    assert wt1.repo is wt2.repo
    # but the worktree config is no longer the same
    assert wt1.config is not wt2.config
    # setting the same key with different value in both worktrees
    wt1.config.sources['git-worktree'][test_key] = ConfigItem('wt1')
    wt2.config.sources['git-worktree'][test_key] = ConfigItem('wt2')
    assert wt1.config[test_key].value == 'wt1'
    assert wt2.config[test_key].value == 'wt2'
    # wt2's worktree scope is not "chained" after wt1, there is just
    # the one setting we found above
    assert len(wt2.config.getall(test_key)) == 1
    wt2.config.sources['git-worktree'].reinit().load()
    assert len(wt2.config.getall(test_key)) == 1
    # only set through the main worktree, but into the shared local scope
    assert test_key2 not in wt1.config
    assert test_key2 not in wt2.config
    wt1.config.sources['git-local'][test_key2] = ConfigItem('shared')
    assert test_key2 in wt1.config
    assert test_key2 in wt2.config

    # check that we can use Repo/Worktree objects as dict keys
    # (e.g. to group some results by repo/worktree)
    rwd = {
        wt1: 'wt1',
        wt2: 'wt2',
        wt1.repo: 'repo',
    }
    assert rwd[wt1] == 'wt1'
    assert rwd[wt2] == 'wt2'
    assert rwd[wt1.repo] == 'repo'
