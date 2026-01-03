from __future__ import annotations

from cymise.dtdl.preflight import preflight_validate


def _base_model(dtmi: str = "dtmi:com:example:device;1", type_value="Interface"):
    return {"@id": dtmi, "@type": type_value, "@context": "dtmi:dtdl:context;3"}


def test_missing_required_keys():
    result = preflight_validate([{}])
    missing = [issue for issue in result.errors if issue.code == "missing_key"]
    assert len(missing) == 3


def test_invalid_dtmi():
    model = _base_model(dtmi="not-a-dtmi")
    result = preflight_validate([model])
    assert any(issue.code == "invalid_dtmi" for issue in result.errors)


def test_duplicate_ids():
    model_a = _base_model()
    model_b = _base_model()
    result = preflight_validate([model_a, model_b])
    assert any(issue.code == "duplicate_id" for issue in result.errors)


def test_valid_interface_passes():
    model = _base_model()
    model["contents"] = []
    result = preflight_validate([model])
    assert result.is_ok
    assert not result.warnings


def test_contents_must_be_list():
    model = _base_model()
    model["contents"] = {}
    result = preflight_validate([model])
    assert any(issue.code == "invalid_contents_type" for issue in result.errors)


def test_type_list_and_string_handled():
    string_model = _base_model(type_value="Interface")
    list_model = _base_model(
        dtmi="dtmi:com:example:device:alt;1", type_value=["Interface", "Base"]
    )
    result = preflight_validate([string_model, list_model])
    assert not result.errors

    no_interface = _base_model(type_value=["Telemetry"])
    warn_result = preflight_validate([no_interface])
    assert any(issue.code == "missing_interface_type" for issue in warn_result.warnings)


def test_unknown_keys_warn():
    model = _base_model()
    model["customKey"] = 123
    result = preflight_validate([model])
    assert any(issue.code == "unknown_key" for issue in result.warnings)
