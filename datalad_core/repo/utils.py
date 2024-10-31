from __future__ import annotations

from typing import TYPE_CHECKING

from datalad_core.runners import call_annex_json_lines

if TYPE_CHECKING:
    from pathlib import Path


def init_annex_at(
    path: Path,
    *,
    description: str | None = None,
    autoenable_remotes: bool = True,
) -> None:
    """Call ``git-annex init`` at a given ``path``

    The ``description`` parameter can be used to label the annex. Otherwise,
    git-annex will auto-generate a description based on username, hostname, and
    the path of the repository.

    The boolean flag ``autoenable_remotes`` controls whether or not
    git-annex should honor a special remote's configuration to get
    auto-enabled on initialization.
    """
    cmd = ['init']
    if not autoenable_remotes:
        # no, we do not set --autoenable, this is a RepoAnnex feature
        cmd.append('--no-autoenable')
    if description is not None:
        cmd.append(description)
    # collect all items, we only expect a single one
    # TODO: consume()?
    list(call_annex_json_lines(cmd, cwd=path))
