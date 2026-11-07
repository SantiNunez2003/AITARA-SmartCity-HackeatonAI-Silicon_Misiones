# T03 — Deploy en un solo servicio

## Objetivo
Publicar AITARA en una URL pública, con la API y la interfaz en el mismo servicio.

## Contexto
- El frontend llama a `/api/...` mediante el proxy de Vite, que solo existe en desarrollo.
- `api.py` inicializa la base al importarse.
- No hay Dockerfile ni configuración de despliegue.

## Archivos permitidos
- `api.py`
- `Dockerfile` (nuevo)
- `.dockerignore` (nuevo)
- `tests/test_deploy.py` (nuevo)
- `README.md` (solo la sección de despliegue)
- `src/warehouse/db.py` (solo si hay que corregir un error de concurrencia reproducido, sin cambiar datos ni lógica)

## Qué hacer
1. En `api.py`, mover la inicialización de la base a un evento de arranque (`lifespan`) en lugar de hacerla al importar el módulo.
2. En `api.py`, servir `frontend/dist` como archivos estáticos en `/`, sin romper las rutas `/api/...`. Si `frontend/dist` no existe, la API tiene que seguir funcionando.
3. Crear un `Dockerfile` en dos etapas:
   - etapa 1: Node, `npm ci` y `npm run build` en `frontend/`;
   - etapa 2: Python 3.12, instala `requirements.txt`, copia el código y `frontend/dist`, y levanta `uvicorn api:app --host 0.0.0.0 --port $PORT`.
4. Crear `.dockerignore` (excluir `node_modules`, `.venv`, `.env`, bases locales).
5. Desplegar en Render (plan gratis, runtime Docker, desde la URL pública del repo y con deploy manual). `GEMINI_API_KEY` se carga como secreto del servicio, nunca en el repo. Hugging Face Spaces queda descartado: Docker ahora requiere plan pago. No hace falta `render.yaml`. La creación del servicio la hace Joaquín con su cuenta.
6. Documentar en el README cómo desplegar. La URL resultante se agrega después del primer deploy.
7. Agregar `tests/test_deploy.py`: la API responde con el arranque por `lifespan`, y las rutas `/api/...` no quedan tapadas por los estáticos.
8. Comprobar pedidos simultáneos (la interfaz hace tres en paralelo al cargar y todos comparten una conexión a DuckDB).

## Criterios de aceptación
- [ ] `docker build` y `docker run` levantan la app en local y la interfaz carga datos desde `/api`.
- [ ] La URL pública muestra la interfaz y responde `/api/status`.
- [ ] Sin `GEMINI_API_KEY`, la app funciona en modo respaldo.
- [ ] Los tests siguen pasando.

## Cómo verificar
```bash
docker build -t aitara .
docker run -p 8000:8000 -e PORT=8000 aitara
# abrir http://localhost:8000 y http://localhost:8000/api/status
```

## Fuera de alcance
Cambios de lógica del motor, del Analista o de la interfaz.

## Revisión
Por decisión de Joaquín, la implementa Codex para priorizar su uso, así que la revisan los críticos de Claude.
