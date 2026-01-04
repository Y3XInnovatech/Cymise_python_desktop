from __future__ import annotations

from typing import Sequence, Set


def severity_bucket(value: float) -> str:
    if value >= 0.75:
        return "high"
    if value >= 0.4:
        return "medium"
    return "low"


def rank_and_filter_impacts(
    records: Sequence[dict],
    severity_filter: Set[str],
    include_propagated: bool = True,
) -> list[dict]:
    filtered = []
    for rec in records:
        if not include_propagated and rec.get("is_propagated"):
            continue
        bucket = severity_bucket(float(rec.get("severity", 0.0)))
        if severity_filter and bucket not in severity_filter:
            continue
        rec_copy = dict(rec)
        rec_copy["_severity_bucket"] = bucket
        filtered.append(rec_copy)
    filtered.sort(key=lambda r: (-float(r.get("severity", 0.0)), -float(r.get("confidence", 0.0))))
    return filtered
