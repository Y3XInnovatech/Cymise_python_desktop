from __future__ import annotations

from typing import Callable, Iterable, Optional

from PySide6 import QtCore, QtWidgets

from cymise.graph.service import GraphService
from cymise.ui.impact_logic import rank_and_filter_impacts, severity_bucket


class ImpactView(QtWidgets.QWidget):
    """Impact tab showing ranked impacts with filtering and graph highlighting."""

    def __init__(
        self,
        graph_service: GraphService,
        highlight_node: Callable[[str], None],
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.graph_service = graph_service
        self.highlight_node = highlight_node
        self._current_result: Optional[dict] = None

        self.artifact_combo = QtWidgets.QComboBox()
        self.kind_combo = QtWidgets.QComboBox()
        self.kind_combo.setEditable(False)

        self.high_cb = QtWidgets.QCheckBox("High")
        self.med_cb = QtWidgets.QCheckBox("Medium")
        self.low_cb = QtWidgets.QCheckBox("Low")
        for cb in (self.high_cb, self.med_cb, self.low_cb):
            cb.setChecked(True)
        self.show_propagated_cb = QtWidgets.QCheckBox("Show propagated")
        self.show_propagated_cb.setChecked(True)

        self.refresh_btn = QtWidgets.QPushButton("Compute Impact")
        self.message_label = QtWidgets.QLabel("")

        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["DTMI", "Severity", "Confidence", "Evidence"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel("Artifact:"))
        controls.addWidget(self.artifact_combo)
        controls.addWidget(QtWidgets.QLabel("Kind:"))
        controls.addWidget(self.kind_combo)
        controls.addWidget(QtWidgets.QLabel("Severity:"))
        controls.addWidget(self.high_cb)
        controls.addWidget(self.med_cb)
        controls.addWidget(self.low_cb)
        controls.addWidget(self.show_propagated_cb)
        controls.addStretch(1)
        controls.addWidget(self.refresh_btn)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.table)
        layout.addWidget(self.message_label)

        self.refresh_btn.clicked.connect(self.compute_impact)
        self.artifact_combo.currentIndexChanged.connect(self._on_artifact_changed)
        self.kind_combo.currentIndexChanged.connect(self._on_kind_changed)
        self.high_cb.stateChanged.connect(self._apply_filters)
        self.med_cb.stateChanged.connect(self._apply_filters)
        self.low_cb.stateChanged.connect(self._apply_filters)
        self.show_propagated_cb.stateChanged.connect(self._apply_filters)
        self.table.itemSelectionChanged.connect(self._on_row_selected)

        self.refresh_artifacts()

    def refresh_artifacts(self) -> None:
        files = self.graph_service.list_file_objects()
        self.artifact_combo.blockSignals(True)
        self.artifact_combo.clear()
        for f in files:
            label = f"{f['path']} (id={f['id']})"
            self.artifact_combo.addItem(label, f["id"])
        self.artifact_combo.blockSignals(False)
        self._populate_kinds()

    def _populate_kinds(self) -> None:
        file_id = self._selected_file_id()
        kinds: set[str] = set()
        if file_id is not None:
            extracted = self.graph_service.repo.list_extracted_objects_for_file(file_id)
            kinds = {obj.kind for obj in extracted if obj and getattr(obj, "kind", None)}
        self.kind_combo.blockSignals(True)
        self.kind_combo.clear()
        for kind in sorted(kinds):
            self.kind_combo.addItem(kind, kind)
        self.kind_combo.blockSignals(False)
        if kinds:
            self.kind_combo.setCurrentIndex(0)
        self._apply_filters()

    def compute_impact(self) -> None:
        file_id = self._selected_file_id()
        kind = self._selected_kind()
        if file_id is None or not kind:
            self._show_message("Select an artifact and kind to compute impact.")
            return
        try:
            result = self.graph_service.compute_impact_for_file(file_id, kind)
        except Exception as exc:  # non-fatal UI
            self._show_message(f"Impact computation failed: {exc}")
            self._current_result = None
            self._populate_table([])
            return

        if not result:
            self._show_message("Not enough revisions to compute impact.")
            self._current_result = None
            self._populate_table([])
            return

        self._current_result = result
        self._show_message(result.get("summary", ""))  # type: ignore[arg-type]
        self._apply_filters()

    def _apply_filters(self) -> None:
        if not self._current_result:
            self._populate_table([])
            return
        severity_filter = {
            name
            for name, cb in (
                ("high", self.high_cb),
                ("medium", self.med_cb),
                ("low", self.low_cb),
            )
            if cb.isChecked()
        }
        include_propagated = self.show_propagated_cb.isChecked()
        combined = list(self._current_result.get("impacted", [])) + list(
            self._current_result.get("propagated", [])
        )
        ranked = rank_and_filter_impacts(combined, severity_filter, include_propagated)
        self._populate_table(ranked)

    def _populate_table(self, records: Iterable[dict]) -> None:
        recs = list(records)
        self.table.setRowCount(len(recs))
        for row_idx, rec in enumerate(recs):
            dtmi = rec.get("dtmi", "") or ""
            severity = f"{rec.get('severity', 0):.2f}"
            confidence = f"{rec.get('confidence', 0):.2f}"
            evidences = rec.get("evidences", []) or []
            summary_parts = []
            for ev in evidences:
                kind = ev.get("kind") if isinstance(ev, dict) else None
                detail = ev.get("detail") if isinstance(ev, dict) else None
                if kind and detail:
                    summary_parts.append(f"{kind}: {detail}")
                elif kind:
                    summary_parts.append(kind)
            summary = "; ".join(summary_parts)

            self.table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(dtmi))
            self.table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(severity))
            self.table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(confidence))
            self.table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(summary))
            self.table.item(row_idx, 0).setData(QtCore.Qt.ItemDataRole.UserRole, rec)

    def _selected_file_id(self) -> Optional[int]:
        return self.artifact_combo.currentData(QtCore.Qt.ItemDataRole.UserRole)

    def _selected_kind(self) -> Optional[str]:
        return self.kind_combo.currentData(QtCore.Qt.ItemDataRole.UserRole)

    def _on_artifact_changed(self, _idx: int) -> None:
        self._populate_kinds()

    def _on_kind_changed(self, _idx: int) -> None:
        # auto-run when both selections exist
        if self._selected_file_id() is not None and self._selected_kind():
            self.compute_impact()

    def _on_row_selected(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        row_item = items[0]
        rec = row_item.data(QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(rec, dict) and rec.get("dtmi"):
            self.highlight_node(rec["dtmi"])

    def _show_message(self, text: str) -> None:
        self.message_label.setText(text)
