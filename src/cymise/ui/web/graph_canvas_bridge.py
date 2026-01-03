from __future__ import annotations

from PySide6 import QtCore


class GraphCanvasBridge(QtCore.QObject):
    """Qt bridge exposed to JS via QWebChannel."""

    pong = QtCore.Signal(str)

    @QtCore.Slot(str, result=str)
    def ping(self, payload: str) -> str:
        """Receive ping from JS and emit pong response."""
        message = f"pong:{payload}"
        self.pong.emit(message)
        return message
