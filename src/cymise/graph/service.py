from __future__ import annotations

from collections import deque
from typing import Iterable, Optional

from cymise.store.models import RelationshipEdge, TwinNode
from cymise.store.repo import StoreRepository

from .types import GraphEdge, GraphNode


class GraphService:
    """Authoritative API for graph mutations and queries."""

    def __init__(self, repo: StoreRepository):
        self.repo = repo

    # Twin operations
    def create_twin(
        self,
        dtmi: str,
        display_name: Optional[str] = None,
        model_version: Optional[str] = None,
    ) -> GraphNode:
        twin = self.repo.add_twin(
            dtmi=dtmi, display_name=display_name, model_version=model_version
        )
        return self._to_node(twin)

    def update_twin(
        self,
        dtmi: str,
        display_name: Optional[str] = None,
        model_version: Optional[str] = None,
    ) -> GraphNode:
        twin = self.repo.update_twin(
            dtmi, display_name=display_name, model_version=model_version
        )
        if not twin:
            raise ValueError(f"Twin not found for dtmi={dtmi}")
        return self._to_node(twin)

    def delete_twin(self, dtmi: str) -> bool:
        return self.repo.delete_twin_by_dtmi(dtmi)

    def get_node(self, dtmi: str) -> Optional[GraphNode]:
        twin = self.repo.get_twin_by_dtmi(dtmi)
        if not twin:
            return None
        return self._to_node(twin)

    def list_nodes(self) -> list[GraphNode]:
        return [self._to_node(t) for t in self.repo.list_twins()]

    # Relationship operations
    def create_relationship(
        self, source_dtmi: str, target_dtmi: str, name: Optional[str] = None
    ) -> GraphEdge:
        source = self._require_twin(source_dtmi)
        target = self._require_twin(target_dtmi)
        edge = self.repo.add_relationship(source_id=source.id, target_id=target.id, name=name)
        return self._to_edge(edge, source, target)

    def get_outgoing_neighbors(self, dtmi: str) -> list[GraphNode]:
        twin = self._require_twin(dtmi)
        edges = self.repo.get_relationships_for_source(twin.id)
        neighbor_nodes = []
        for edge in edges:
            target = self.repo.get_twin_by_id(edge.target_id)
            if target:
                neighbor_nodes.append(target)
        return [self._to_node(n) for n in neighbor_nodes]

    def get_incoming_neighbors(self, dtmi: str) -> list[GraphNode]:
        twin = self._require_twin(dtmi)
        edges = self.repo.get_relationships_for_target(twin.id)
        neighbor_nodes = []
        for edge in edges:
            source = self.repo.get_twin_by_id(edge.source_id)
            if source:
                neighbor_nodes.append(source)
        return [self._to_node(n) for n in neighbor_nodes]

    def get_subgraph(
        self, start_dtmi: str, max_hops: int, directed: bool = True
    ) -> tuple[list[GraphNode], list[GraphEdge]]:

        if max_hops < 0:
            raise ValueError("max_hops must be non-negative")
        start = self._require_twin(start_dtmi)
        visited_nodes: dict[int, TwinNode] = {start.id: start}
        visited_edges: dict[int, RelationshipEdge] = {}
        queue: deque[tuple[int, int]] = deque()
        queue.append((start.id, 0))

        while queue:
            node_id, depth = queue.popleft()
            if depth >= max_hops:
                continue
            # Directed traversal (default): follow outgoing relationships only.
            # Undirected traversal: treat incoming edges as traversable for
            # visualization.
            outgoing = self.repo.get_relationships_for_source(node_id)
            incoming = self.repo.get_relationships_for_target(node_id)

            if directed:
                edges_to_walk = list(outgoing)
            else:
                edges_to_walk = list(outgoing) + list(incoming)

            for edge in edges_to_walk:
                if edge.id not in visited_edges:
                    visited_edges[edge.id] = edge

                if directed:
                    # Only traverse source -> target
                    neighbor_id = edge.target_id
                else:
                    # Traverse to the "other end" (visual neighborhood)
                    neighbor_id = (
                        edge.target_id if edge.source_id == node_id else edge.source_id
                    )

                if neighbor_id not in visited_nodes:
                    neighbor = self.repo.get_twin_by_id(neighbor_id)
                    if neighbor:
                        visited_nodes[neighbor_id] = neighbor
                        queue.append((neighbor_id, depth + 1))

        nodes = [self._to_node(twin) for twin in visited_nodes.values()]
        edges = [
            self._to_edge(
                edge,
                self._require_twin_by_id(edge.source_id),
                self._require_twin_by_id(edge.target_id),
            )
            for edge in visited_edges.values()
        ]
        return nodes, edges

    # Validation
    def set_node_validation(self, dtmi: str, payload: Optional[dict]) -> GraphNode:
        twin = self.repo.set_twin_validation(dtmi, payload)
        if not twin:
            raise ValueError(f"Twin not found for dtmi={dtmi}")
        return self._to_node(twin)

    def get_node_validation(self, dtmi: str) -> Optional[dict]:
        twin = self.repo.get_twin_by_dtmi(dtmi)
        if not twin:
            return None
        return twin.validation

    def set_edge_validation(self, edge_id: int, payload: Optional[dict]) -> GraphEdge:
        edge = self.repo.set_edge_validation(edge_id, payload)
        if not edge:
            raise ValueError(f"Edge not found for id={edge_id}")
        source = self._require_twin_by_id(edge.source_id)
        target = self._require_twin_by_id(edge.target_id)
        return self._to_edge(edge, source, target)

    def get_edge_validation(self, edge_id: int) -> Optional[dict]:
        edge = self.repo.get_relationship_by_id(edge_id)
        if not edge:
            return None
        return edge.validation

    def update_relationship_name(self, edge_id: int, name: Optional[str]) -> GraphEdge:
        edge = self.repo.update_relationship_name(edge_id, name)
        if not edge:
            raise ValueError(f"Edge not found for id={edge_id}")
        source = self._require_twin_by_id(edge.source_id)
        target = self._require_twin_by_id(edge.target_id)
        return self._to_edge(edge, source, target)

    # Documents
    def get_model_document(self, dtmi: str):
        return self.repo.get_model_document_by_dtmi(dtmi)

    # FileObjects
    def add_file_object(
        self,
        path: str,
        media_type: Optional[str] = None,
        version: Optional[str] = None,
        twin_dtmi: Optional[str] = None,
    ) -> dict:
        twin_id = None
        if twin_dtmi:
            twin = self.repo.get_twin_by_dtmi(twin_dtmi)
            if not twin:
                raise ValueError(f"Twin not found for dtmi={twin_dtmi}")
            twin_id = twin.id
        file_obj = self.repo.add_file_object(path=path, media_type=media_type, version=version, twin_id=twin_id)
        return self._file_to_dict(file_obj)

    def list_file_objects(self) -> list[dict]:
        file_objs = self.repo.list_file_objects()
        return [self._file_to_dict(f) for f in file_objs]

    def attach_file(self, file_id: int, twin_dtmi: str) -> dict:
        twin = self.repo.get_twin_by_dtmi(twin_dtmi)
        if not twin:
            raise ValueError(f"Twin not found for dtmi={twin_dtmi}")
        updated = self.repo.update_file_object(file_id, twin_id=twin.id)
        if not updated:
            raise ValueError(f"File not found for id={file_id}")
        return self._file_to_dict(updated)

    def detach_file(self, file_id: int) -> dict:
        updated = self.repo.update_file_object(file_id, twin_id=None)
        if not updated:
            raise ValueError(f"File not found for id={file_id}")
        return self._file_to_dict(updated)

    # Helpers
    def _require_twin(self, dtmi: str) -> TwinNode:
        twin = self.repo.get_twin_by_dtmi(dtmi)
        if not twin:
            raise ValueError(f"Twin not found for dtmi={dtmi}")
        return twin

    def _require_twin_by_id(self, twin_id: int) -> TwinNode:
        twin = self.repo.get_twin_by_id(twin_id)
        if not twin:
            raise ValueError(f"Twin not found for id={twin_id}")
        return twin

    def _edges_for_node(self, node_id: int) -> Iterable[RelationshipEdge]:
        outgoing = self.repo.get_relationships_for_source(node_id)
        incoming = self.repo.get_relationships_for_target(node_id)
        return list(outgoing) + list(incoming)

    @staticmethod
    def _to_node(twin: TwinNode) -> GraphNode:
        return GraphNode(
            dtmi=twin.dtmi,
            display_name=twin.display_name,
            model_version=twin.model_version,
            validation=twin.validation,
        )

    @staticmethod
    def _to_edge(edge: RelationshipEdge, source: TwinNode, target: TwinNode) -> GraphEdge:
        return GraphEdge(
            id=edge.id,
            name=edge.name,
            source_dtmi=source.dtmi,
            target_dtmi=target.dtmi,
            validation=edge.validation,
        )

    def _file_to_dict(self, file_obj):
        twin_dtmi = None
        if file_obj.twin_id:
            twin = self.repo.get_twin_by_id(file_obj.twin_id)
            twin_dtmi = twin.dtmi if twin else None
        return {
            "id": file_obj.id,
            "path": file_obj.path,
            "media_type": file_obj.media_type,
            "version": file_obj.version,
            "twin_dtmi": twin_dtmi,
        }
