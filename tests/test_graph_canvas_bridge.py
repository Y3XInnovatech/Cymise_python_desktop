from __future__ import annotations

import pytest

pytest.importorskip("PySide6.QtCore")
pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("PySide6.QtTest")

from PySide6 import QtTest, QtWidgets

from cymise.ui.web.graph_canvas_bridge import GraphCanvasBridge


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


def test_bridge_select_element_emits_selection(monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    bridge = GraphCanvasBridge()
    spy = QtTest.QSignalSpy(bridge.selection_changed)

    bridge.select_element("node-1", "node")
    app.processEvents()

    assert spy.count() == 1
    args = spy.at(0)
    assert args[0] == "node-1"
    assert args[1] == "node"
