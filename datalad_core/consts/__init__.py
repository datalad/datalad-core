"""Assorted common constants"""

__all__ = [
    'UnsetValue',
    'DATALAD_DOTDIR_RELPATH',
    'DATALAD_BRANCH_CONFIG_RELPATH',
    'PRE_INIT_COMMIT_SHA',
]

from os.path import join as opj

from datasalad.settings import UnsetValue

DATALAD_DOTDIR_RELPATH = '.datalad'
"""Path to dataset directory with committed datalad-specific information

``str`` path in platform conventions, relative to the root of the dataset.
"""
DATALAD_BRANCH_CONFIG_RELPATH = opj(DATALAD_DOTDIR_RELPATH, 'config')
"""Path to the branch-specific DataLad configuration file in a dataset

``str`` path in platform conventions, relative to the root of the dataset.
"""

PRE_INIT_COMMIT_SHA = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
"""Magic SHA from `git hash-object -t tree /dev/null`, i.e. from nothing"""
