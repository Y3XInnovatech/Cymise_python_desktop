from __future__ import annotations

from cymise.ui.impact_logic import rank_and_filter_impacts, severity_bucket


def test_rank_and_filter_impacts_orders_and_filters():
    records = [
        {"dtmi": "b", "severity": 0.5, "confidence": 0.6},
        {"dtmi": "a", "severity": 0.9, "confidence": 0.4},
        {"dtmi": "c", "severity": 0.2, "confidence": 0.9},
    ]

    result = rank_and_filter_impacts(records, severity_filter={"high", "medium"}, include_propagated=True)
    assert [r["dtmi"] for r in result] == ["a", "b"]
    assert result[0]["_severity_bucket"] == "high"
    assert result[1]["_severity_bucket"] == "medium"


def test_severity_bucket_thresholds():
    assert severity_bucket(0.8) == "high"
    assert severity_bucket(0.5) == "medium"
    assert severity_bucket(0.1) == "low"
