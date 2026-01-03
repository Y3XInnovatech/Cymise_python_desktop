from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtWebChannel, QtWebEngineWidgets, QtWidgets

from cymise.graph.service import GraphService

from ..web.graph_canvas_bridge import GraphCanvasBridge


class GraphView(QtWidgets.QWidget):
    """Graph tab hosting the WebEngine canvas."""

    def __init__(self, graph_service: GraphService, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.graph_service = graph_service

        layout = QtWidgets.QVBoxLayout(self)
        self._view = QtWebEngineWidgets.QWebEngineView(self)
        layout.addWidget(self._view)

        self._bridge = GraphCanvasBridge()
        self._channel = QtWebChannel.QWebChannel(self._view.page())
        self._channel.registerObject("bridge", self._bridge)
        self._view.page().setWebChannel(self._channel)

        self._view.loadFinished.connect(self._on_load_finished)
        self._load_canvas()

    def _load_canvas(self) -> None:
        html_path = Path(__file__).resolve().parent.parent / "web" / "graph_canvas.html"
        url = QtCore.QUrl.fromLocalFile(str(html_path))
        self._view.setUrl(url)

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            return
        # Demonstrate Python -> JS call (not asserted in tests to avoid WebEngine flakiness).
        self._view.page().runJavaScript("window.cymiseReceive && window.cymiseReceive('pong')")
