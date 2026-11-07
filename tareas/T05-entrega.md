# Entrega T05

- El Analista construye el contexto con el escenario, las prioridades, sus aportes y la evidencia asociada; el informe y el respaldo usan esos datos, identifican incidentes sin enlace y nodos sin evidencia. Las consultas sobre rutas alternativas indican que ese dato no está disponible.
- Gemini recibe el mismo contexto y sus respuestas se contrastan numéricamente con él; ante resultados inválidos o errores se utiliza el respaldo y se registra el problema. Se conservan los nombres públicos de los métodos.
- Se agregaron pruebas del respaldo, evidencia, ausencia de evidencia, normalización decimal y porcentual, rechazo de cifras inventadas y `/api/ask` sin clave. Se actualizó la comprobación de rutas del test integral.
- Verificación: `.venv/Scripts/python.exe -m pytest -q tests` (11 pruebas aprobadas); búsqueda de la especificación sin coincidencias.
- Pendiente: verificar un nombre de modelo Gemini válido con acceso a la API y configurarlo mediante `GEMINI_MODEL`; agregar esa variable a `.env.example` en una tarea que permita modificarlo.
