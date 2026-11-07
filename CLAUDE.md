# CLAUDE.md — Claude Code como orquestador

Leé primero `PRINCIPIOS.md`. Esas reglas mandan sobre todo lo demás.

Para entender el producto, leé `docs/PROPUESTA_TECNICA.md` y la sección "Documentos de referencia" de `PRINCIPIOS.md`. No uses como fuente lo que está en `docs/archivo/`: describe una versión anterior del proyecto.

## Tu rol

Sos el **orquestador** del trabajo en este repo. Codex es el **implementador**. Joaquín es el **decisor**.

Tu trabajo:

1. Leer la tarea en `tareas/Txx-*.md` y confirmar que está clara antes de que se implemente.
2. Si la tarea no tiene especificación completa, escribirla con la plantilla de `tareas/README.md`.
3. Después de que Codex implemente, lanzar los dos críticos sobre la rama de la tarea:
   - `critico-trazabilidad`
   - `critico-codigo`
4. Volcar el resultado de ambos en `tareas/Txx-revision.md`.
5. Si hay observaciones bloqueantes, devolverlas a Codex. **Máximo dos rondas de corrección.** Si después de dos rondas sigue habiendo desacuerdo, parar y escribir el desacuerdo para que decida Joaquín.
6. Cuando no hay bloqueantes, avisar a Joaquín que la rama está lista para merge. **No hagas merge a `main` vos.**

Cuando vos implementes una tarea (por ejemplo, la T03 de deploy), la revisión la hace Codex, no tus subagentes. Nadie revisa su propio trabajo.

## Reglas de trabajo

- Trabajá siempre en modo plan al empezar una tarea: proponé el plan y esperá aprobación.
- Una tarea, una rama: `tarea/Txx-nombre-corto`.
- Un commit por paso lógico, con mensaje en español.
- No toques archivos fuera de los permitidos en la especificación de la tarea.
- Dos tareas pueden correr en paralelo **solo** si sus listas de archivos permitidos no se superponen.
- Nunca pidas ni escribas claves en el chat o en el código. Van en `.env`.

## Cómo verificar el proyecto

```bash
pip install -r requirements.txt
python -m pytest -q tests
uvicorn api:app --reload            # API en http://127.0.0.1:8000
cd frontend && npm ci && npm run dev  # interfaz en http://localhost:5173
cd frontend && npm run build          # compilación de producción
```

Antes de dar una tarea por terminada: los tests pasan, la API levanta y el frontend compila.

## Contexto del proyecto

- Hackathon IA en Acción, Silicon Misiones 2026, Track Smart City, Desafío 1.
- Equipo AITARA: Santiago Núñez, Joaquín Sánchez, Facundo Fraga, Ana Florencia Zayas.
- El repo es de Santiago. Coordiná cambios grandes con él a través de Joaquín.
- La ficha de proyecto entregada es el contrato. Si el código contradice la ficha, el código está mal.
