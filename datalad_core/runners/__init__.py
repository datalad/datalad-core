"""Execution of subprocesses

This module provides all relevant components for subprocess execution.  The
main work horse is :func:`~datalad_core.runners.iter_subproc`, a context
manager that enables interaction with a subprocess in the form of an iterable
for input/output processing. Execution errors are communicated with the
:class:`~datalad_core.runners.CommandError` exception. In addition, a few
convenience functions are provided to execute Git commands (including
git-annex).

.. currentmodule:: datalad_core.runners
.. autosummary::
   :toctree: generated

   call_git
   call_git_lines
   call_git_oneline
   call_git_success
   iter_subproc
   iter_git_subproc
   CommandError
"""

__all__ = [
    'CommandError',
    'iter_subproc',
    'iter_git_subproc',
    'call_git',
    'call_git_lines',
    'call_git_oneline',
    'call_git_success',
]


from datasalad.runners import (
    CommandError,
    iter_subproc,
)

from .git import (
    call_git,
    call_git_lines,
    call_git_oneline,
    call_git_success,
    iter_git_subproc,
)
