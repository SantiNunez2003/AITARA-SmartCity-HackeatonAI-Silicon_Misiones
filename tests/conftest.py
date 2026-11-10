"""Configuración global de pytest: garantiza ejecución 100% offline sin llamadas reales a Gemini."""

import os
import pytest

# Definir claves vacías en os.environ ANTES de importar módulos evita que load_dotenv()
# (que por defecto tiene override=False) cargue las claves reales desde .env durante pytest.
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""


@pytest.fixture(autouse=True)
def _aislar_claves_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
