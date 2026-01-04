from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Optional

from cymise.graph.service import GraphService


@dataclass(slots=True)
class RevisionDiffResult:
    file_object_id: int
    kind: str
    old_extracted_object_id: int
    new_extracted_object_id: int
    dt_key_added: list[str]
    dt_key_removed: list[str]
    dt_key_unchanged: list[str]
    structural: dict
    summary: str


class RevisionDiffService:
    def __init__(self, graph_service: GraphService):
        self.graph_service = graph_service

    def diff_extracted_objects(
        self, old_id: int, new_id: int
    ) -> Optional[RevisionDiffResult]:
        repo = self.graph_service.repo
        old_obj = repo.get_extracted_object_by_id(old_id)
        new_obj = repo.get_extracted_object_by_id(new_id)

        if not old_obj or not new_obj:
            return None

        file_object_id = new_obj.file_object_id
        kind = new_obj.kind or old_obj.kind

        old_keys = self._extract_dt_keys(old_obj.data)
        new_keys = self._extract_dt_keys(new_obj.data)

        dt_key_added = sorted(new_keys - old_keys)
        dt_key_removed = sorted(old_keys - new_keys)
        dt_key_unchanged = sorted(old_keys & new_keys)

        structural = self._structural_diff(old_obj, new_obj)
        structural_summary = self._structural_summary(structural)

        summary = f"dt_keys +{len(dt_key_added)} -{len(dt_key_removed)}, structural: {structural_summary}"

        return RevisionDiffResult(
            file_object_id=file_object_id,
            kind=kind,
            old_extracted_object_id=old_obj.id,
            new_extracted_object_id=new_obj.id,
            dt_key_added=dt_key_added,
            dt_key_removed=dt_key_removed,
            dt_key_unchanged=dt_key_unchanged,
            structural=structural,
            summary=summary,
        )

    def _extract_dt_keys(self, data: Any) -> set[str]:
        if not isinstance(data, dict):
            return set()
        keys = data.get("dt_keys") or []
        return {k for k in keys if isinstance(k, str)}

    def _structural_diff(self, old_obj, new_obj) -> dict:
        if old_obj.kind != new_obj.kind:
            return {"kind_mismatch": {"old": old_obj.kind, "new": new_obj.kind}}

        kind = new_obj.kind
        old_data = old_obj.data if isinstance(old_obj.data, dict) else {}
        new_data = new_obj.data if isinstance(new_obj.data, dict) else {}

        if kind == "kicad_ecad":
            return self._structural_diff_kicad(old_data, new_data)
        if kind == "freecad_tree":
            return self._structural_diff_freecad(old_data, new_data)

        return self._structural_diff_hash(old_data, new_data)

    def _structural_diff_kicad(self, old_data: dict, new_data: dict) -> dict:
        old_components = self._component_identities(
            old_data.get("components") or old_data.get("parts") or []
        )
        new_components = self._component_identities(
            new_data.get("components") or new_data.get("parts") or []
        )

        old_nets = self._net_identities(old_data.get("nets") or [])
        new_nets = self._net_identities(new_data.get("nets") or [])

        return {
            "components_added": sorted(new_components - old_components),
            "components_removed": sorted(old_components - new_components),
            "nets_added": sorted(new_nets - old_nets),
            "nets_removed": sorted(old_nets - new_nets),
        }

    def _component_identities(self, components: Any) -> set[str]:
        identities: set[str] = set()
        if not isinstance(components, list):
            return identities
        for comp in components:
            if isinstance(comp, dict):
                ref = comp.get("ref") or comp.get("reference")
                if isinstance(ref, str):
                    identities.add(ref)
                    continue
            if isinstance(comp, str):
                identities.add(comp)
            else:
                identities.add(str(comp))
        return identities

    def _net_identities(self, nets: Any) -> set[str]:
        identities: set[str] = set()
        if not isinstance(nets, list):
            return identities
        for net in nets:
            if isinstance(net, dict):
                name = net.get("name")
                if isinstance(name, str):
                    identities.add(name)
                    continue
            if isinstance(net, str):
                identities.add(net)
            else:
                identities.add(str(net))
        return identities

    def _structural_diff_freecad(self, old_data: dict, new_data: dict) -> dict:
        old_tree = old_data.get("tree") or []
        new_tree = new_data.get("tree") or []

        old_paths = self._flatten_tree_paths(old_tree)
        new_paths = self._flatten_tree_paths(new_tree)

        return {
            "tree_nodes_added": sorted(new_paths - old_paths),
            "tree_nodes_removed": sorted(old_paths - new_paths),
        }

    def _flatten_tree_paths(self, tree: Any) -> set[str]:
        paths: set[str] = set()

        def walk(node: Any, prefix: list[str]):
            if isinstance(node, dict):
                name = node.get("name") or node.get("label")
                children = node.get("children") or []
                current_prefix = prefix
                if isinstance(name, str):
                    current_prefix = prefix + [name]
                    paths.add("/".join(current_prefix))
                if isinstance(children, list):
                    for child in children:
                        walk(child, current_prefix)
                return

            if isinstance(node, list):
                for child in node:
                    walk(child, prefix)
                return

            if isinstance(node, str):
                paths.add("/".join(prefix + [node]))
                return

            # Fallback string identity for unexpected shapes
            paths.add("/".join(prefix + [str(node)]))

        walk(tree, [])
        return paths

    def _structural_diff_hash(self, old_data: Any, new_data: Any) -> dict:
        exclude_keys = {"tool_info", "errors", "timestamp", "created_at", "updated_at"}

        def clean(obj: Any):
            if isinstance(obj, dict):
                return {
                    k: clean(v)
                    for k, v in obj.items()
                    if k not in exclude_keys
                }
            if isinstance(obj, list):
                return [clean(v) for v in obj]
            return obj

        def digest(obj: Any) -> str:
            try:
                normalized = json.dumps(clean(obj), sort_keys=True, separators=(",", ":"))
                return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            except Exception:
                fallback = str(obj)
                return hashlib.sha256(fallback.encode("utf-8")).hexdigest()

        old_hash = digest(old_data)
        new_hash = digest(new_data)
        return {
            "data_hash_old": old_hash,
            "data_hash_new": new_hash,
            "hash_changed": old_hash != new_hash,
        }

    def _structural_summary(self, structural: dict) -> str:
        if not structural:
            return "no change"
        if "kind_mismatch" in structural:
            return "kind mismatch"
        if "hash_changed" in structural:
            return "hash changed" if structural.get("hash_changed") else "hash unchanged"
        if any(key.startswith("components") or key.startswith("nets") for key in structural):
            added = len(structural.get("components_added", [])) + len(
                structural.get("nets_added", [])
            )
            removed = len(structural.get("components_removed", [])) + len(
                structural.get("nets_removed", [])
            )
            return f"kicad Δ +{added}/-{removed}"
        if any(key.startswith("tree_nodes") for key in structural):
            added = len(structural.get("tree_nodes_added", []))
            removed = len(structural.get("tree_nodes_removed", []))
            return f"freecad Δ +{added}/-{removed}"
        return "structural diff"

    @staticmethod
    def to_dict(result: RevisionDiffResult) -> dict:
        return asdict(result)
