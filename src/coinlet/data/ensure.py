"""Locate bundled Parquet data or download it into a persistent cache.

Used by the marimo explorer so molab sessions can reuse downloaded
``data/*.parquet`` files across runs without relying on PyPI ``coinlet``.
"""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.request import urlopen

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR_NAME = "coinlet_data"
ENV_DATA_DIR = "COINLET_DATA_DIR"
DEFAULT_RAW_BASE = "https://raw.githubusercontent.com/jeunjetta/coinlet/main/data"
DEFAULT_PARQUET_FILES: tuple[str, ...] = (
    "coinbase_BTC_USD_1d.parquet",
    "coinbase_ETH_USD_1d.parquet",
)
PARQUET_MAGIC = b"PAR1"


def is_parquet_bytes(data: bytes) -> bool:
    """Return True if ``data`` looks like a Parquet file (PAR1 magic)."""
    return len(data) >= 8 and data[:4] == PARQUET_MAGIC and data[-4:] == PARQUET_MAGIC


def resolve_persistent_dir(cache_dir: Path | str | None = None) -> Path:
    """Resolve the persistent download directory.

    Priority: explicit ``cache_dir`` → ``COINLET_DATA_DIR`` → ``./coinlet_data``.
    """
    if cache_dir is not None:
        return Path(cache_dir)
    env = os.environ.get(ENV_DATA_DIR)
    if env:
        return Path(env)
    return Path(DEFAULT_CACHE_DIR_NAME)


def candidate_data_dirs(
    notebook_dir: Path | str | None = None,
    cwd: Path | str | None = None,
) -> list[Path]:
    """Search order for local Parquet: public/, data/, ../data/, notebook parent data/."""
    root = Path(cwd) if cwd is not None else Path.cwd()
    dirs: list[Path] = []

    if notebook_dir is not None:
        nb = Path(notebook_dir)
        dirs.append(nb / "public")
        dirs.append(nb.parent / "data")

    dirs.append(root / "data")
    dirs.append(root / "../data")
    # Deduplicate while preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for d in dirs:
        key = d.resolve() if d.exists() else d
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def find_local_data_dir(
    notebook_dir: Path | str | None = None,
    cwd: Path | str | None = None,
) -> Path | None:
    """Return the first candidate directory that contains ``*.parquet``, or None."""
    for candidate in candidate_data_dirs(notebook_dir=notebook_dir, cwd=cwd):
        if candidate.is_dir() and any(candidate.glob("*.parquet")):
            return candidate
    return None


def _require_https(url: str) -> None:
    if not url.startswith("https://"):
        raise ValueError(f"Only https:// URLs are allowed, got: {url!r}")


def _default_fetch(url: str) -> bytes:
    _require_https(url)
    # URL is built from trusted constants (DEFAULT_RAW_BASE + known filenames).
    with urlopen(url, timeout=60) as response:  # noqa: S310
        return response.read()


def _download_file(
    url: str,
    dest: Path,
    fetch: Callable[[str], bytes],
) -> None:
    _require_https(url)
    data = fetch(url)
    if not is_parquet_bytes(data):
        raise ValueError(f"Downloaded content is not valid Parquet: {url}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(dest)
    logger.info("Cached %s (%d bytes)", dest.name, len(data))


def ensure_cached_data(
    *,
    notebook_dir: Path | str | None = None,
    cwd: Path | str | None = None,
    cache_dir: Path | str | None = None,
    force_refresh: bool = False,
    filenames: Sequence[str] | None = None,
    base_url: str = DEFAULT_RAW_BASE,
    fetch: Callable[[str], bytes] | None = None,
) -> Path:
    """Return a directory containing Parquet data, downloading if needed.

    Search order (when ``force_refresh`` is False):

    1. ``notebook_dir/public/`` (WASM / GitHub Pages bundle)
    2. ``data/`` under ``cwd``
    3. ``../data/``
    4. Existing files in the persistent cache (``COINLET_DATA_DIR`` / ``coinlet_data/``)

    If none have Parquet files (or ``force_refresh`` is True), download
    ``filenames`` from ``base_url`` into the persistent cache and return that path.

    Args:
        notebook_dir: Directory containing the notebook (for ``public/`` lookup).
        cwd: Working directory used for ``data/`` / ``../data/`` candidates.
        cache_dir: Override persistent cache location.
        force_refresh: Re-download into the persistent cache even if local data exists.
        filenames: Parquet basenames to download (defaults to bundled BTC/ETH daily).
        base_url: HTTPS base URL for remote files (must be https).
        fetch: Optional injectable downloader for tests.

    Returns:
        Path to a directory containing one or more ``*.parquet`` files.
    """
    _require_https(base_url)

    names = tuple(filenames) if filenames is not None else DEFAULT_PARQUET_FILES
    fetcher = fetch or _default_fetch
    persistent = resolve_persistent_dir(cache_dir)

    local = find_local_data_dir(notebook_dir=notebook_dir, cwd=cwd)

    if not force_refresh:
        if local is not None:
            return local
        if persistent.is_dir() and any(persistent.glob("*.parquet")):
            # Fill any missing default files, then reuse.
            _ensure_files(persistent, names, base_url, fetcher, force=False)
            return persistent

    try:
        _ensure_files(persistent, names, base_url, fetcher, force=True)
        return persistent
    except Exception:
        # WASM / offline: keep bundled public/ or data/ if download fails.
        if local is not None:
            logger.warning("Download failed; using local data at %s", local)
            return local
        raise


def _ensure_files(
    dest_dir: Path,
    names: Sequence[str],
    base_url: str,
    fetch: Callable[[str], bytes],
    *,
    force: bool,
) -> None:
    base = base_url.rstrip("/")
    dest_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        if "/" in name or name in (".", "..") or name.startswith("."):
            raise ValueError(f"Invalid parquet filename: {name!r}")
        dest = dest_dir / name
        if dest.exists() and not force:
            continue
        url = f"{base}/{name}"
        _download_file(url, dest, fetch)
