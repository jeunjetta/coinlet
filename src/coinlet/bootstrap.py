"""Bootstrap helpers so molab notebooks load coinlet without PyPI auto-install.

Molab's marimo auto-installer maps ``import coinlet`` to ``uv pip install coinlet``
(PyPI), which fails because this package is not published there. Notebooks should:

1. Call :func:`ensure_coinlet` in a cell that returns a sentinel (e.g. ``coinlet_source``).
2. Pass that sentinel into every cell that loads coinlet (via ``importlib``) so the
   DAG runs bootstrap first.
3. Prefer ``importlib.import_module("coinlet...")`` over static ``import coinlet`` so
   marimo's AST scanner does not trigger a PyPI install.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

COINLET_GIT_URL = "git+https://github.com/jeunjetta/coinlet.git"

# Relative to notebook_dir and/or cwd (molab may mount the repo in several layouts).
_SRC_HINTS: tuple[str, ...] = (
    "../src",
    "src",
    "./src",
    "coinlet/src",
    "./coinlet/src",
    "../coinlet/src",
)


@dataclass(frozen=True)
class BootstrapResult:
    """Where coinlet was loaded from for UI / debugging."""

    kind: str  # "wasm" | "installed" | "repo" | "github"
    detail: str
    src_path: Path | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "kind": self.kind,
            "detail": self.detail,
            "src_path": str(self.src_path) if self.src_path is not None else None,
        }


def is_wasm(platform: str | None = None) -> bool:
    """Return True when running under Pyodide / emscripten."""
    return (platform if platform is not None else sys.platform) == "emscripten"


def coinlet_available() -> bool:
    """Return True if the ``coinlet`` package can be imported."""
    return importlib.util.find_spec("coinlet") is not None


def candidate_src_dirs(
    notebook_dir: Path | str | None = None,
    cwd: Path | str | None = None,
) -> list[Path]:
    """Return candidate ``src`` directories (may not exist yet)."""
    roots: list[Path] = []
    if notebook_dir is not None:
        roots.append(Path(notebook_dir))
    roots.append(Path(cwd) if cwd is not None else Path.cwd())

    out: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        for hint in _SRC_HINTS:
            candidate = root / hint
            key = candidate.resolve() if candidate.exists() else candidate
            if key in seen:
                continue
            seen.add(key)
            out.append(candidate)
    return out


def find_local_src(
    notebook_dir: Path | str | None = None,
    cwd: Path | str | None = None,
) -> Path | None:
    """Return the first ``src`` dir that contains ``coinlet/__init__.py``."""
    for candidate in candidate_src_dirs(notebook_dir=notebook_dir, cwd=cwd):
        marker = candidate / "coinlet" / "__init__.py"
        if marker.is_file():
            return candidate.resolve()
    return None


def prepend_sys_path(src: Path | str) -> None:
    """Insert ``src`` at ``sys.path[0]``, deduplicating if already present."""
    resolved = str(Path(src).resolve())
    while resolved in sys.path:
        sys.path.remove(resolved)
    sys.path.insert(0, resolved)


def install_coinlet_from_git(
    *,
    git_url: str = COINLET_GIT_URL,
    python: str | None = None,
) -> None:
    """Install coinlet into the active interpreter from GitHub.

    Prefers ``uv pip install --python <sys.executable>`` so molab's ``/tmp/uv-venv``
    receives the package, then falls back to ``python -m pip``.
    """
    if not git_url.startswith("git+https://"):
        raise ValueError(f"Only git+https:// URLs are allowed, got: {git_url!r}")

    interpreter = python or sys.executable
    uv = shutil.which("uv")
    if uv is not None:
        uv_cmd = [uv, "pip", "install", "--python", interpreter, git_url]
        try:
            # uv path from shutil.which; argv is a fixed install of a trusted URL.
            subprocess.run(uv_cmd, check=True)  # noqa: S603
            importlib.invalidate_caches()
            logger.info("Installed coinlet via uv into %s", interpreter)
            return
        except (OSError, subprocess.CalledProcessError) as exc:
            logger.warning("uv install failed (%s); falling back to pip", exc)

    pip_cmd = [interpreter, "-m", "pip", "install", "--no-input", git_url]
    subprocess.run(pip_cmd, check=True)  # noqa: S603
    importlib.invalidate_caches()
    logger.info("Installed coinlet via pip into %s", interpreter)


def ensure_coinlet(
    *,
    notebook_dir: Path | str | None = None,
    cwd: Path | str | None = None,
    git_url: str = COINLET_GIT_URL,
    python: str | None = None,
) -> BootstrapResult:
    """Make ``coinlet`` importable and report where it came from.

    Order:

    1. WASM / emscripten — skip install (bundled env).
    2. Already importable — reuse installed package.
    3. Local repo ``src/`` — prepend to ``sys.path``.
    4. Otherwise install from ``git+https://github.com/jeunjetta/coinlet.git``.
    """
    if is_wasm():
        return BootstrapResult(
            kind="wasm",
            detail="Pyodide/WASM runtime — skip pip/uv install",
        )

    if coinlet_available():
        return BootstrapResult(
            kind="installed",
            detail="coinlet already importable in this environment",
        )

    local = find_local_src(notebook_dir=notebook_dir, cwd=cwd)
    if local is not None:
        prepend_sys_path(local)
        importlib.invalidate_caches()
        return BootstrapResult(
            kind="repo",
            detail=f"Added local src to sys.path: {local}",
            src_path=local,
        )

    install_coinlet_from_git(git_url=git_url, python=python)
    if not coinlet_available():
        raise RuntimeError(
            "coinlet is still not importable after installing from "
            f"{git_url}. Check network access and the active virtualenv."
        )
    return BootstrapResult(
        kind="github",
        detail=f"Installed from {git_url}",
    )
