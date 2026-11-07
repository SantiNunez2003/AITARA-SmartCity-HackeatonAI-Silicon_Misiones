# T02 — Dependencias y configuración

## Objetivo
Que cualquier persona pueda clonar el repo e instalar y levantar el proyecto sin errores.

## Contexto
- `requirements.txt` no incluye `fastapi`, `uvicorn`, `python-dotenv` ni `google-genai`, que el código sí usa.
- (Ya resuelto en la rama de setup: `docs/` dejó de estar en `.gitignore`.)
- No hay `.env.example` que documente las variables de entorno.

## Archivos permitidos
- `requirements.txt`
- `.gitignore`
- `.env.example` (nuevo)

## Qué hacer
1. Agregar a `requirements.txt` las dependencias faltantes, con versión mínima: `fastapi`, `uvicorn[standard]`, `python-dotenv`, `google-genai`, `pytest`, `httpx`.
2. Crear `.env.example` con `GEMINI_API_KEY=` vacía y un comentario breve por variable.

## Criterios de aceptación
- [ ] En un entorno limpio, `pip install -r requirements.txt` instala todo.
- [ ] `python -c "import api"` funciona.
- [ ] `python -m pytest -q tests` pasa.
- [ ] `.env` sigue ignorado; `.env.example` se versiona.

## Cómo verificar
```bash
python -m venv /tmp/venv-aitara && . /tmp/venv-aitara/bin/activate
pip install -r requirements.txt
python -c "import api" && python -m pytest -q tests
```

## Fuera de alcance
Cambios de lógica en cualquier módulo.
