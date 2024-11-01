from pathlib import (
    Path,
)
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
