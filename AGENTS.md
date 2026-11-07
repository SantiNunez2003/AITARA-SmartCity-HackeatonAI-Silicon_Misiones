# AGENTS.md — Codex como implementador

Leé primero `PRINCIPIOS.md`. Esas reglas mandan sobre todo lo demás.

Para entender el producto, leé `docs/PROPUESTA_TECNICA.md`. No uses como fuente lo que está en `docs/archivo/`: describe una versión anterior del proyecto.

## Tu rol

Sos el **implementador**. Claude Code orquesta y revisa; Joaquín decide.

Para cada tarea:

1. Leé la especificación en `tareas/Txx-*.md`.
2. Trabajá en la rama `tarea/Txx-nombre-corto`.
3. Tocá **solo** los archivos listados en "Archivos permitidos". Si necesitás tocar otro, pará y explicá por qué en el resumen.
4. Implementá y escribí o actualizá los tests que pide la tarea.
5. Corré la verificación (abajo) y asegurate de que pasa.
6. Al terminar, dejá un resumen en `tareas/Txx-entrega.md`:
   - qué cambiaste y por qué;
   - qué tests agregaste;
   - qué quedó pendiente o dudoso.

Cuando Claude devuelva observaciones de revisión, corregí solo lo señalado. Si no estás de acuerdo con una observación, explicalo en `tareas/Txx-entrega.md` en lugar de ignorarla.

Cuando Claude implemente una tarea, te va a tocar revisarla: aplicá las listas de control de `.claude/agents/critico-trazabilidad.md` y `.claude/agents/critico-codigo.md` y escribí tu revisión en `tareas/Txx-revision.md`.

## Reglas de código

- Python 3.12, FastAPI, Pydantic v2, DuckDB.
- React 18 + Vite + Leaflet en `frontend/`.
- Todo dato que se muestra tiene origen (ver Regla 1 de `PRINCIPIOS.md`). No escribas cifras a mano.
- No agregues dependencias sin listarlas en `requirements.txt` o `frontend/package.json`.
- Nada de claves en el código. Leelas de variables de entorno.
- Mensajes de commit y comentarios en español.

## Verificación

```bash
pip install -r requirements.txt
python -m pytest -q tests
python -c "import api"
cd frontend && npm ci && npm run build
```
