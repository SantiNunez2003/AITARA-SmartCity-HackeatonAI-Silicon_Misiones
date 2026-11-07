# T09 — Dividir App.jsx

## Objetivo
Separar `frontend/src/App.jsx` (más de 2.000 líneas) en componentes por vista, sin cambiar el comportamiento.

## Contexto
Un único archivo concentra mapa, escenarios, ranking, Analista y estado global. Cualquier cambio en la interfaz toca el mismo archivo, lo que impide trabajar en paralelo.

## Archivos permitidos
- `frontend/src/`

## Qué hacer
1. Crear un cliente de API (`frontend/src/api.js`) con la dirección base configurable por variable de entorno de Vite.
2. Extraer componentes, uno por vista: mapa, simulador de escenarios, panel de prioridades, ranking de zonas críticas, ficha de zona y Analista.
3. Dejar en `App.jsx` solo la composición y el estado compartido.

## Criterios de aceptación
- [ ] `App.jsx` queda por debajo de 300 líneas.
- [ ] La interfaz se ve y se comporta igual que antes.
- [ ] `npm run build` compila sin errores.

## Cómo verificar
```bash
cd frontend && npm run build && npm run dev
```
Recorrer todas las vistas y comparar con la versión anterior.

## Fuera de alcance
Cambios visuales o de contenido. Esta tarea va sola: no correr en paralelo con otra que toque `frontend/`.
