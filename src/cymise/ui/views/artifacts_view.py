from __future__ import annotations

from typing import Callable, Optional

from PySide6 import QtWidgets

from cymise.graph.service import GraphService
from cymise.tools.launcher import launch_tool


class ArtifactsView(QtWidgets.QWidget):
    """Minimal artifact registry view."""

    def __init__(
        self,
        graph_service: GraphService,
        get_selected_dtmi: Optional[Callable[[], Optional[str]]] = None,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent)
        self.graph_service = graph_service
        self.get_selected_dtmi = get_selected_dtmi or (lambda: None)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Path", "Media Type", "Version", "Attached DTMI"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)

        add_btn = QtWidgets.QPushButton("Add File...")
        attach_btn = QtWidgets.QPushButton("Attach...")
        detach_btn = QtWidgets.QPushButton("Detach")
        refresh_btn = QtWidgets.QPushButton("Refresh")
        set_meta_btn = QtWidgets.QPushButton("Set Version/Type")
        edit_btn = QtWidgets.QPushButton("Edit")

        btn_row = QtWidgets.QHBoxLayout()
        for btn in (add_btn, attach_btn, detach_btn, set_meta_btn, edit_btn, refresh_btn):
            btn_row.addWidget(btn)
        btn_row.addStretch(1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(btn_row)
        layout.addWidget(self.table)

        add_btn.clicked.connect(self._add_file)
        attach_btn.clicked.connect(self._attach)
        detach_btn.clicked.connect(self._detach)
        refresh_btn.clicked.connect(self.refresh_from_store)
        set_meta_btn.clicked.connect(self._set_metadata)
        edit_btn.clicked.connect(self._edit_file)

    def refresh_from_store(self) -> None:
        files = self.graph_service.list_file_objects()
        self.table.setRowCount(len(files))
        for row, f in enumerate(files):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(f["id"])))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(f.get("path") or ""))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(f.get("media_type") or ""))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(f.get("version") or ""))
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(f.get("twin_dtmi") or ""))

    def _selected_file_id(self) -> Optional[int]:
        items = self.table.selectedItems()
        if not items:
            return None
        try:
            return int(items[0].text())
        except ValueError:
            return None

    def _add_file(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Artifact")
        if not path:
            return
        dtmi = self.get_selected_dtmi()
        self.graph_service.add_file_object(path=path, twin_dtmi=dtmi)
        self.refresh_from_store()

    def _attach(self) -> None:
        file_id = self._selected_file_id()
        if file_id is None:
            return
        dtmi = self.get_selected_dtmi()
        if not dtmi:
            dtmi, ok = QtWidgets.QInputDialog.getText(self, "Attach to Twin", "DTMI:")
            if not ok or not dtmi:
                return
        self.graph_service.attach_file(file_id, dtmi)
        self.refresh_from_store()

    def _detach(self) -> None:
        file_id = self._selected_file_id()
        if file_id is None:
            return
        self.graph_service.detach_file(file_id)
        self.refresh_from_store()

    def _set_metadata(self) -> None:
        file_id = self._selected_file_id()
        if file_id is None:
            return
        version, _ = QtWidgets.QInputDialog.getText(self, "Set Version", "Version:")
        media_type, _ = QtWidgets.QInputDialog.getText(self, "Set Media Type", "Media Type:")
        self.graph_service.repo.update_file_object(
            file_id, version=version or None, media_type=media_type or None
        )
        self.refresh_from_store()

    def _edit_file(self) -> None:
        file_id = self._selected_file_id()
        if file_id is None:
            QtWidgets.QMessageBox.warning(self, "Edit", "Select a file to edit.")
            return
        row = self.table.currentRow()
        path_item = self.table.item(row, 1)
        if not path_item:
            return
        path = path_item.text()
        if not path:
            QtWidgets.QMessageBox.warning(self, "Edit", "Selected file has no path.")
            return
        tool = self._infer_tool(path)
        result = launch_tool(tool, path)
        if not result.ok:
            QtWidgets.QMessageBox.warning(self, "Edit", result.message)

    @staticmethod
    def _infer_tool(path: str) -> str:
        lower = path.lower()
        if lower.endswith(".fcstd"):
            return "freecad"
        if lower.endswith(".kicad_pcb") or lower.endswith(".kicad_sch"):
            return "kicad"
        return "default"
