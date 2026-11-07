# T04, T11, T05 y T06 — Revisión conjunta

**Veredicto: sin bloqueantes abiertos.** Por pedido de Joaquín, para cuidar la cuota, hubo una sola pasada de críticos sobre las cuatro tareas, en vez de una por tarea. No se relanzaron después de las correcciones: el orquestador las verificó con pruebas.

## Bloqueantes resueltos
| Origen | Problema | Corrección |
|---|---|---|
| Inspección del orquestador | Sin `GEMINI_MODEL`, nunca se usaba Gemini | Modelo por defecto `gemini-3.5-flash-lite`, reemplazable por variable |
| Inspección del orquestador | El respaldo mostraba decimales largos y volcaba todos los nodos | Respaldo acorde a la pregunta y valores redondeados |
| Inspección del orquestador | El primer intento de T06 reescribió `App.jsx` de 2152 a 170 líneas | Rechazado y rehecho con edición en el lugar |
| Inspección del orquestador | Acentos dañados en código y README | Corregidos |
| Ambos críticos | La variación se mostraba como "×" siendo un porcentaje | Ahora se muestra como porcentaje con signo |
| Crítico de trazabilidad | "Modelos calibrados" sin calibración | Línea eliminada |

## Correcciones no bloqueantes
- XSS: el texto de Gemini se escapa antes de renderizarse.
- Control de números: detecta números pegados a letras ("500m") y listas falsas.
- Vocabulario: "Táctica", "Copiloto Táctico" y "Municipalidad de Posadas" (sugería un aval).

## Verificación en Docker (512 MiB)
- Imagen de 628 MB; 15 tests aprobados; 400 de 400 pedidos simultáneos correctos; unos 143 MiB de memoria.
- Navegador real (Chromium): las tres pestañas y el panel de análisis, sin errores de consola ni de API.

## Pendientes
- Gemini no se probó con una llamada real, porque no hay clave en este entorno.
- `src/engine/risk_model.py`: `or 0.5` y `or 2` inventan valores si faltan datos. Revisar en T07.
- `src/engine/analista.py`: el control valida números, no afirmaciones causales, nodo atribuido ni números en palabras. El respaldo elige plantilla por palabra clave, aunque usa datos calculados.
- `api.py`: CORS `*` con credenciales y `pregunta` sin límite de longitud.
- `data/silver/incidentes_posadas.jsonl`: `inc-pos-003` tiene severidad 3 (fatal), pero la nota informa una persona en terapia intensiva. Lo decide Joaquín.
- T07: el riesgo sigue apoyado en puntajes cargados a mano y no hay datos simulados.
- Rutas alternativas: la propuesta las incluye en el prototipo; se quitó la ruta escrita a mano y falta una tarea propia.
