# T05 — Analista sin cifras inventadas

## Objetivo
Que todo lo que dice el Analista salga de los datos y resultados calculados, con o sin Gemini.

## Contexto
- La respuesta de respaldo en `src/engine/analista.py` busca palabras clave y devuelve textos con cifras inventadas ("34 siniestros anuales, 78 % motos", "pérdida de adherencia del 40 %", "64 % de capacidad libre", "87 % de criticidad", "cota topográfica baja").
- El prompt de Gemini pide tono "autoritativo" y "acción para móviles".

## Archivos permitidos
- `src/engine/analista.py`
- `api.py` (solo `/api/ask` y el informe)
- `tests/`

## Qué hacer
1. Construir un único **contexto de datos** por consulta: prioridades (de T04), escenario e incidentes relevantes. Todo lo que el Analista puede decir está ahí.
2. **Respaldo sin conexión:** reemplazar las respuestas por palabra clave por plantillas que se completan solo con valores del contexto (nodo, nivel, aportes, cantidad real de incidentes, enlaces).
3. **Prompt de Gemini:**
   - rol: analista que explica, no copiloto táctico;
   - usar solo los datos del contexto y citar los incidentes;
   - si un dato no está, decir que no está;
   - sin órdenes ni cantidades de recursos.
4. **Control de salida:** antes de devolver la respuesta de Gemini, verificar que cada número que menciona exista en el contexto. Si no, usar el respaldo.
5. Verificar que el nombre del modelo de Gemini existe; si la llamada falla, registrar el error en el log de forma visible.
6. Quitar de `tests/` las verificaciones de textos fijos, como el desvío por "San Lorenzo", y quitar de `analista.py` el vocabulario prohibido por `PRINCIPIOS.md`.

## Criterios de aceptación
- [ ] No queda ninguna cifra escrita a mano en `analista.py`.
- [ ] Test: el respaldo, para varias preguntas, solo menciona números presentes en el contexto.
- [ ] Test: una respuesta simulada de Gemini con un número inventado se rechaza y se usa el respaldo.
- [ ] Sin `GEMINI_API_KEY`, `/api/ask` responde con el respaldo.

## Cómo verificar
```bash
python -m pytest -q tests
grep -nE "[0-9]+ ?%|siniestros anuales|cota|sumidero" src/engine/analista.py   # no debe devolver texto fijo
```

## Fuera de alcance
La interfaz (T06) y el cálculo del riesgo (T07).
