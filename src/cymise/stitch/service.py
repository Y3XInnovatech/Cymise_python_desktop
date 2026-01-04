from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cymise.graph.service import GraphService


@dataclass(slots=True)
class StitchCandidateDTO:
    file_object_id: int
    extracted_object_id: int
    dt_key: str
    target_dtmi: Optional[str]
    confidence: float
    rationale: Optional[str]
    status: str = "candidate"


class StitchService:
    def __init__(self, graph_service: GraphService):
        self.graph_service = graph_service

    def generate_candidates_for_file(self, file_object_id: int) -> list[StitchCandidateDTO]:
        file_obj = self.graph_service.repo.get_file_object_by_id(file_object_id)
        if not file_obj:
            return []

        extracted_objects = self.graph_service.repo.list_extracted_objects_for_file(file_object_id)
        candidates: list[StitchCandidateDTO] = []
        seen_keys: set[tuple[int, str, Optional[str]]] = set()

        for extracted in extracted_objects:
            data = extracted.data or {}
            dt_keys = data.get("dt_keys") or []
            if not dt_keys:
                continue

            for dt_key in dt_keys:
                if not isinstance(dt_key, str):
                    continue

                if dt_key.startswith("dtmi:"):
                    target_dtmi = dt_key
                    confidence = 0.9
                    rationale = "dt_key looks like DTMI"
                else:
                    target_dtmi = None
                    confidence = 0.3
                    rationale = "unresolved dt_key"

                dedupe_key = (extracted.id, dt_key, target_dtmi)
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)

                candidates.append(
                    StitchCandidateDTO(
                        file_object_id=file_object_id,
                        extracted_object_id=extracted.id,
                        dt_key=dt_key,
                        target_dtmi=target_dtmi,
                        confidence=confidence,
                        rationale=rationale,
                        status="candidate",
                    )
                )

        return candidates

    def persist_candidates(self, candidates: list[StitchCandidateDTO]) -> list[int]:
        ids: list[int] = []
        for candidate in candidates:
            row = self.graph_service.repo.add_stitch_candidate(
                file_object_id=candidate.file_object_id,
                extracted_object_id=candidate.extracted_object_id,
                dt_key=candidate.dt_key,
                target_dtmi=candidate.target_dtmi,
                confidence=candidate.confidence,
                rationale=candidate.rationale,
                status=candidate.status,
            )
            ids.append(row.id)
        return ids

    def stitch_file(self, file_object_id: int) -> list[dict]:
        candidates = self.generate_candidates_for_file(file_object_id)
        if not candidates:
            return []
        ids = self.persist_candidates(candidates)
        result = []
        for candidate_id, candidate in zip(ids, candidates):
            result.append(
                {
                    "id": candidate_id,
                    "file_object_id": candidate.file_object_id,
                    "extracted_object_id": candidate.extracted_object_id,
                    "dt_key": candidate.dt_key,
                    "target_dtmi": candidate.target_dtmi,
                    "confidence": candidate.confidence,
                    "rationale": candidate.rationale,
                    "status": candidate.status,
                }
            )
        return result
