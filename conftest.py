"""Fixture setup"""

__all__ = [
    'cfgman',
    'bareannexrepo',
    'baregitrepo',
    'annexrepo',
    'gitrepo',
    'modified_dataset',
    'skip_when_symlinks_not_supported',
    'symlinks_supported',
    'verify_pristine_gitconfig_global',
]


from datalad_core.tests.fixtures import (
    # function-scope temporary Git repo with an initialized annex
    annexrepo,
    # function-scope temporary, bare Git repo with an initialized annex
    bareannexrepo,
    # function-scope temporary, bare Git repo
    baregitrepo,
    # function-scope config manager
    cfgman,
    # function-scope temporary Git repo
    gitrepo,
    # session-scope repository with complex unsafed modifications
    modified_dataset,
    # function-scope auto-skip when `symlinks_supported` is False
    skip_when_symlinks_not_supported,
    # session-scope flag if symlinks are supported in test directories
    symlinks_supported,
    # verify no test leave contaminated config behind
    verify_pristine_gitconfig_global,
)
