from __future__ import annotations

import pytest

from cymise.ui.web.graph_canvas_bridge import GraphCanvasBridge

QtCore = pytest.importorskip("PySide6.QtCore")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
QtTest = pytest.importorskip("PySide6.QtTest")



def test_bridge_ping_emits_pong_signal():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    bridge = GraphCanvasBridge()
    spy = QtTest.QSignalSpy(bridge.pong)

    response = bridge.ping("hello")
    app.processEvents()

    assert response == "pong:hello"
    assert spy.count() == 1
    # QSignalSpy in PySide6 exposes arguments via .at(index)
    assert spy.at(0)[0] == "pong:hello"
