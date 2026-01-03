# BACKLOG — CyMiSE Phase 1 (Desktop-first Python)
## Baseline: DTDL v2 + v3 (Offline, No Azure Dependency)

This backlog is ordered to ensure that **DTDL graph creation + validation** is fully functional
*before* tool integrations. The DT graph is the primary product artifact.

Conventions:
- DT keys: `dt_<name>`
- DTDL versions supported: v2 and v3
- Validation split:
  - Stage A: Python pre-flight validation (fast feedback)
  - Stage B: .NET DTDLParser validation (authoritative, offline)
- CyMiSE extensions are validated **after** DTDL validation passes.

---

## EPIC A — DTDL Core (Authoritative Graph Foundation)

### T1 — Repo bootstrap, tooling, and dev scripts
**Goal**
- Ensure a repeatable local development workflow.

**Acceptance Criteria**
- [ ] Virtualenv setup documented
- [ ] `pip install -e .[dev]` works
- [ ] `pytest`, `ruff`, `black` all pass
- [ ] Makefile or `scripts/` with lint/test/format commands

---

### T2 — Runtime graph store schema (DTDL-first)
**Goal**
- Persist a DTDL-centric graph model with versioning.

**Acceptance Criteria**
- [ ] SQLite schema for:
  - TwinNode (DTDL Interface abstraction)
  - RelationshipEdge
  - FileObject (extension)
  - ExtractedObject (extension)
- [ ] Schema supports both DTDL v2 and v3 constructs
- [ ] Graph CRUD operations implemented

---

### T3 — Runtime Graph Service API
**Goal**
- Single authoritative API for all graph mutations and queries.

**Acceptance Criteria**
- [ ] Create/update/delete nodes and edges
- [ ] Query neighbors and subgraphs
  - Query: get_subgraph(start_dtmi, max_hops, directed=True)
  - Default directed=True follows relationship direction (source → target)
  - Optional directed=False returns an undirected neighborhood for visualization only
  - Unit test must prove directionality (A→B→C: starting at C returns only C when directed)
- [ ] Attach validation state to nodes/edges
- [ ] Persist all operations

---

### T4 — Python DTDL pre-flight validator
**Goal**
- Fast local validation before invoking .NET validator.

**Checks**
- JSON parse
- Required fields (`@id`, `@type`, `@context`)
- DTMI format sanity
- Duplicate IDs
- Unsupported custom extensions flagged

**Acceptance Criteria**
- [ ] Returns structured warnings/errors
- [ ] Does not block on minor issues

---

### T5 — .NET DTDLParser validator CLI (offline)
**Goal**
- Authoritative DTDL v2/v3 validation without Azure.

**Acceptance Criteria**
- [ ] Uses `DTDLParser.ModelParser`
- [ ] Accepts one or more model files/folders
- [ ] Outputs JSON:
  - model id
  - severity
  - message
  - path/location
- [ ] Non-zero exit code on fatal errors

---

### T6 — Python validator adapter
**Goal**
- Bridge Python ↔ .NET validator via subprocess.

**Acceptance Criteria**
- [ ] Unified `ValidationResult` model
- [ ] Graceful fallback if validator unavailable
- [ ] Errors attach to graph nodes by DTMI

---

### T7 — DTDL import pipeline
**Goal**
- Build runtime graph from standard DTDL JSON.

**Acceptance Criteria**
- [ ] Import multiple files
- [ ] Validate (T4 + T5)
- [ ] Create graph nodes and edges
- [ ] Store original model documents for round-trip export

---

### T8 — DTDL export pipeline
**Goal**
- Export runtime graph back to valid DTDL v2/v3 JSON.

**Acceptance Criteria**
- [ ] Export preserves original semantics
- [ ] Exported models pass validator
- [ ] Custom CyMiSE extensions excluded or namespaced

---

## EPIC B — DT Graph Builder UI

### T9 — Desktop UI shell (PySide6)

**Goal**
- Application frame with navigation and state, using PySide6.

**Implementation Notes (Option B)**
- Use **PySide6** for the desktop app.
- Use **Qt WebEngine (PySide6-QtWebEngine)** to embed a graph canvas implemented in HTML/JS.
- Graph renderer: **Cytoscape.js** (bundled locally, no CDN dependency).
- Python remains the source of truth; the WebView is a renderer/controller surface.

**Acceptance Criteria**
- [ ] App launches
- [ ] Tabs: Graph, Artifacts, Validation, Impact
- [ ] WebEngine loads a local `graph_canvas.html` from `src/cymise/ui/web/`
- [ ] Two-way messaging works (Python ⇄ JS) with a simple ping/pong test

