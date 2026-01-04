from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for CyMiSE store."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TwinNode(Base):
    __tablename__ = "twin_nodes"
    __table_args__ = (UniqueConstraint("dtmi", name="uq_twin_nodes_dtmi"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dtmi: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    validation: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=None)

    outgoing_edges: Mapped[list["RelationshipEdge"]] = relationship(
        back_populates="source",
        foreign_keys="RelationshipEdge.source_id",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[list["RelationshipEdge"]] = relationship(
        back_populates="target",
        foreign_keys="RelationshipEdge.target_id",
        cascade="all, delete-orphan",
    )
    files: Mapped[list["FileObject"]] = relationship(
        back_populates="twin_node", cascade="all, delete-orphan"
    )


class RelationshipEdge(Base):
    __tablename__ = "relationship_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("twin_nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("twin_nodes.id", ondelete="CASCADE"), nullable=False
    )
    validation: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=None)

    source: Mapped["TwinNode"] = relationship(
        back_populates="outgoing_edges", foreign_keys=[source_id]
    )
    target: Mapped["TwinNode"] = relationship(
        back_populates="incoming_edges", foreign_keys=[target_id]
    )


class FileObject(Base):
    __tablename__ = "file_objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String, nullable=False)
    media_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    twin_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("twin_nodes.id", ondelete="SET NULL"), nullable=True
    )

    twin_node: Mapped[Optional["TwinNode"]] = relationship(back_populates="files")
    extracted_objects: Mapped[list["ExtractedObject"]] = relationship(
        back_populates="file_object", cascade="all, delete-orphan"
    )
    stitches: Mapped[list["StitchCandidate"]] = relationship(
        back_populates="file_object", cascade="all, delete-orphan"
    )


class ExtractedObject(Base):
    __tablename__ = "extracted_objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    file_object_id: Mapped[int] = mapped_column(
        ForeignKey("file_objects.id", ondelete="CASCADE"), nullable=False
    )

    file_object: Mapped["FileObject"] = relationship(back_populates="extracted_objects")
    stitches: Mapped[list["StitchCandidate"]] = relationship(
        back_populates="extracted_object", cascade="all, delete-orphan"
    )


class StitchCandidate(Base):
    __tablename__ = "stitch_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    file_object_id: Mapped[int] = mapped_column(
        ForeignKey("file_objects.id", ondelete="CASCADE"), nullable=False
    )
    extracted_object_id: Mapped[int] = mapped_column(
        ForeignKey("extracted_objects.id", ondelete="CASCADE"), nullable=False
    )

    dt_key: Mapped[str] = mapped_column(String, nullable=False)
    target_dtmi: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    confidence: Mapped[float] = mapped_column(default=0.5)
    rationale: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, nullable=False, default="candidate")
    # allowed: "candidate"|"accepted"|"rejected"

    file_object: Mapped["FileObject"] = relationship(back_populates="stitches")
    extracted_object: Mapped["ExtractedObject"] = relationship(back_populates="stitches")


class ModelDocument(Base):
    __tablename__ = "model_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    dtmi: Mapped[Optional[str]] = mapped_column(String, nullable=True)
