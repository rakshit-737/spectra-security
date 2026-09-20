"""sys.path wiring for the workspace.

Why this exists: the workspace packages live under `python/<name>/src/<name>/` and none
of them is installed. There is no pip on this machine and no network to reach one, so
`pip install -e` is not an option and neither is a `.pth` file dropped into a
site-packages directory that no process owns. The alternative to this module is every
entry point growing its own hand-rolled path arithmetic, which drifts.

THE ONE LINE other entry points call, once, before importing any sibling package:

    from spectra_core.bootstrap import install; install()

A script that cannot yet import `spectra_core` at all needs the bootstrap file itself on
the path first. Two lines, and the only two that should ever appear:

    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[N] / "python" / "spectra_core" / "src"))
    from spectra_core.bootstrap import install; install()

where N walks from the script up to the repository root.

`install()` is idempotent and appends rather than prepends, so a genuinely installed
package would still win over the working tree. It reads no environment variable, because
a path that depends on the environment is a path that differs between two runs that are
supposed to be byte-identical. It reads no wall clock.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

__all__ = ["SRC_GLOB", "find_repo_root", "install", "workspace_src_dirs"]

#: Where a workspace package keeps its importable tree, relative to the repository root.
SRC_GLOB: Final[str] = "python/*/src"

#: Files that together identify the repository root and no subdirectory of it.
_ROOT_MARKERS: Final[tuple[str, ...]] = ("pyproject.toml", "docs", "python")


def find_repo_root(start: Path | None = None) -> Path:
    """Walk upwards from `start` until a directory holds every root marker.

    Markers rather than a fixed number of `parents[]` hops so that moving this module
    deeper or shallower in the tree does not silently point the workspace at the wrong
    directory; a wrong root would import a stale copy of a package rather than fail.
    """
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if candidate.is_dir() and all((candidate / m).exists() for m in _ROOT_MARKERS):
            return candidate
    raise RuntimeError(
        f"bootstrap: no directory above {here} holds all of {_ROOT_MARKERS}; "
        "run from inside the repository"
    )


def workspace_src_dirs(repo_root: Path | None = None) -> tuple[str, ...]:
    """Every `python/*/src` directory, sorted bytewise ascending.

    Sorted, not glob-ordered: glob order is filesystem order, and a path list whose order
    depends on the filesystem is a path list that can resolve a name two ways on two
    machines.
    """
    root = repo_root if repo_root is not None else find_repo_root()
    found = [p for p in root.glob(SRC_GLOB) if p.is_dir()]
    return tuple(sorted((str(p) for p in found), key=lambda s: s.encode("utf-8")))


def install(repo_root: Path | None = None) -> tuple[str, ...]:
    """Append every workspace source directory to `sys.path`. Returns what was added.

    Appends so that a real installation takes precedence over the working tree, and
    skips anything already present so that calling it from several entry points in one
    process cannot grow `sys.path` without bound.
    """
    added: list[str] = []
    for src in workspace_src_dirs(repo_root):
        if src not in sys.path:
            sys.path.append(src)
            added.append(src)
    return tuple(added)
