# T07 — Revisión

**Veredicto: sin bloqueantes abiertos, después de una ronda de corrección.** Los críticos revisaron antes de esa ronda; las correcciones las verificó el orquestador con pruebas, sin relanzarlos, para cuidar la cuota.

## Bloqueantes resueltos
| Origen | Problema | Corrección |
|---|---|---|
| Trazabilidad | Datos simulados sumados a los reales, sin marca, en indicadores, ranking y Analista | Reales y simulados por separado, con marca SIMULADO y aviso sobre el ranking |
| Trazabilidad | `MULTIPLICADOR_CORREDOR` era una tabla por nodo disfrazada | Eliminado; las tasas salen de atributos compartidos |
| Código | El test de recuperación medía datos del generador, no lo cargado en la base | Estimación desde la base, con dos multiplicadores distintos |

## Otras correcciones
- Suavizado que impide que un solo incidente grave encabece el ranking, con test.
- Riesgos y variación redondeados.
- Zona crítica definida por riesgo estructural.
- Sin edades en los resúmenes de noticias.
- `inc-pos-003` corregido a severidad 2, según la nota original.

## Verificación en Docker (512 MiB)
- 20 tests aprobados; 400 de 400 pedidos simultáneos correctos; unos 158 MiB de memoria; imagen de 629 MB.
- Navegador real: pestañas y panel de análisis sin errores.
- Efecto de lluvia recuperado: 1,694 para un multiplicador de 1,8, y 1,212 para uno de 1,2.

## Límites que hay que declarar
- La recuperación valida el método de estimación con datos simulados. Los pesos del escenario siguen siendo criterio experto y no incorporan ese efecto.
- Con 12 incidentes reales y 1417 simulados, el ranking depende de los parámetros del generador y los riesgos estructurales quedan muy juntos. Demuestra el método; no describe la ciudad.
- `lanes` y `has_bus_stop`, además de los nodos, siguen cargados a mano en `db.py`, sin fuente declarada.
- Gemini no se probó con una llamada real.
