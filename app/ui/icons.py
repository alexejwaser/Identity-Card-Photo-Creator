# app/ui/icons.py
"""Small embedded UI icons.

Icons are stored as base64 PNG strings and decoded at runtime with QtGui only
(no QtSvg, no external asset files), so they always work in the packaged app
without extra PyInstaller data files or plugins.
"""
from __future__ import annotations

import base64

from PySide6 import QtCore, QtGui

# Official GitHub mark, rendered to a 64x64 PNG in dark grey (#444).
_GITHUB_PNG_B64 = (
    "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"
)


def github_icon() -> QtGui.QIcon:
    """Return the GitHub mark as a QIcon."""
    data = QtCore.QByteArray(base64.b64decode(_GITHUB_PNG_B64))
    pix = QtGui.QPixmap()
    pix.loadFromData(data, "PNG")
    return QtGui.QIcon(pix)
