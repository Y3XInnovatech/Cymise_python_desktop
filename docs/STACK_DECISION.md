# Stack Decision (Phase 1)

**Chosen:** Desktop-first local app in Python.

## UI framework (locked)
- **PySide6 (Qt)**
- **Qt WebEngine** (`PySide6-QtWebEngine`) for embedding a local HTML/JS graph canvas

## Graph canvas (locked)
- **Cytoscape.js** bundled locally (no CDN)
- Two-way messaging between Python ⇄ JS for selection, edits, and validation state overlays

## Why
- Fastest path to a professional interactive graph UX (pan/zoom, styling, layouts).
- Keeps Python as the source of truth and makes the UI renderer easy to iterate.

## Notes
- Add runtime dependencies when implementing T9:
  - `PySide6`
  - `PySide6-QtWebEngine`
- Cytoscape.js should be vendored into `src/cymise/ui/web/vendor/`.
