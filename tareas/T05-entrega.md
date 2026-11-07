# Entrega T05

- Gemini usa por defecto `gemini-3.5-flash-lite` con clave y permite configurar `GEMINI_MODEL`; sin clave conserva el respaldo.
- El contexto y el respaldo presentan valores redondeados, niveles legibles y sí/no; el respaldo identifica nodos por nombre y resume las prioridades del motor. El informe resume hasta tres prioridades.
- Se ampliaron las pruebas de modelo, formato, control numérico, selección de nodos, ranking y resumen; se actualizó la expectativa integral.
- Verificación: `.venv/Scripts/python.exe -m pytest -q tests` (14 pruebas aprobadas).
- Pendiente: no se realizó una llamada real a Gemini; el modelo predeterminado sigue la indicación de la tarea.
