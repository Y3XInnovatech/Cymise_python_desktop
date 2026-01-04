from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6 import QtCore, QtWidgets

from cymise.graph.service import GraphService


@dataclass
class ValidationRow:
    model_id: str
    severity: str
    message: str
    path: Optional[str]
    code: Optional[str]
    kind: str  # "node"|"edge"
    element_id: str
    category: str  # "dtdl"|"cymise"


class ValidationView(QtWidgets.QWidget):
    """Validation panel grouping issues by model."""

    issueActivated = QtCore.Signal(str, str)  # kind, element_id
    modelSelected = QtCore.Signal(str)

    def __init__(self, graph_service: GraphService, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.graph_service = graph_service
        self._model_groups: dict[str, list[ValidationRow]] = {}

        self.models_list = QtWidgets.QListWidget()
        self.issues_table = QtWidgets.QTableWidget(0, 5)
        self.issues_table.setHorizontalHeaderLabels(["Severity", "Message", "Path", "Code", "Category"])
        self.issues_table.horizontalHeader().setStretchLastSection(True)
        self.issues_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.issues_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        splitter = QtWidgets.QSplitter()
        splitter.addWidget(self.models_list)
        splitter.addWidget(self.issues_table)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(splitter)

        self.models_list.currentItemChanged.connect(self._on_model_selected)
        self.issues_table.itemDoubleClicked.connect(self._on_issue_activated)

    def refresh_from_store(self, graph_service: Optional[GraphService] = None) -> None:
        svc = graph_service or self.graph_service
        self._model_groups = extract_validation_groups(svc)
        self._populate_models()
        self.issues_table.setRowCount(0)

    def _populate_models(self) -> None:
        self.models_list.clear()
        for model_id, rows in sorted(self._model_groups.items()):
            errs = sum(1 for r in rows if r.severity == "error")
            warns = sum(1 for r in rows if r.severity == "warning")
            item = QtWidgets.QListWidgetItem(f"{model_id}  (E:{errs} W:{warns})")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, model_id)
            self.models_list.addItem(item)

    def _on_model_selected(self, current, _previous) -> None:
        if not current:
            return
        model_id = current.data(QtCore.Qt.ItemDataRole.UserRole)
        self.modelSelected.emit(model_id)
        rows = self._model_groups.get(model_id, [])
        self._populate_issues(rows)

    def _populate_issues(self, rows: list[ValidationRow]) -> None:
        self.issues_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            self.issues_table.setItem(idx, 0, QtWidgets.QTableWidgetItem(row.severity))
            self.issues_table.setItem(idx, 1, QtWidgets.QTableWidgetItem(row.message))
            self.issues_table.setItem(idx, 2, QtWidgets.QTableWidgetItem(row.path or ""))
            self.issues_table.setItem(idx, 3, QtWidgets.QTableWidgetItem(row.code or ""))
            self.issues_table.setItem(idx, 4, QtWidgets.QTableWidgetItem(row.category))
            # stash metadata
            self.issues_table.item(idx, 0).setData(QtCore.Qt.ItemDataRole.UserRole, row)

    def _on_issue_activated(self, item: QtWidgets.QTableWidgetItem) -> None:
        row = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(row, ValidationRow):
            self.issueActivated.emit(row.kind, row.element_id)


def extract_validation_groups(graph_service: GraphService) -> dict[str, list[ValidationRow]]:
    groups: dict[str, list[ValidationRow]] = {}

    for twin in graph_service.repo.list_twins():
        rows = _rows_from_payload(twin.validation, model_id=twin.dtmi, kind="node", element_id=twin.dtmi)
        if rows:
            groups.setdefault(twin.dtmi, []).extend(rows)

    for edge in graph_service.repo.list_relationships():
        source = graph_service.repo.get_twin_by_id(edge.source_id)
        target = graph_service.repo.get_twin_by_id(edge.target_id)
        model_id = source.dtmi if source else ""
        rows = _rows_from_payload(
            edge.validation,
            model_id=model_id,
            kind="edge",
            element_id=str(edge.id),
        )
        if rows:
            groups.setdefault(model_id or "unknown", []).extend(rows)

    return groups


def _rows_from_payload(
    payload: Optional[dict],
    *,
    model_id: str,
    kind: str,
    element_id: str,
) -> list[ValidationRow]:
    if not payload:
        return []
    issues = payload.get("issues", [])
    rows: list[ValidationRow] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        severity = (issue.get("severity") or "").lower()
        if severity not in ("error", "warning"):
            continue
        code = issue.get("code")
        category = _issue_category(code, payload)
        model = issue.get("model_id") or issue.get("modelId") or model_id
        rows.append(
            ValidationRow(
                model_id=model,
                severity=severity,
                message=issue.get("message") or "",
                path=issue.get("path"),
                code=code,
                kind=kind,
                element_id=element_id,
                category=category,
            )
        )
    return rows


def _issue_category(code: Optional[str], payload: dict) -> str:
    if payload.get("category") == "cymise":
        return "cymise"
    if code and (code.startswith("dt_") or code.startswith("cymise_")):
        return "cymise"
    return "dtdl"
