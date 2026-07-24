# app/main.py
import sys
import logging
from pathlib import Path

from PySide6 import QtWidgets, QtGui

from app.core.config.settings import Settings
from pydantic import ValidationError
from app.core.util.logging import setup_logging
from app.core.controller import MainController
from app.ui.main_window import MainWindow
from app.ui.theme import apply_dark_theme


def main() -> int:
    setup_logging(Path('logs'))
    logger = logging.getLogger(__name__)
    try:
        settings = Settings.load()
    except ValidationError as e:
        logger.error("Fehler in der Konfiguration: %s", e)
        return 1

    app = QtWidgets.QApplication(sys.argv)
    apply_dark_theme(app)
    app.setFont(QtGui.QFont("Segoe UI", 10))
    controller = MainController(settings)
    win = MainWindow(settings, controller, logger=logger.getChild('MainWindow'))
    win.show()
    return app.exec()

if __name__ == '__main__':
    sys.exit(main())
