# T06 — Entrega

- Se conservó la estructura de la interfaz, el mapa, las pestañas y el Analista. El panel presenta prioridades, riesgos, aportes y evidencia de la API; los registros simulados llevan una marca visible. La vista estratégica usa el escenario de referencia y sus campos actuales.
- Se retiraron el trazado de desvío, su leyenda y control, y la dotación: no existen en los contratos actuales. Las carpetas de fuentes se derivan de los incidentes, y los estados vacíos ya no muestran cifras de ejemplo.
- Tests: no se agregaron tests automatizados; se comprobó la sintaxis JSX con esbuild y se buscó el vocabulario indicado sin coincidencias.
- Pendiente: `node_modules/.bin/vite build` quedó bloqueado por la política de ejecución de PowerShell; con `vite.cmd build`, esbuild recibió «Acceso denegado» al leer el directorio superior en el sandbox. El orquestador debe verificar el build y el recorrido visual del escenario con lluvia y actividad escolar.
