from __future__ import annotations

from cymise.graph.service import GraphService
from cymise.revision_diff.service import RevisionDiffService
from cymise.store.db import create_db, get_engine, get_session
from cymise.store.repo import StoreRepository


def setup_env(tmp_path):
    engine = get_engine(tmp_path / "revision.db")
    create_db(engine)
    session = get_session(engine)
    repo = StoreRepository(session)
    graph = GraphService(repo)
    service = RevisionDiffService(graph)
    return engine, session, repo, graph, service


def test_dt_key_diff_added_removed(tmp_path):
    _engine, session, repo, _graph, service = setup_env(tmp_path)
    try:
        file_obj = repo.add_file_object(path="doc.json", media_type="application/json")
        old_obj = repo.add_extracted_object(
            file_object_id=file_obj.id, kind="kicad_ecad", data={"dt_keys": ["a", "b"]}
        )
        new_obj = repo.add_extracted_object(
            file_object_id=file_obj.id, kind="kicad_ecad", data={"dt_keys": ["b", "c"]}
        )

        result = service.diff_extracted_objects(old_obj.id, new_obj.id)
        assert result is not None
        assert result.dt_key_added == ["c"]
        assert result.dt_key_removed == ["a"]
        assert result.dt_key_unchanged == ["b"]
    finally:
        session.close()


def test_structural_diff_kicad_components(tmp_path):
    _engine, session, repo, _graph, service = setup_env(tmp_path)
    try:
        file_obj = repo.add_file_object(path="board.kicad_pcb", media_type="application/x-kicad")
        old_obj = repo.add_extracted_object(
            file_object_id=file_obj.id,
            kind="kicad_ecad",
            data={"components": [{"ref": "R1"}, {"ref": "R2"}], "nets": ["N1"]},
        )
        new_obj = repo.add_extracted_object(
            file_object_id=file_obj.id,
            kind="kicad_ecad",
            data={"components": [{"ref": "R2"}, {"ref": "R3"}], "nets": ["N1", "N2"]},
        )

        result = service.diff_extracted_objects(old_obj.id, new_obj.id)
        assert result is not None
        structural = result.structural
        assert structural["components_added"] == ["R3"]
        assert structural["components_removed"] == ["R1"]
        assert structural["nets_added"] == ["N2"]
        assert structural["nets_removed"] == []
    finally:
        session.close()


def test_structural_diff_freecad_tree(tmp_path):
    _engine, session, repo, _graph, service = setup_env(tmp_path)
    try:
        file_obj = repo.add_file_object(path="model.fcstd", media_type="application/x-freecad")
        old_obj = repo.add_extracted_object(
            file_object_id=file_obj.id,
            kind="freecad_tree",
            data={"tree": [{"name": "Body1", "children": [{"name": "Sketch1"}]}]},
        )
        new_obj = repo.add_extracted_object(
            file_object_id=file_obj.id,
            kind="freecad_tree",
            data={
                "tree": [
                    {"name": "Body1", "children": [{"name": "Sketch1"}, {"name": "Pad1"}]}
                ]
            },
        )

        result = service.diff_extracted_objects(old_obj.id, new_obj.id)
        assert result is not None
        structural = result.structural
        assert structural["tree_nodes_added"] == ["Body1/Pad1"]
        assert structural["tree_nodes_removed"] == []
    finally:
        session.close()


def test_diff_latest_for_file(tmp_path):
    _engine, session, repo, graph, _service = setup_env(tmp_path)
    try:
        file_obj = repo.add_file_object(path="doc.json", media_type="application/json")
        first = repo.add_extracted_object(
            file_object_id=file_obj.id, kind="kicad_ecad", data={"dt_keys": ["x"]}
        )
        second = repo.add_extracted_object(
            file_object_id=file_obj.id, kind="kicad_ecad", data={"dt_keys": ["x", "y"]}
        )

        result = graph.diff_latest_extraction_for_file(file_obj.id, kind="kicad_ecad")
        assert result is not None
        assert result["old_extracted_object_id"] == first.id
        assert result["new_extracted_object_id"] == second.id
        assert result["dt_key_added"] == ["y"]
        assert result["dt_key_removed"] == []
    finally:
        session.close()
