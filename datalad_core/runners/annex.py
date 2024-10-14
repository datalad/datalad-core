from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

from datasalad.itertools import (
    itemize,
    load_json,
)

from datalad_core.runners.git import iter_git_subproc
from datalad_core.runners.imports import CommandError

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


def call_annex_json_lines(
    annex_args: list[str],
    *,
    git_args: list[str] | None = None,
    cwd: Path | None = None,
) -> Generator[Any]:
    """Runs a git-annex command and yields JSON-based results

    This function can only be used with git-annex commands that
    support both ``--json`` and ``--json-error-messages``. These
    options are automatically and unconditionally added to the
    command arguments.

    If ``git_args`` are provided, they will be prepended to the
    annex command (i.e., ``git <git_args> annex <annex_args>``.

    The ``cwd`` parameter is passed on to :func:`iter_git_subproc`,
    which perform the actual command execution.
    """
    cmd = git_args or []
    cmd.append('annex')
    cmd.extend(annex_args)
    cmd.extend(('--json', '--json-error-messages'))

    # we collect error results in order to be able to enrich an eventual
    # command error. this could be done in consuming code, but it
    # makes senses to MIH to do this in this central place.
    # the motivation here is that git-annex with --json-error-messages
    # will communicate errors via stdout (part of JSON lines), so we yield
    # them. But if consuming code does not actively look for information
    # on errors in them, they will only see a CommandError, which only
    # carries stderr capture (which hardly ever has the real info).
    error_results = []

    try:
        with iter_git_subproc(cmd, cwd=cwd) as annex_proc:
            for res in load_json(itemize(annex_proc, sep=None)):
                if res.get('success', True) is False:
                    error_results.append(
                        {
                            k: v
                            for k, v in res.items()
                            if k in ('command', 'input', 'error-messages', 'note')
                        }
                    )
                yield res
    except CommandError as e:
        # TODO: I think we'd rather want to have an exception subclass here
        # that can take this information in a structured fashion, and does the
        # formatting on access
        e.msg = _format_errors(error_results)
        raise


def _format_errors(err: list[dict[str, str | list[str]]]) -> str:
    nerrors = len(err)
    if not nerrors:
        return ''
    if nerrors == 1:
        return _format_error(err[0])
    return f'{nerrors} errors: {[_format_error(e) for e in err]}'


def _format_error(err: dict[str, str | list[str]]) -> str:
    # we cannot newline-join in an f-string with PY3.9, so do upfront
    error_messages = err.get('error-messages')
    if error_messages:
        formated_error_msg = '\n'.join(err['error-messages'])
    return ''.join(
        (
            f'{err["command"]!r} ' if 'command' in err else '',
            'failed',
            f' for input {err["input"]!r}' if err.get('input') else '',
            f' with {formated_error_msg!r}' if error_messages else '',
            f' [note: {err["note"]}]' if 'note' in err else '',
        )
    )
