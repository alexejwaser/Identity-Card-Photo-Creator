# app/ui/theme.py
"""Forced dark theme.

The app always runs in a dark theme regardless of the OS setting, so the UI
(and the light-grey button icons) look consistent on every machine. Applied at
the QApplication level so dialogs and message boxes inherit it too.
"""
from __future__ import annotations

from PySide6 import QtGui, QtWidgets, QtCore


def apply_dark_theme(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    c = QtGui.QColor
    p = QtGui.QPalette()

    window = c(32, 33, 36)
    base = c(40, 41, 45)
    button = c(55, 57, 62)
    text = c(230, 230, 232)
    disabled = c(120, 122, 126)
    accent = c(42, 130, 218)

    p.setColor(QtGui.QPalette.Window, window)
    p.setColor(QtGui.QPalette.WindowText, text)
    p.setColor(QtGui.QPalette.Base, base)
    p.setColor(QtGui.QPalette.AlternateBase, window)
    p.setColor(QtGui.QPalette.ToolTipBase, base)
    p.setColor(QtGui.QPalette.ToolTipText, text)
    p.setColor(QtGui.QPalette.Text, text)
    p.setColor(QtGui.QPalette.Button, button)
    p.setColor(QtGui.QPalette.ButtonText, text)
    p.setColor(QtGui.QPalette.BrightText, c(255, 90, 90))
    p.setColor(QtGui.QPalette.Link, accent)
    p.setColor(QtGui.QPalette.Highlight, accent)
    p.setColor(QtGui.QPalette.HighlightedText, c(255, 255, 255))
    p.setColor(QtGui.QPalette.PlaceholderText, c(150, 152, 156))

    for role in (
        QtGui.QPalette.WindowText,
        QtGui.QPalette.Text,
        QtGui.QPalette.ButtonText,
    ):
        p.setColor(QtGui.QPalette.Disabled, role, disabled)

    app.setPalette(p)