**Files**
- `src/cymise/ui/app.py`
- `src/cymise/ui/main_window.py`
- `src/cymise/ui/web/graph_canvas.html`
- `src/cymise/ui/web/graph_canvas.js`
- `src/cymise/ui/web/graph_canvas_bridge.py`
---

### T10 — Graph canvas (DTDL graph visualization)

**Goal**
- Interactive DTDL graph visualization and selection using Cytoscape.js in Qt WebEngine.

**Acceptance Criteria**
- [ ] Render nodes and edges from runtime graph store
- [ ] Pan/zoom supported
- [ ] Click node/edge selects it and notifies Python (node_id / edge_id)
- [ ] Python can command JS to:
  - add/update/remove nodes/edges
  - apply style classes for validation state (ok/warn/error)
- [ ] No network dependency (Cytoscape bundled locally)

**Files**
- `src/cymise/ui/views/graph_view.py`
- `src/cymise/ui/web/graph_canvas.html`
- `src/cymise/ui/web/graph_canvas.js`
- `src/cymise/ui/web/graph_canvas_bridge.py`
---

### T11 — Graph editing UX

**Goal**
- Visual authoring of DTDL constructs with a pragmatic UX (Phase 1).

**Implementation Notes**
- Start with a **palette + forms** approach; add full drag/drop later if needed.
- Palette actions create nodes/edges in Python; JS re-renders graph.
- Node/edge property editing occurs in a right-hand panel (Qt widgets).

**Acceptance Criteria**
- [ ] Add Interface/Component node from palette
- [ ] Add relationship edge between two selected nodes
- [ ] Edit node properties (`@id`, `displayName`, key properties) and persist
- [ ] Save/load project state from SQLite
- [ ] Validation state badges appear on nodes/edges (driven by validator results)

**Files**
- `src/cymise/ui/views/graph_view.py`
- `src/cymise/ui/views/properties_panel.py`
- `src/cymise/graph/service.py`
---

### T12 — Validation panel
**Goal**
- Surface DTDL validation results to users.

**Acceptance Criteria**
- [ ] Errors/warnings grouped by model
- [ ] Clicking error highlights node/edge
- [ ] Clear distinction between DTDL errors and CyMiSE extension errors

---

## EPIC C — Artifact Integration (Extensions Layer)

### T13 — FileObject registry
**Goal**
- Register non-DTDL artifacts into the graph.

**Acceptance Criteria**
- [ ] Attach artifact files
- [ ] FileObject nodes created
- [ ] Versioning metadata stored

---

### T14 — External tool launcher
**Goal**
- Launch native tools from CyMiSE.

**Acceptance Criteria**
- [ ] “Edit” opens FreeCAD/KiCad via OS or configured path
- [ ] Errors logged and surfaced

---

### T15 — File watcher + debounce
**Goal**
- Detect artifact changes reliably.

**Acceptance Criteria**
- [ ] Save storms debounced
- [ ] Hash-based change detection
- [ ] Parse jobs queued asynchronously

---

### T16 — FreeCAD extractor v0
**Goal**
- Extract assembly tree + dt_ keys.

**Acceptance Criteria**
- [ ] ExtractedObject tree persisted
- [ ] dt_ keys detected
- [ ] Failures non-fatal

---

### T17 — KiCad extractor v0
**Goal**
- Extract ECAD structure.

**Acceptance Criteria**
- [ ] Components list
- [ ] Nets summary
- [ ] dt_ keys best-effort

---

## EPIC D — Stitching + Impact Reasoning

### T18 — Relationship Builder (stitching UI)
**Goal**
- Create cross-domain semantic links.

**Acceptance Criteria**
- [ ] Stitch dependency/synchronization/spatial
- [ ] Optional expressions stored
- [ ] Graph updated immediately

---

### T19 — Revision diff engine
**Goal**
- Detect what changed between revisions.

**Acceptance Criteria**
- [ ] dt_ key diffs
- [ ] Structural diffs

---

### T20 — Impact engine (review-only)
**Goal**
- Reason over graph changes.

**Acceptance Criteria**
- [ ] Impact traversal
- [ ] Suggestions generated
- [ ] Severity assigned

---

### T21 — Impact UI
**Goal**
- Communicate impact clearly.

**Acceptance Criteria**
- [ ] Ranked impacts
- [ ] Filter by artifact/severity
- [ ] Trace-back to graph nodes

---

## EPIC E — Snapshots, Compare, Packaging

### T22 — Snapshot product state
### T23 — Compare snapshots
### T24 — Export reports (Markdown)
### T25 — Packaging + sample project
