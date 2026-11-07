# T04 — Reemplazar despacho por prioridad

## Objetivo
Que el motor entregue prioridades justificadas en lugar de órdenes de despacho, como dice la ficha.

## Contexto
- `src/contracts.py` define `OrdenDespacho` y `ParametrosEscenario.dotacion_patrullas`.
- `src/engine/risk_model.py` genera órdenes con instrucciones escritas a mano por `nodo_id` (conos, balizas, móviles).
- `tests/test_e2e_audit.py` verifica la cantidad de órdenes emitidas.

## Archivos permitidos
- `src/contracts.py`
- `src/engine/risk_model.py`
- `src/engine/analista.py` (solo el mínimo para que siga funcionando con el contrato nuevo)
- `src/warehouse/db.py` (solo para agregar el campo `origen` a los incidentes)
- `api.py` (solo `/api/evaluate`, `AskRequest` y los textos de despacho de su docstring)
- `tests/`
- `app.py` y `.streamlit/` (se eliminan)
- `requirements.txt` (solo quitar `streamlit`, `streamlit-folium` y `folium`)

## Qué hacer
1. En `src/contracts.py`:
   - eliminar `OrdenDespacho` y `dotacion_patrullas`;
   - quitar `desvio_sugerido` de `EvaluacionNodo`, y `ordenes_despacho` de `InformeOperativoAnalista`, que pasa a llevar `prioridades`;
   - crear `AporteFactor` (nombre del factor, aporte numérico, descripción breve generada a partir del dato);
   - crear `Evidencia` (id del incidente, fecha, tipo, fuente, url, origen real o simulado);
   - crear `Prioridad` (nodo, nivel, riesgo estructural, variación por escenario, riesgo del escenario, lista de `AporteFactor`, lista de `Evidencia`);
   - agregar `origen` a `IncidenteSilver`.
2. En `risk_model.py`:
   - eliminar todos los textos fijos por `nodo_id`, incluido el desvío sugerido, y los factores con afirmaciones sin dato ("siniestros de motovehículos");
   - devolver una lista de `Prioridad` ordenada por riesgo;
   - cada `Prioridad` trae el aporte de cada factor (temporal, clima, topología, siniestralidad): peso por dimensión, tal como se calcula hoy, sin cambiar pesos ni fórmulas;
   - la evidencia son los incidentes de la base a no más de una distancia declarada como constante, asignados al nodo más cercano. Un nodo sin incidentes cercanos devuelve lista vacía; no se inventa evidencia.
3. En `db.py`, agregar la columna `origen` a `silver_incident_history` con el mismo patrón idempotente que `fecha_evento`. Al cargar, usar el `origen` del registro y, si no lo trae, `real`: el archivo actual son noticias reales.
4. Adaptar `/api/evaluate` para que devuelva `prioridades` y deje de devolver `ordenes_despacho`. Mantener `nodos` hasta T06, porque lo usa el mapa.
5. Eliminar `app.py` y `.streamlit/`: es la consola anterior, no se publica y no se mantiene. Quitar sus dependencias de `requirements.txt`.
6. Actualizar los tests: dejar de contar órdenes; verificar que cada prioridad tiene aportes y que los aportes explican el riesgo.

## Criterios de aceptación
- [ ] No existen `OrdenDespacho`, `dotacion_patrullas` ni textos de recomendación por nodo.
- [ ] Cada `Prioridad` trae aportes por factor y al menos la evidencia disponible para ese nodo.
- [ ] La suma o combinación de los aportes reproduce el riesgo informado.
- [ ] Los tests pasan.

## Cómo verificar
```bash
python -m pytest -q tests
grep -niE "despacho|movil|móvil|patrulla|conos|baliza" src/contracts.py src/engine/risk_model.py api.py   # no debe devolver nada
```
`src/engine/analista.py` queda fuera de este control: lo limpia T05.

## Fuera de alcance
- El Analista (T05) y la interfaz (T06). Si se rompen por el cambio de contrato, dejarlos compilando con el mínimo cambio y anotarlo en la entrega. La interfaz puede quedar incompleta hasta T06: no se publica hasta entonces.
- `/api/status`, `/api/strategic` y `corredor_desvio` (T11).
- Los puntajes cargados a mano en `db.py` (T07).
