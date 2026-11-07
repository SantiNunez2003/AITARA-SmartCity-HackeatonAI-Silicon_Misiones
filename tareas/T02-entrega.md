# Entrega T02 — Dependencias y configuración

- Se declararon con versiones mínimas FastAPI, Uvicorn, python-dotenv, google-genai, pytest y httpx para instalar las dependencias solicitadas.
- DuckDB ya figuraba en `requirements.txt`. Se agregó `.env.example` con `GEMINI_API_KEY` vacía; `.env` continúa ignorado y el ejemplo no está ignorado.
- No se agregaron tests: la tarea no solicita tests nuevos y no se modificó lógica. Los existentes pasaron: `python -m pytest -q tests` (2 aprobados).
- Pendiente verificar la instalación limpia: `pip install -r requirements.txt` falló al consultar PyPI por un error de certificado SSL. El Python disponible es 3.11.9, no 3.12.
- `python -c "import api"` falló en el entorno existente: FastAPI 0.116.1 y Starlette 1.1.0 son incompatibles (`Router.__init__` rechaza `on_startup`). No se pudo comprobar la resolución en un entorno limpio.
- `npm ci` terminó usando una caché temporal; `npm run build` falló porque esbuild no pudo leer un directorio superior por acceso denegado ni resolver `vite.config.js`.

## Verificación del orquestador
Codex no pudo verificar por su sandbox y por el escudo web de Avast de la PC local. Claude repitió la verificación en un contenedor limpio `python:3.12-slim`: `pip install -r requirements.txt` instala todo, `import api` funciona con DuckDB y `pytest` da 2 aprobados. La incompatibilidad FastAPI/Starlette es solo del Python local de la PC; no aparece en un entorno limpio.
