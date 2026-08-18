"""Wartezimmer-Anzeige: Mini-Webserver, der den aktuellen Fotografier-Fortschritt
auf einem zweiten Geraet (Laptop/Tablet/Monitor vor dem Fotoraum) anzeigt."""

from .server import DisplayServer, local_addresses
from .state import build_snapshot, format_name

__all__ = ["DisplayServer", "local_addresses", "build_snapshot", "format_name"]
