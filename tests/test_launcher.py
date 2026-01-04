from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from cymise.tools import launcher


def test_open_with_default_app_windows(monkeypatch, tmp_path):
    called = {}

    def fake_startfile(path):
        called["path"] = path

    monkeypatch.setattr(launcher.platform, "system", lambda: "Windows")
    monkeypatch.setattr(os, "startfile", fake_startfile)  # type: ignore[attr-defined]

    file_path = tmp_path / "f.txt"
    file_path.write_text("x")
    result = launcher.open_with_default_app(file_path)

    assert result.ok
    assert called["path"] == str(file_path)


def test_launch_tool_env_override(monkeypatch, tmp_path):
    file_path = tmp_path / "model.fcstd"
    file_path.write_text("x")

    monkeypatch.setenv("CYMISE_FREECAD_CMD", "C:\\FreeCAD\\FreeCAD.exe --flag")
    spawned = {}

    def fake_popen(cmd):
        spawned["cmd"] = cmd
        return SimpleNamespace()

    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)

    result = launcher.launch_tool("freecad", file_path)

    assert result.ok
    assert spawned["cmd"][0].endswith("FreeCAD.exe")
    assert spawned["cmd"][-1] == str(file_path)


def test_launch_tool_which_fallback(monkeypatch, tmp_path):
    file_path = tmp_path / "board.kicad_pcb"
    file_path.write_text("x")

    monkeypatch.delenv("CYMISE_KICAD_CMD", raising=False)
    monkeypatch.setattr(launcher.shutil, "which", lambda _: "kicad")
    spawned = {}

    def fake_popen(cmd):
        spawned["cmd"] = cmd
        return SimpleNamespace()

    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)

    result = launcher.launch_tool("kicad", file_path)

    assert result.ok
    assert spawned["cmd"][0] == "kicad"
    assert spawned["cmd"][-1] == str(file_path)


def test_launch_tool_missing_file(tmp_path):
    missing = tmp_path / "missing.step"
    result = launcher.launch_tool("default", missing)
    assert not result.ok
    assert "does not exist" in result.message
