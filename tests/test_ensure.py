"""Tests for local data discovery and remote Parquet caching."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from coinlet.data.ensure import (
    DEFAULT_PARQUET_FILES,
    DEFAULT_RAW_BASE,
    ensure_cached_data,
    find_local_data_dir,
    is_parquet_bytes,
    resolve_persistent_dir,
)

PARQUET_HEADER = b"PAR1" + b"\x00" * 20 + b"PAR1"


def _write_fake_parquet(path: Path, payload: bytes = PARQUET_HEADER) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


class TestFindLocalDataDir:
    def test_prefers_notebook_public(self, tmp_path: Path) -> None:
        notebook_dir = tmp_path / "notebooks"
        public = notebook_dir / "public"
        data = tmp_path / "data"
        _write_fake_parquet(public / "a.parquet")
        _write_fake_parquet(data / "b.parquet")

        found = find_local_data_dir(notebook_dir=notebook_dir, cwd=tmp_path)
        assert found == public

    def test_falls_back_to_data_dir(self, tmp_path: Path) -> None:
        data = tmp_path / "data"
        _write_fake_parquet(data / "coinbase_BTC_USD_1d.parquet")

        found = find_local_data_dir(notebook_dir=tmp_path / "notebooks", cwd=tmp_path)
        assert found == data

    def test_falls_back_to_parent_data(self, tmp_path: Path) -> None:
        notebooks = tmp_path / "notebooks"
        notebooks.mkdir()
        data = tmp_path / "data"
        _write_fake_parquet(data / "x.parquet")

        found = find_local_data_dir(notebook_dir=notebooks, cwd=notebooks)
        assert found == Path("../data") or found.resolve() == data.resolve()

    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        assert find_local_data_dir(notebook_dir=tmp_path, cwd=tmp_path) is None


class TestResolvePersistentDir:
    def test_explicit_cache_dir(self, tmp_path: Path) -> None:
        target = tmp_path / "custom"
        assert resolve_persistent_dir(cache_dir=target) == target

    def test_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "from_env"
        monkeypatch.setenv("COINLET_DATA_DIR", str(target))
        assert resolve_persistent_dir() == target

    def test_default_coinlet_data(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("COINLET_DATA_DIR", raising=False)
        monkeypatch.chdir(tmp_path)
        assert resolve_persistent_dir() == Path("coinlet_data")


class TestParquetValidation:
    def test_accepts_parquet_magic(self) -> None:
        assert is_parquet_bytes(PARQUET_HEADER)

    def test_rejects_non_parquet(self) -> None:
        assert not is_parquet_bytes(b"not parquet")
        assert not is_parquet_bytes(b"")


class TestEnsureCachedData:
    def test_uses_local_when_present(self, tmp_path: Path) -> None:
        data = tmp_path / "data"
        _write_fake_parquet(data / "local.parquet")
        fetch = MagicMock()

        result = ensure_cached_data(notebook_dir=tmp_path, cwd=tmp_path, fetch=fetch)

        assert result == data
        fetch.assert_not_called()

    def test_downloads_when_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("COINLET_DATA_DIR", raising=False)
        cache = tmp_path / "coinlet_data"
        fetched_urls: list[str] = []

        def fetch(url: str) -> bytes:
            fetched_urls.append(url)
            assert url.startswith("https://")
            name = url.rsplit("/", 1)[-1]
            assert name in DEFAULT_PARQUET_FILES
            return PARQUET_HEADER

        result = ensure_cached_data(
            notebook_dir=tmp_path / "empty",
            cwd=tmp_path,
            cache_dir=cache,
            fetch=fetch,
        )

        assert result == cache
        assert sorted(p.name for p in cache.glob("*.parquet")) == sorted(DEFAULT_PARQUET_FILES)
        assert all(u.startswith(DEFAULT_RAW_BASE) for u in fetched_urls)
        assert len(fetched_urls) == len(DEFAULT_PARQUET_FILES)

    def test_reuses_persistent_cache(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cache = tmp_path / "coinlet_data"
        for name in DEFAULT_PARQUET_FILES:
            _write_fake_parquet(cache / name)
        fetch = MagicMock()

        result = ensure_cached_data(
            notebook_dir=tmp_path / "empty",
            cwd=tmp_path,
            cache_dir=cache,
            fetch=fetch,
        )

        assert result == cache
        fetch.assert_not_called()

    def test_force_refresh_redownloads(self, tmp_path: Path) -> None:
        cache = tmp_path / "coinlet_data"
        for name in DEFAULT_PARQUET_FILES:
            _write_fake_parquet(cache / name, payload=b"PAR1" + b"OLD" + b"PAR1")

        calls = 0

        def fetch(url: str) -> bytes:
            nonlocal calls
            calls += 1
            return PARQUET_HEADER

        # Local data exists, but force_refresh should still re-download into cache.
        data = tmp_path / "data"
        _write_fake_parquet(data / "local.parquet")

        result = ensure_cached_data(
            notebook_dir=tmp_path,
            cwd=tmp_path,
            cache_dir=cache,
            force_refresh=True,
            fetch=fetch,
        )

        assert result == cache
        assert calls == len(DEFAULT_PARQUET_FILES)
        assert (cache / DEFAULT_PARQUET_FILES[0]).read_bytes() == PARQUET_HEADER

    def test_rejects_http_base_url(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="https"):
            ensure_cached_data(
                notebook_dir=tmp_path,
                cwd=tmp_path,
                cache_dir=tmp_path / "cache",
                base_url="http://example.com/data",
                fetch=lambda url: PARQUET_HEADER,
            )

    def test_rejects_invalid_download(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Parquet"):
            ensure_cached_data(
                notebook_dir=tmp_path,
                cwd=tmp_path,
                cache_dir=tmp_path / "cache",
                fetch=lambda url: b"not-parquet",
            )

    def test_download_skips_existing_files_unless_refresh(self, tmp_path: Path) -> None:
        cache = tmp_path / "coinlet_data"
        existing = DEFAULT_PARQUET_FILES[0]
        _write_fake_parquet(cache / existing)
        fetched: list[str] = []

        def fetch(url: str) -> bytes:
            fetched.append(url)
            return PARQUET_HEADER

        ensure_cached_data(
            notebook_dir=tmp_path / "empty",
            cwd=tmp_path,
            cache_dir=cache,
            fetch=fetch,
        )

        assert len(fetched) == len(DEFAULT_PARQUET_FILES) - 1
        assert not any(existing in u for u in fetched)
