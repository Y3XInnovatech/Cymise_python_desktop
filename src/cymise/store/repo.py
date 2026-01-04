from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import (
    ExtractedObject,
    FileObject,
    ModelDocument,
    RelationshipEdge,
    StitchCandidate,
    TwinNode,
)


class StoreRepository:
    """Minimal repository for graph store CRUD."""

    def __init__(self, session: Session):
        self.session = session

    # TwinNode
    def add_twin(
        self,
        dtmi: str,
        display_name: Optional[str] = None,
        model_version: Optional[str] = None,
    ) -> TwinNode:
        twin = TwinNode(dtmi=dtmi, display_name=display_name, model_version=model_version)
        self.session.add(twin)
        return self._commit_and_refresh(twin)

    def get_twin_by_dtmi(self, dtmi: str) -> Optional[TwinNode]:
        return self.session.scalar(select(TwinNode).where(TwinNode.dtmi == dtmi))

    def get_twin_by_id(self, twin_id: int) -> Optional[TwinNode]:
        return self.session.get(TwinNode, twin_id)

    def update_twin(
        self,
        dtmi: str,
        display_name: Optional[str] = None,
        model_version: Optional[str] = None,
    ) -> Optional[TwinNode]:
        twin = self.get_twin_by_dtmi(dtmi)
        if not twin:
            return None
        if display_name is not None:
            twin.display_name = display_name
        if model_version is not None:
            twin.model_version = model_version
        return self._commit_and_refresh(twin)

    def delete_twin_by_dtmi(self, dtmi: str) -> bool:
        twin = self.get_twin_by_dtmi(dtmi)
        if not twin:
            return False
        self.session.delete(twin)
        self._commit()
        return True

    def list_twins(self) -> Iterable[TwinNode]:
        return self.session.scalars(select(TwinNode)).all()

    def delete_twin(self, twin_id: int) -> None:
        twin = self.session.get(TwinNode, twin_id)
        if twin:
            self.session.delete(twin)
            self._commit()

    # RelationshipEdge
    def add_relationship(
        self, source_id: int, target_id: int, name: Optional[str] = None
    ) -> RelationshipEdge:
        edge = RelationshipEdge(source_id=source_id, target_id=target_id, name=name)
        self.session.add(edge)
        return self._commit_and_refresh(edge)

    def list_relationships(self) -> Iterable[RelationshipEdge]:
        return self.session.scalars(select(RelationshipEdge)).all()

    def get_relationship_by_id(self, edge_id: int) -> Optional[RelationshipEdge]:
        return self.session.get(RelationshipEdge, edge_id)

    def update_relationship_name(
        self, edge_id: int, name: Optional[str]
    ) -> Optional[RelationshipEdge]:
        edge = self.get_relationship_by_id(edge_id)
        if not edge:
            return None
        edge.name = name
        return self._commit_and_refresh(edge)

    def get_relationships_for_source(self, source_id: int) -> Iterable[RelationshipEdge]:
        return self.session.scalars(
            select(RelationshipEdge).where(RelationshipEdge.source_id == source_id)
        ).all()

    def get_relationships_for_target(self, target_id: int) -> Iterable[RelationshipEdge]:
        return self.session.scalars(
            select(RelationshipEdge).where(RelationshipEdge.target_id == target_id)
        ).all()

    # FileObject
    def add_file_object(
        self,
        path: str,
        media_type: Optional[str] = None,
        version: Optional[str] = None,
        twin_id: Optional[int] = None,
    ) -> FileObject:
        file_obj = FileObject(
            path=path, media_type=media_type, version=version, twin_id=twin_id
        )
        self.session.add(file_obj)
        return self._commit_and_refresh(file_obj)

    def list_file_objects(self) -> Iterable[FileObject]:
        return self.session.scalars(select(FileObject)).all()

    def get_file_object_by_id(self, file_id: int) -> Optional[FileObject]:
        return self.session.get(FileObject, file_id)

    def update_file_object(
        self,
        file_id: int,
        *,
        twin_id: Optional[int] = None,
        media_type: Optional[str] = None,
        version: Optional[str] = None,
    ) -> Optional[FileObject]:
        file_obj = self.get_file_object_by_id(file_id)
        if not file_obj:
            return None
        file_obj.twin_id = twin_id
        if media_type is not None:
            file_obj.media_type = media_type
        if version is not None:
            file_obj.version = version
        return self._commit_and_refresh(file_obj)

    # ExtractedObject
    def add_extracted_object(
        self, file_object_id: int, kind: str, data: dict
    ) -> ExtractedObject:
        extracted = ExtractedObject(file_object_id=file_object_id, kind=kind, data=data)
        self.session.add(extracted)
        return self._commit_and_refresh(extracted)

    def list_extracted_objects(self) -> Iterable[ExtractedObject]:
        return self.session.scalars(select(ExtractedObject)).all()

    def list_extracted_objects_for_file(
        self,
        file_object_id: int,
        kind: Optional[str] = None,
        newest_first: bool = True,
    ) -> Iterable[ExtractedObject]:
        stmt = select(ExtractedObject).where(ExtractedObject.file_object_id == file_object_id)
        if kind is not None:
            stmt = stmt.where(ExtractedObject.kind == kind)
        order_column = ExtractedObject.id.desc() if newest_first else ExtractedObject.id
        stmt = stmt.order_by(order_column)
        return self.session.scalars(stmt).all()

    def get_extracted_object_by_id(self, extracted_object_id: int) -> Optional[ExtractedObject]:
        return self.session.get(ExtractedObject, extracted_object_id)

    # ModelDocument
    def add_model_document(
        self, name: str, content: str, dtmi: Optional[str] = None
    ) -> ModelDocument:
        doc = ModelDocument(name=name, content=content, dtmi=dtmi)
        self.session.add(doc)
        return self._commit_and_refresh(doc)

    def list_model_documents(self) -> Iterable[ModelDocument]:
        return self.session.scalars(select(ModelDocument)).all()

    def get_model_document_by_dtmi(self, dtmi: str) -> Optional[ModelDocument]:
        return self.session.scalar(select(ModelDocument).where(ModelDocument.dtmi == dtmi))

    def upsert_model_document(
        self, name: str, content: str, dtmi: Optional[str] = None
    ) -> ModelDocument:
        existing = None
        if dtmi:
            existing = self.session.scalar(
                select(ModelDocument).where(ModelDocument.dtmi == dtmi)
            )
        if existing:
            existing.name = name
            existing.content = content
            return self._commit_and_refresh(existing)

        doc = ModelDocument(name=name, content=content, dtmi=dtmi)
        self.session.add(doc)
        return self._commit_and_refresh(doc)

    # Stitch candidates
    def add_stitch_candidate(
        self,
        file_object_id: int,
        extracted_object_id: int,
        dt_key: str,
        target_dtmi: Optional[str] = None,
        confidence: float = 0.5,
        rationale: Optional[str] = None,
        status: str = "candidate",
    ) -> StitchCandidate:
        candidate = StitchCandidate(
            file_object_id=file_object_id,
            extracted_object_id=extracted_object_id,
            dt_key=dt_key,
            target_dtmi=target_dtmi,
            confidence=confidence,
            rationale=rationale,
            status=status,
        )
        self.session.add(candidate)
        return self._commit_and_refresh(candidate)

    def list_stitch_candidates(
        self,
        *,
        file_object_id: Optional[int] = None,
        extracted_object_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> Iterable[StitchCandidate]:
        stmt = select(StitchCandidate)
        if file_object_id is not None:
            stmt = stmt.where(StitchCandidate.file_object_id == file_object_id)
        if extracted_object_id is not None:
            stmt = stmt.where(StitchCandidate.extracted_object_id == extracted_object_id)
        if status is not None:
            stmt = stmt.where(StitchCandidate.status == status)
        return self.session.scalars(stmt).all()

    def update_stitch_candidate(
        self,
        candidate_id: int,
        *,
        status: Optional[str] = None,
        target_dtmi: Optional[str] = None,
        confidence: Optional[float] = None,
        rationale: Optional[str] = None,
    ) -> Optional[StitchCandidate]:
        candidate = self.session.get(StitchCandidate, candidate_id)
        if not candidate:
            return None
        if status is not None:
            candidate.status = status
        if target_dtmi is not None:
            candidate.target_dtmi = target_dtmi
        if confidence is not None:
            candidate.confidence = confidence
        if rationale is not None:
            candidate.rationale = rationale
        return self._commit_and_refresh(candidate)

    def delete_stitches_for_file(self, file_object_id: int) -> int:
        result = self.session.execute(
            delete(StitchCandidate).where(StitchCandidate.file_object_id == file_object_id)
        )
        self._commit()
        return result.rowcount or 0

    # Validation payloads
    def set_twin_validation(self, dtmi: str, payload: Optional[dict]) -> Optional[TwinNode]:
        twin = self.get_twin_by_dtmi(dtmi)
        if not twin:
            return None
        twin.validation = payload
        return self._commit_and_refresh(twin)

    def set_edge_validation(
        self, edge_id: int, payload: Optional[dict]
    ) -> Optional[RelationshipEdge]:
        edge = self.get_relationship_by_id(edge_id)
        if not edge:
            return None
        edge.validation = payload
        return self._commit_and_refresh(edge)

    def _commit(self) -> None:
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def _commit_and_refresh(self, obj):
        try:
            self.session.commit()
            self.session.refresh(obj)
            return obj
        except Exception:
            self.session.rollback()
            raise
