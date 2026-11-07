# T03 — Entrega

- La inicialización de DuckDB, motor y agentes se realiza en el lifespan; el frontend compilado se monta después de las rutas API solo si existe.
- Se agregaron Dockerfile multi-etapa, .dockerignore y las instrucciones de Render.
- Se agregó `tests/test_deploy.py` para estado, lista de incidentes y 404 de API usando el lifespan.
- En la ronda de corrección, DuckDB usa un cursor por llamada a `execute` y `df`; SQLite protege ambas operaciones con `RLock`, sin cambiar consultas ni firmas.
- El respaldo de `/api/evaluate` usa `SimpleNamespace` y conserva la franja solicitada. Se quitó `chmod 777` del Dockerfile.
- Se agregaron pruebas de 200 pedidos simultáneos con 16 hilos y de fallo en el informe del Analista. Se verificó que `risk_model.py` y `analista.py` no usan `db.con` directamente.
- `python -m py_compile src/warehouse/db.py api.py tests/test_deploy.py` pasó. `python -m pytest -q tests` y `python -c "import api"` fallaron por incompatibilidad local de FastAPI y Starlette (`Router.__init__` no acepta `on_startup`); los tests nuevos no pudieron ejecutarse localmente.
- En la verificación anterior, `npm run build` falló por acceso denegado al resolver la configuración; `npm ci` falló por permisos de la caché y dejó `frontend/node_modules` posiblemente incompleto. `docker build` falló por acceso denegado a la configuración de Docker.
- El orquestador reprodujo en Docker el error de concurrencia con 16 hilos: antes hubo 145 de 400 pedidos correctos; después, 400 de 400 en cada una de tres corridas. También verificó el build, el arranque, el modo sin clave y los tests.
- En la segunda ronda se corrigió el respaldo del informe para indicar que no está disponible, se amplió su prueba, se excluyeron los archivos `.env` anidados del contexto Docker y se agregó `exec` al arranque de Uvicorn.
- Pendientes: probar la interfaz en el navegador y obtener la URL pública. La creación del servicio corresponde a Joaquín.
