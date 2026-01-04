from __future__ import annotations

from cymise.graph.service import GraphService
from cymise.impact.service import ImpactService
from cymise.store.db import create_db, get_engine, get_session
from cymise.store.repo import StoreRepository


def setup_env(tmp_path):
    engine = get_engine(tmp_path / "impact.db")
    create_db(engine)
    session = get_session(engine)
    repo = StoreRepository(session)
    graph = GraphService(repo)
    impact = ImpactService(graph)
    return engine, session, repo, graph, impact


def test_direct_dtmi_impact(tmp_path):
    _engine, session, repo, graph, _impact = setup_env(tmp_path)
    try:
        file_obj = repo.add_file_object(path="doc.json", media_type="application/json")
        repo.add_extracted_object(file_object_id=file_obj.id, kind="kicad_ecad", data={"dt_keys": []})
        repo.add_extracted_object(
            file_object_id=file_obj.id,
            kind="kicad_ecad",
            data={"dt_keys": ["dtmi:com:example:Node;1"]},
        )

        result = graph.compute_impact_for_file(file_obj.id, kind="kicad_ecad")
        assert result is not None
        assert len(result["impacted"]) == 1
        impacted = result["impacted"][0]
        assert impacted["dtmi"] == "dtmi:com:example:Node;1"
        assert impacted["severity"] == 0.6
        assert impacted["confidence"] == 0.9
        assert impacted["evidences"][0]["kind"] == "dt_key_added"
    finally:
        session.close()


def test_stitch_mapping_lower_confidence(tmp_path):
    _engine, session, repo, graph, _impact = setup_env(tmp_path)
    try:
        file_obj = repo.add_file_object(path="doc.json", media_type="application/json")
        repo.add_extracted_object(file_object_id=file_obj.id, kind="kicad_ecad", data={"dt_keys": []})
        second = repo.add_extracted_object(
            file_object_id=file_obj.id,
            kind="kicad_ecad",
            data={"dt_keys": ["part-1"]},
        )
        repo.add_stitch_candidate(
            file_object_id=file_obj.id,
            extracted_object_id=second.id,
            dt_key="part-1",
            target_dtmi="dtmi:com:example:Mapped;1",
            status="accepted",
        )

        result = graph.compute_impact_for_file(file_obj.id, kind="kicad_ecad")
        assert result is not None
        impacted = result["impacted"][0]
        assert impacted["dtmi"] == "dtmi:com:example:Mapped;1"
        assert impacted["confidence"] == 0.6
    finally:
        session.close()


def test_structural_change_bumps_severity(tmp_path):
    _engine, session, repo, graph, _impact = setup_env(tmp_path)
    try:
        file_obj = repo.add_file_object(path="doc.json", media_type="application/json")
        repo.add_extracted_object(
            file_object_id=file_obj.id, kind="other", data={"dt_keys": [], "foo": 1}
        )
        repo.add_extracted_object(
            file_object_id=file_obj.id, kind="other", data={"dt_keys": ["dtmi:com:example:Struct;1"], "foo": 2}
        )

        result = graph.compute_impact_for_file(file_obj.id, kind="other")
        assert result is not None
        impacted = result["impacted"][0]
        assert impacted["severity"] == 0.8  # base 0.6 + structural bump
        kinds = {e["kind"] for e in impacted["evidences"]}
        assert "structural_change" in kinds
    finally:
        session.close()


def test_propagation_includes_neighbors(tmp_path):
    _engine, session, repo, graph, _impact = setup_env(tmp_path)
    try:
        graph.create_twin("dtmi:com:example:Root;1")
        graph.create_twin("dtmi:com:example:Neighbor;1")
        graph.create_relationship("dtmi:com:example:Root;1", "dtmi:com:example:Neighbor;1")

        file_obj = repo.add_file_object(path="doc.json", media_type="application/json")
        repo.add_extracted_object(file_object_id=file_obj.id, kind="kicad_ecad", data={"dt_keys": []})
        repo.add_extracted_object(
            file_object_id=file_obj.id,
            kind="kicad_ecad",
            data={"dt_keys": ["dtmi:com:example:Root;1"]},
        )

        result = graph.compute_impact_for_file(file_obj.id, kind="kicad_ecad", hops=1, directed=True)
        assert result is not None
        assert len(result["impacted"]) == 1
        assert len(result["propagated"]) == 1
        propagated = result["propagated"][0]
        assert propagated["dtmi"] == "dtmi:com:example:Neighbor;1"
        assert propagated["is_propagated"] is True
    finally:
        session.close()


def test_dedup_merges_evidences(tmp_path):
    _engine, session, repo, graph, _impact = setup_env(tmp_path)
    try:
        file_obj = repo.add_file_object(path="doc.json", media_type="application/json")
        repo.add_extracted_object(file_object_id=file_obj.id, kind="kicad_ecad", data={"dt_keys": []})
        second = repo.add_extracted_object(
            file_object_id=file_obj.id,
            kind="kicad_ecad",
            data={"dt_keys": ["alias-1", "alias-2"]},
        )
        for alias in ("alias-1", "alias-2"):
            repo.add_stitch_candidate(
                file_object_id=file_obj.id,
                extracted_object_id=second.id,
                dt_key=alias,
                target_dtmi="dtmi:com:example:Dedup;1",
                status="accepted",
            )

        result = graph.compute_impact_for_file(file_obj.id, kind="kicad_ecad")
        assert result is not None
        impacted = result["impacted"]
        assert len(impacted) == 1
        evidences = impacted[0]["evidences"]
        assert len(evidences) == 2
    finally:
        session.close()
