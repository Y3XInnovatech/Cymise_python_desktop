from __future__ import annotations

import sys
from typing import Optional

from PySide6 import QtWidgets

from cymise.graph.service import GraphService

from .main_window import MainWindow


def run_app(graph_service: GraphService, *, argv: Optional[list[str]] = None) -> int:
    """
    Launch the desktop UI shell.

    Core modules must not import UI implicitly; only call this from an
    interactive entrypoint.
    """

    args = argv if argv is not None else sys.argv
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(args)
    window = MainWindow(graph_service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(
        "This module is not intended to be run directly. " \
        "Import and call run_app(graph_service)."
    )
