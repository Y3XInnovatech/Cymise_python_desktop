from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from cymise.graph.service import GraphService


@dataclass(slots=True)
class ImpactEvidence:
    kind: str  # "dt_key_added"|"dt_key_removed"|"structural_change"|"propagated"
    detail: str
    source: Optional[str] = None


@dataclass(slots=True)
class ImpactRecord:
    dtmi: str
    severity: float
    confidence: float
    evidences: list[ImpactEvidence]
    is_propagated: bool = False


@dataclass(slots=True)
class ImpactResult:
    file_object_id: int
    kind: str
    old_extracted_object_id: int
    new_extracted_object_id: int
    impacted: list[ImpactRecord]
    propagated: list[ImpactRecord]
    summary: str


class ImpactService:
    def __init__(self, graph_service: GraphService):
        self.graph_service = graph_service

    def compute_impact_for_file(
        self, file_object_id: int, kind: str, *, hops: int = 1, directed: bool = True
    ) -> Optional[ImpactResult]:
        diff = self.graph_service.diff_latest_extraction_for_file(file_object_id, kind)
        if not diff:
            return None
        return self.compute_impact_from_diff(
            file_object_id=file_object_id, diff=diff, hops=hops, directed=directed
        )

    def compute_impact_from_diff(
        self, file_object_id: int, diff: dict, *, hops: int = 1, directed: bool = True
    ) -> ImpactResult:
        dt_key_added = diff.get("dt_key_added") or []
        dt_key_removed = diff.get("dt_key_removed") or []
        structural = diff.get("structural") or {}

        impacted_map: dict[str, ImpactRecord] = {}

        def add_impact(dtmi: str, severity: float, confidence: float, evidence: ImpactEvidence):
            record = impacted_map.get(dtmi)
            if record:
                record.severity = max(record.severity, severity)
                record.confidence = max(record.confidence, confidence)
                record.evidences.append(evidence)
            else:
                impacted_map[dtmi] = ImpactRecord(
                    dtmi=dtmi,
                    severity=severity,
                    confidence=confidence,
                    evidences=[evidence],
                    is_propagated=False,
                )

        for dt_key in dt_key_added:
            resolved = self._resolve_dtmi(dt_key, file_object_id)
            if not resolved:
                continue
            dtmi, is_direct = resolved
            severity = 0.6
            confidence = 0.9 if is_direct else 0.6
            add_impact(
                dtmi,
                severity,
                confidence,
                ImpactEvidence(kind="dt_key_added", detail=dt_key, source=str(diff["new_extracted_object_id"])),
            )

        for dt_key in dt_key_removed:
            resolved = self._resolve_dtmi(dt_key, file_object_id)
            if not resolved:
                continue
            dtmi, is_direct = resolved
            severity = 0.8
            confidence = 0.9 if is_direct else 0.6
            add_impact(
                dtmi,
                severity,
                confidence,
                ImpactEvidence(kind="dt_key_removed", detail=dt_key, source=str(diff["new_extracted_object_id"])),
            )

        structural_changed = self._structural_changed(structural)
        if structural_changed:
            for record in impacted_map.values():
                record.severity = min(1.0, record.severity + 0.2)
                record.evidences.append(
                    ImpactEvidence(kind="structural_change", detail="structural change detected")
                )

        propagated_records: list[ImpactRecord] = []
        if hops > 0:
            origin_dtmis = list(impacted_map.keys())
            for origin_dtmi in origin_dtmis:
                neighbors = self._neighbors(origin_dtmi, directed=directed)
                for neighbor in neighbors:
                    if neighbor in impacted_map or any(p.dtmi == neighbor for p in propagated_records):
                        continue
                    propagated_records.append(
                        ImpactRecord(
                            dtmi=neighbor,
                            severity=0.3,
                            confidence=0.3,
                            evidences=[
                                ImpactEvidence(
                                    kind="propagated",
                                    detail=f"propagated from {origin_dtmi}",
                                    source=str(file_object_id),
                                )
                            ],
                            is_propagated=True,
                        )
                    )

        summary = (
            f"impacted={len(impacted_map)}, propagated={len(propagated_records)}, "
            f"dt_keys +{len(dt_key_added)} -{len(dt_key_removed)}"
        )

        return ImpactResult(
            file_object_id=file_object_id,
            kind=diff.get("kind", ""),
            old_extracted_object_id=diff.get("old_extracted_object_id"),
            new_extracted_object_id=diff.get("new_extracted_object_id"),
            impacted=list(impacted_map.values()),
            propagated=propagated_records,
            summary=summary,
        )

    def _resolve_dtmi(self, dt_key: str, file_object_id: int) -> Optional[tuple[str, bool]]:
        if not isinstance(dt_key, str):
            return None
        if dt_key.startswith("dtmi:"):
            return dt_key, True

        stitches = []
        for status in ("accepted", "candidate"):
            stitches.extend(
                self.graph_service.list_stitches(file_object_id=file_object_id, status=status)
            )

        for stitch in stitches:
            if stitch.get("dt_key") == dt_key and stitch.get("target_dtmi"):
                return stitch["target_dtmi"], False
        return None

    def _structural_changed(self, structural: dict) -> bool:
        if not structural:
            return False
        if "hash_changed" in structural:
            return bool(structural.get("hash_changed"))
        for key, value in structural.items():
            if key == "kind_mismatch":
                return True
            if isinstance(value, list) and any(value):
                return True
            if isinstance(value, bool) and value:
                return True
        return False

    def _neighbors(self, dtmi: str, directed: bool) -> list[str]:
        neighbors = []
        try:
            outgoing = self.graph_service.get_outgoing_neighbors(dtmi)
            neighbors.extend(outgoing)
            if not directed:
                incoming = self.graph_service.get_incoming_neighbors(dtmi)
                neighbors.extend(incoming)
        except Exception:
            return []
        return [n.dtmi for n in neighbors]

    @staticmethod
    def to_dict(result: ImpactResult) -> dict:
        return asdict(result)
