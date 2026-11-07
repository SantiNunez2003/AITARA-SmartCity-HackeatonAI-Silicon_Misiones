# T11 — API y README sin cifras ni promesas a mano

## Objetivo
Que `/api/status`, `/api/strategic` y el README solo afirmen lo que sale de los datos o del motor, y lo que dice la ficha.

## Depende de
T04 (prioridades).

## Contexto
- `/api/status` devuelve una latencia fija, un modo "Sincronizado con Medios Locales y Red Vial" y una lista de fuentes escrita a mano.
- `/api/strategic` tiene cifras, causas y obras escritas a mano ("32 min promedio", "34 siniestros anuales", "cota topográfica baja").
- `/api/evaluate` devuelve `corredor_desvio`, con una ruta escrita a mano y `capacidad_remanente_pct: 64`.
- El README promete anticipación de 30 a 60 minutos y despacho de inspectores y conos, y explica cómo levantar la consola de Streamlit que T04 elimina.

## Archivos permitidos
- `api.py` (salvo `/api/ask`)
- `src/warehouse/db.py` (solo `get_pipeline_status`)
- `README.md`
- `tests/`

## Qué hacer
1. `/api/status`: quitar la latencia fija y el texto de modo. `fuentes_activas` se calcula con las fuentes presentes en la base. Los totales siguen saliendo de la base.
2. `/api/strategic`:
   - los indicadores salen de la base y del motor: cantidad de incidentes, de nodos y de prioridades de nivel crítico para el escenario de referencia;
   - eliminar el indicador de demora evitada;
   - el ranking se arma con las `Prioridad` del motor: nodo, coordenadas, nivel, riesgo estructural, factor de mayor aporte y cantidad de incidentes de evidencia;
   - eliminar `causa_raiz`, `frecuencia` y `obra_recomendada`: no tienen dato que los respalde;
   - declarar en la respuesta qué escenario de referencia se usó.
3. `/api/evaluate`: eliminar `corredor_desvio`.
4. `api.py`: reemplazar "Copiloto Táctico" y cualquier vocabulario prohibido por `PRINCIPIOS.md` en título y descripción.
5. `README.md`: reescribir visión, caso piloto, puesta en marcha y estructura según `PRINCIPIOS.md` y `docs/PROPUESTA_TECNICA.md`. Conservar equipo y despliegue.

## Criterios de aceptación
- [ ] `/api/strategic` cambia si cambian los incidentes o el resultado del motor.
- [ ] Test: ninguna respuesta contiene `latencia_consulta_ms`, `corredor_desvio`, `causa_raiz` ni `obra_recomendada`.
- [ ] El README no promete anticipación a 30–60 minutos ni despacho, y sus comandos funcionan.
- [ ] Los tests pasan.

## Cómo verificar
```bash
python -m pytest -q tests
grep -niE "despacho|patrulla|conos|baliza|inspectores|streamlit|T\+30" README.md api.py   # no debe devolver nada
```

## Fuera de alcance
- La interfaz, que adapta T06 a estas respuestas.
- Rutas alternativas calculadas sobre el grafo vial: la propuesta las incluye en el prototipo, pero requieren una tarea propia, que queda pendiente.
- El cálculo del riesgo (T07).
