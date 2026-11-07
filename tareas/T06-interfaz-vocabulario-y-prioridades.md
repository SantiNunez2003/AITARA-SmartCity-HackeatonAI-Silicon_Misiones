# T06 — Interfaz: vocabulario y prioridades

## Objetivo
Que la interfaz muestre prioridades justificadas y use el vocabulario de la ficha.

## Contexto
- `frontend/src/App.jsx` muestra "Mapa Operativo y Despacho", "Análisis de Corredores y Despacho Táctico", "Órdenes de Despacho Táctico" y una cantidad de móviles.
- Después de T04, `/api/evaluate` devuelve prioridades con aportes y evidencia.

## Archivos permitidos
- `frontend/src/App.jsx`
- `frontend/src/components/` (componentes nuevos si hacen falta)
- `frontend/src/index.css`

## Qué hacer
1. Reemplazar textos de despacho según la tabla de vocabulario de `PRINCIPIOS.md`.
2. Reemplazar el panel de órdenes por un panel de **prioridades**: nodo, nivel, aporte de cada factor (barra o lista) y evidencia con enlace a la noticia.
3. Mostrar una marca visible **SIMULADO** en todo dato con origen simulado.
4. Quitar el control de "dotación de patrullas" del escenario.
5. Mostrar el riesgo estructural y la variación por escenario como dos valores distintos.
6. Adaptar la interfaz a lo que deja T11: pestaña estratégica con los campos nuevos, sin causas ni obras fijas, y sin el corredor de desvío del mapa ni los textos asociados.
7. Quitar del código de la interfaz las cifras y afirmaciones escritas a mano que queden. Un nodo sin evidencia tiene que decirlo.

## Criterios de aceptación
- [ ] No aparece "despacho", "móvil" ni "patrulla" en la interfaz.
- [ ] Cada prioridad muestra sus aportes y su evidencia.
- [ ] Los datos simulados se distinguen a simple vista.
- [ ] `npm run build` compila sin errores.

## Cómo verificar
```bash
cd frontend && npm run build
grep -niE "despacho|móvil|movil|patrulla" src/   # no debe devolver nada
```
Además, levantar la app y recorrer el escenario "mañana de lluvia en horario escolar".

## Fuera de alcance
Dividir `App.jsx` en componentes (T09), salvo los componentes nuevos que esta tarea necesite.
