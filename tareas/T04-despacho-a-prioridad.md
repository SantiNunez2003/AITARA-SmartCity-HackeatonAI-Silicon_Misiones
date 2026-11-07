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
- `api.py` (solo para adaptar las respuestas de `/api/evaluate`)
- `tests/`

## Qué hacer
1. En `src/contracts.py`:
   - eliminar `OrdenDespacho` y `dotacion_patrullas`;
   - crear `AporteFactor` (nombre del factor, aporte numérico, descripción breve generada a partir del dato);
   - crear `Evidencia` (id del incidente, fecha, tipo, fuente, url, origen real o simulado);
   - crear `Prioridad` (nodo, nivel, riesgo estructural, variación por escenario, lista de `AporteFactor`, lista de `Evidencia`).
2. En `risk_model.py`:
   - eliminar todos los textos fijos por `nodo_id`;
   - devolver una lista de `Prioridad` ordenada por riesgo;
   - cada `Prioridad` trae el aporte de cada factor (temporal, clima, topología, siniestralidad) tal como se calcula hoy;
   - la evidencia son los incidentes de la base cercanos a ese nodo.
3. Adaptar `/api/evaluate` para que devuelva prioridades.
4. Actualizar los tests: dejar de contar órdenes; verificar que cada prioridad tiene aportes y que los aportes explican el riesgo.

## Criterios de aceptación
- [ ] No existen `OrdenDespacho`, `dotacion_patrullas` ni textos de recomendación por nodo.
- [ ] Cada `Prioridad` trae aportes por factor y al menos la evidencia disponible para ese nodo.
- [ ] La suma o combinación de los aportes reproduce el riesgo informado.
- [ ] Los tests pasan.

## Cómo verificar
```bash
python -m pytest -q tests
grep -rniE "despacho|movil|móvil|patrulla|conos|baliza" src api.py   # no debe devolver nada
```

## Fuera de alcance
El Analista (T05) y la interfaz (T06). Si se rompen por el cambio de contrato, dejarlos compilando con el mínimo cambio y anotarlo en la entrega.
