# T03 — Revisión

**Veredicto: sin bloqueantes abiertos, después de dos rondas de corrección.** Los críticos revisaron antes de la ronda 2; esa ronda la verificó el orquestador con pruebas, sin relanzarlos.

## Reparto
Por decisión de Joaquín, implementó Codex y revisaron los críticos de Claude.

## Bloqueantes resueltos
| Ronda | Origen | Problema | Corrección |
|---|---|---|---|
| 1 | Prueba del orquestador | Con pedidos simultáneos, DuckDB rechazaba llamadas: 145 de 400 correctos | Cursor por llamada en `src/warehouse/db.py`: 400 de 400 en cuatro corridas |
| 1 | Prueba del orquestador | El respaldo de `/api/evaluate` importaba `InformeTurno`, inexistente, y daba error 500 | Respaldo sin esa clase, con test |
| 2 | Crítico de trazabilidad | El respaldo afirmaba "Condición normal" aunque lloviera | Ahora indica "No disponible", con test |

## Verificación en Docker (512 MiB)
- Build correcto; imagen de 1,04 GB; 5 tests aprobados.
- Interfaz en `/`, API en `/api`, y 404 en rutas `/api` inexistentes.
- Sin `GEMINI_API_KEY`: `/api/ask` responde en modo respaldo.
- Memoria: unos 140 MiB después de la carga.
- Arranque de unos 22 s con 0,1 CPU.
- Para pasar el escudo web de Avast de la PC local se usó un Dockerfile temporal fuera del repo. El `Dockerfile` versionado no contiene nada de eso.

## Menores sin resolver
- `tests/test_deploy.py`: sin `frontend/dist`, no cubre el montaje de estáticos (sí se comprobó en Docker). Tampoco cubre `/api/ask`, y un fallo del Analista queda oculto porque el respaldo responde 200.
- `api.py`: globales no declaradas a nivel de módulo, y la conexión no se cierra al apagar.
- `Dockerfile`: el contenedor corre como root.

## Pendientes
- Probar la interfaz en un navegador y obtener la URL pública.
- Preexistente, fuera de alcance (T04 a T07): cifras a mano en `/api/strategic`, `ordenes_despacho`, latencia fija y vocabulario de despacho. No poner el link en la ficha hasta resolverlo.
