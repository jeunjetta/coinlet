"""Tests for molab/local notebook bootstrap (path resolution + install helpers)."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from coinlet.bootstrap import (
    COINLET_GIT_URL,
    BootstrapResult,
    candidate_src_dirs,
    coinlet_available,
    ensure_coinlet,
    find_local_src,
    install_coinlet_from_git,
    is_wasm,
    prepend_sys_path,
)


def _make_src_tree(root: Path) -> Path:
    src = root / "src"
    pkg = src / "coinlet"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('__version__ = "0.0-test"\n', encoding="utf-8")
    return src


class TestIsWasm:
    def test_emscripten(self) -> None:
        assert is_wasm("emscripten") is True

    def test_other_platform(self) -> None:
        assert is_wasm("linux") is False


class TestCandidateSrcDirs:
    def test_includes_common_hints_relative_to_notebook_and_cwd(self, tmp_path: Path) -> None:
        nb = tmp_path / "notebooks"
        nb.mkdir()
        cwd = tmp_path
        dirs = candidate_src_dirs(notebook_dir=nb, cwd=cwd)
        resolved = {d.resolve() for d in dirs}
        assert (nb / "../src").resolve() in resolved
        assert (cwd / "src").resolve() in resolved
        assert (cwd / "coinlet" / "src").resolve() in resolved


class TestFindLocalSrc:
    def test_finds_repo_src_from_notebook_dir(self, tmp_path: Path) -> None:
        src = _make_src_tree(tmp_path)
        notebooks = tmp_path / "notebooks"
        notebooks.mkdir()

        found = find_local_src(notebook_dir=notebooks, cwd=notebooks)
        assert found is not None
        assert found.resolve() == src.resolve()

    def test_finds_nested_coinlet_src(self, tmp_path: Path) -> None:
        src = _make_src_tree(tmp_path / "coinlet")
        found = find_local_src(notebook_dir=tmp_path, cwd=tmp_path)
        assert found is not None
        assert found.resolve() == src.resolve()

    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        assert find_local_src(notebook_dir=tmp_path, cwd=tmp_path) is None


class TestPrependSysPath:
    def test_inserts_at_front(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "path", ["/other", str(tmp_path)])
        prepend_sys_path(tmp_path)
        assert sys.path[0] == str(tmp_path.resolve())
        assert sys.path.count(str(tmp_path.resolve())) == 1


class TestInstallCoinletFromGit:
    def test_prefers_uv_with_python_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], check: bool = False, **kwargs: object) -> MagicMock:
            calls.append(list(cmd))
            return MagicMock(returncode=0)

        monkeypatch.setattr("coinlet.bootstrap.shutil.which", lambda name: "/usr/bin/uv")
        monkeypatch.setattr("coinlet.bootstrap.subprocess.run", fake_run)
        invalidate = MagicMock()
        monkeypatch.setattr(importlib, "invalidate_caches", invalidate)

        # Mirror molab's active venv path shape without hardcoding /tmp literals.
        venv_python = str(tmp_path / "uv-venv" / "bin" / "python")
        install_coinlet_from_git(python=venv_python)

        assert calls == [
            [
                "/usr/bin/uv",
                "pip",
                "install",
                "--python",
                venv_python,
                COINLET_GIT_URL,
            ]
        ]
        invalidate.assert_called_once()

    def test_falls_back_to_pip_when_uv_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], check: bool = False, **kwargs: object) -> MagicMock:
            calls.append(list(cmd))
            return MagicMock(returncode=0)

        monkeypatch.setattr("coinlet.bootstrap.shutil.which", lambda name: None)
        monkeypatch.setattr("coinlet.bootstrap.subprocess.run", fake_run)
        monkeypatch.setattr(importlib, "invalidate_caches", MagicMock())

        install_coinlet_from_git(python=sys.executable)

        assert calls == [[sys.executable, "-m", "pip", "install", "--no-input", COINLET_GIT_URL]]

    def test_falls_back_to_pip_when_uv_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], check: bool = False, **kwargs: object) -> MagicMock:
            calls.append(list(cmd))
            if cmd and cmd[0] == "/usr/bin/uv":
                raise subprocess.CalledProcessError(1, cmd)
            return MagicMock(returncode=0)

        monkeypatch.setattr("coinlet.bootstrap.shutil.which", lambda name: "/usr/bin/uv")
        monkeypatch.setattr("coinlet.bootstrap.subprocess.run", fake_run)
        monkeypatch.setattr(importlib, "invalidate_caches", MagicMock())

        install_coinlet_from_git(python=sys.executable)

        assert calls[0][0] == "/usr/bin/uv"
        assert calls[1] == [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-input",
            COINLET_GIT_URL,
        ]


class TestEnsureCoinlet:
    def test_skips_on_wasm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("coinlet.bootstrap.sys.platform", "emscripten")
        result = ensure_coinlet()
        assert result == BootstrapResult(
            kind="wasm",
            detail="Pyodide/WASM runtime — skip pip/uv install",
        )

    def test_skips_when_already_importable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("coinlet.bootstrap.sys.platform", "linux")
        monkeypatch.setattr("coinlet.bootstrap.coinlet_available", lambda: True)
        install = MagicMock()
        monkeypatch.setattr("coinlet.bootstrap.install_coinlet_from_git", install)

        result = ensure_coinlet(notebook_dir=tmp_path, cwd=tmp_path)

        assert result.kind == "installed"
        install.assert_not_called()

    def test_uses_local_repo_src(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        src = _make_src_tree(tmp_path)
        notebooks = tmp_path / "notebooks"
        notebooks.mkdir()
        monkeypatch.setattr("coinlet.bootstrap.sys.platform", "linux")
        monkeypatch.setattr("coinlet.bootstrap.coinlet_available", lambda: False)
        install = MagicMock()
        monkeypatch.setattr("coinlet.bootstrap.install_coinlet_from_git", install)
        monkeypatch.setattr(sys, "path", list(sys.path))

        result = ensure_coinlet(notebook_dir=notebooks, cwd=tmp_path)

        assert result.kind == "repo"
        assert result.src_path is not None
        assert result.src_path.resolve() == src.resolve()
        assert sys.path[0] == str(src.resolve())
        install.assert_not_called()

    def test_installs_from_github_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("coinlet.bootstrap.sys.platform", "linux")
        install = MagicMock()
        monkeypatch.setattr("coinlet.bootstrap.install_coinlet_from_git", install)
        # Before install: missing; after install: importable.
        states = iter([False, True])

        def available() -> bool:
            return next(states, True)

        monkeypatch.setattr("coinlet.bootstrap.coinlet_available", available)

        result = ensure_coinlet(notebook_dir=tmp_path, cwd=tmp_path)

        assert result.kind == "github"
        assert COINLET_GIT_URL in result.detail
        install.assert_called_once()


class TestCoinletAvailable:
    def test_true_in_dev_environment(self) -> None:
        # The test suite runs with src/ on path via pytest pythonpath.
        assert coinlet_available() is True
