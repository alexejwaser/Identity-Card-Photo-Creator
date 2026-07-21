# tests/conftest.py
# Point settings.CONFIG_DIR at a throwaway directory for the whole test
# session, before any test module can import app.core.config.settings (which
# resolves CONFIG_DIR at import time). This prevents tests from ever writing
# to the real user config path (e.g. ~/LegicCardCreator/settings.json) if a
# test forgets to monkeypatch Settings.save().
import os
import tempfile

os.environ.setdefault("LEGICCARD_CONFIG_DIR", tempfile.mkdtemp(prefix="legiccard_test_config_"))
