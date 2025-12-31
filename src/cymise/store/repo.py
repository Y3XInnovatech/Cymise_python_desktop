from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    ExtractedObject,
    FileObject,
    ModelDocument,
    RelationshipEdge,
    TwinNode,
)


class StoreRepository:
    """Minimal repository for graph store CRUD."""

    def __init__(self, session: Session):
        self.session = session

    # TwinNode
    def add_twin(self, dtmi: str, display_name: Optional[str] = None) -> TwinNode:
        twin = TwinNode(dtmi=dtmi, display_name=display_name)
        self.session.add(twin)
        return self._commit_and_refresh(twin)

    def get_twin_by_dtmi(self, dtmi: str) -> Optional[TwinNode]:
        return self.session.scalar(select(TwinNode).where(TwinNode.dtmi == dtmi))

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

    # ExtractedObject
    def add_extracted_object(
        self, file_object_id: int, kind: str, data: dict
    ) -> ExtractedObject:
        extracted = ExtractedObject(file_object_id=file_object_id, kind=kind, data=data)
        self.session.add(extracted)
        return self._commit_and_refresh(extracted)

    def list_extracted_objects(self) -> Iterable[ExtractedObject]:
        return self.session.scalars(select(ExtractedObject)).all()

    # ModelDocument
    def add_model_document(
        self, name: str, content: str, dtmi: Optional[str] = None
    ) -> ModelDocument:
        doc = ModelDocument(name=name, content=content, dtmi=dtmi)
        self.session.add(doc)
        return self._commit_and_refresh(doc)

    def list_model_documents(self) -> Iterable[ModelDocument]:
        return self.session.scalars(select(ModelDocument)).all()

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
