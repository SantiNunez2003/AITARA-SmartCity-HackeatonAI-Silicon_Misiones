# Tareas

Cada tarea tiene un archivo de especificación (`Txx-nombre.md`). Durante el trabajo se suman dos archivos:

- `Txx-entrega.md`: lo escribe quien implementa (qué cambió, tests, pendientes).
- `Txx-revision.md`: lo escriben los críticos (veredicto y observaciones).

## Flujo

```
Especificación (Claude) → Implementación (Codex, rama propia) → Tests
   → Críticos (Claude) → Correcciones (máximo 2 rondas) → Merge (Joaquín)
```

Quien implementa nunca revisa su propio trabajo: si implementa Codex, revisa Claude; si implementa Claude, revisa Codex.

## Orden y paralelismo

| # | Tarea | Implementa | Depende de | Puede ir en paralelo con |
|---|---|---|---|---|
| T02 | Dependencias y configuración | Codex | — | T03 |
| T03 | Deploy | Claude | — | T02, T04 |
| T04 | Despacho → Prioridad | Codex | — | T03 |
| T05 | Analista sin cifras inventadas | Codex | T04 | — |
| T06 | Interfaz: vocabulario y prioridades | Codex | T04 | T05 |
| T07 | Zonas críticas calculadas y generador sintético | Codex | T04 | T08 |
| T08 | Lector real con caché | Codex | T02 | T07 |
| T09 | Dividir `App.jsx` | Codex | T06 | Ninguna |
| T10 | Link del deploy en la ficha y PDF | Joaquín | T03 | — |

**Mínimo para la presentación:** T02 a T06 y T10.

## Plantilla de especificación

```markdown
# Txx — Título

## Objetivo
Una o dos frases.

## Contexto
Qué hay hoy y por qué hay que cambiarlo.

## Archivos permitidos
- ruta/archivo

## Qué hacer
1. ...

## Criterios de aceptación
- [ ] ...

## Cómo verificar
Comandos o pasos concretos.

## Fuera de alcance
Lo que no hay que tocar en esta tarea.
```
