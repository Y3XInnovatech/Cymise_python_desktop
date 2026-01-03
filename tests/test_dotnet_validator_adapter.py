from __future__ import annotations

import json
from types import SimpleNamespace

import cymise.dtdl.dotnet_validator as dotnet_validator
from cymise.dtdl.dotnet_validator import validate_with_dotnet


class DummyCompleted(SimpleNamespace):
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        super().__init__(returncode=returncode, stdout=stdout, stderr=stderr)


def test_success_json(monkeypatch, tmp_path):
    called = {}

    def fake_run(cmd, **kwargs):
        called["cmd"] = cmd
        payload = {
            "issues": [
                {
                    "severity": "Error",
                    "message": "bad model",
                    "modelId": "dtmi:com:example:device;1",
                    "path": "/interface",
                    "code": "E100",
                },
                {"severity": "warning", "message": "just a warning"},
            ]
        }
        return DummyCompleted(stdout=json.dumps(payload), stderr="", returncode=0)

    monkeypatch.setattr(dotnet_validator.subprocess, "run", fake_run)

    model_path = tmp_path / "model.json"
    result = validate_with_dotnet(model_path)

    assert len(result.issues) == 2
    assert result.errors[0].severity == "error"
    assert result.errors[0].code == "E100"
    assert called["cmd"][-2:] == ["--input", str(model_path)]
    assert called["cmd"][0].lower().endswith(".exe")


def test_error_json_exit_code_two(monkeypatch, tmp_path):
    def fake_run(cmd, **kwargs):
        payload = {
            "issues": [
                {
                    "severity": "ERROR",
                    "message": "broken",
                    "code": "E200",
                    "path": "/bad",
                }
            ]
        }
        return DummyCompleted(stdout=json.dumps(payload), stderr="", returncode=2)

    monkeypatch.setattr(dotnet_validator.subprocess, "run", fake_run)

    result = validate_with_dotnet(tmp_path / "model.json")

    assert len(result.errors) == 1
    assert result.errors[0].code == "E200"
    assert result.errors[0].message == "broken"


def test_tool_failure(monkeypatch, tmp_path):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("dotnet")

    monkeypatch.setattr(dotnet_validator.subprocess, "run", fake_run)

    result = validate_with_dotnet(tmp_path / "model.json")

    assert len(result.errors) == 1
    assert result.errors[0].code == "validator_not_found"
    assert "not found" in result.errors[0].message.lower()


def test_bad_json(monkeypatch, tmp_path):
    def fake_run(cmd, **kwargs):
        return DummyCompleted(stdout="not-json", stderr="", returncode=0)

    monkeypatch.setattr(dotnet_validator.subprocess, "run", fake_run)

    result = validate_with_dotnet(tmp_path / "model.json")

    assert len(result.errors) == 1
    assert result.errors[0].code == "invalid_validator_output"
