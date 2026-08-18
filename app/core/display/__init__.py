"""Wartezimmer-Anzeige: Mini-Webserver, der den aktuellen Fotografier-Fortschritt
auf einem zweiten Geraet (Laptop/Tablet/Monitor vor dem Fotoraum) anzeigt."""

from .server import DisplayServer, local_addresses
from .state import build_snapshot, format_name
# Zuletzt: controller.py importiert aus .server und .state, die oben bereits
# geladen sind - so bleibt die Reihenfolge auch bei "import app.core.display"
# zyklenfrei.
from .controller import DisplayContext, DisplayController

__all__ = [
    "DisplayServer",
    "local_addresses",
    "build_snapshot",
    "format_name",
    "DisplayContext",
    "DisplayController",
]
