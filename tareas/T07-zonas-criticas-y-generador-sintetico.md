# T07 — Zonas críticas calculadas y generador sintético

## Objetivo
Que el riesgo estructural y el ranking de zonas críticas se calculen a partir de los incidentes, y que exista un generador de datos simulados declarados.

## Contexto
- `src/warehouse/db.py` carga a mano 7 nodos con `historical_incident_score` y `drainage_risk_level` fijos.
- Solo hay 12 incidentes reales, insuficientes para estimar patrones.

## Archivos permitidos
- `src/ingesta/generador_sintetico.py` (nuevo)
- `src/warehouse/db.py`
- `src/engine/risk_model.py`
- `data/simulado/` (nuevo)
- `tests/`

## Qué hacer
1. **Generador sintético** (`src/ingesta/generador_sintetico.py`):
   - genera partes policiales y del 911 para dos o tres años, con fecha, hora, intersección, tipo, vehículos y gravedad;
   - concentra eventos en vías principales y horas pico; respeta la ubicación de escuelas;
   - aplica efectos **declarados como parámetros** (por ejemplo, multiplicador por lluvia y por horario escolar);
   - usa una semilla fija para que sea reproducible;
   - marca todo con `origen = "simulado"`;
   - guarda el resultado en `data/simulado/`.
2. **Riesgo estructural calculado:**
   - asignar cada incidente (real y simulado) a su nodo más cercano;
   - intensidad por nodo ponderada por gravedad y confianza;
   - suavizado para que un nodo con un solo incidente grave no encabece el ranking;
   - eliminar los puntajes históricos cargados a mano.
3. **Ranking de zonas críticas** derivado de ese cálculo.
4. **Test de recuperación del método:** con el generador configurado con un efecto conocido de lluvia, el modelo estima un efecto cercano.

## Criterios de aceptación
- [ ] No quedan puntajes históricos escritos a mano en `db.py`.
- [ ] El ranking cambia si cambian los incidentes.
- [ ] Todo dato simulado tiene `origen = "simulado"`.
- [ ] El test de recuperación pasa.

## Cómo verificar
```bash
python -m src.ingesta.generador_sintetico
python -m pytest -q tests
```

## Fuera de alcance
El eje de fluidez y el feed con formato Waze (pueden quedar para una tarea posterior).
