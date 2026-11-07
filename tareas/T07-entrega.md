# Entrega T07

Se incorporó un generador reproducible de 1.552 partes sintéticos con lluvia y exposición declaradas. La carga se hace en bloque; al iniciar se asignan incidentes a nodos y se guarda la intensidad ponderada y suavizada. La normalización, los pesos de origen y los parámetros de escenarios están declarados. El ranking estratégico se ordena por riesgo estructural.

La API filtra incidentes reales por defecto y expone recuentos por origen; las prioridades conservan totales y hasta cinco evidencias, con prioridad para fuentes reales. La interfaz y el Analista distinguen los datos simulados. Se retiraron los valores sin fuente del modelo y el efecto de drenaje; la variación compara contra lluvia cero en la misma franja.

Se agregaron pruebas de recuperación (1,958 frente a 1,8, tolerancia 0,25), origen, filtrado, cambio de ranking, campos eliminados, límite de evidencia y suma de aportes. Se actualizaron pruebas de contratos existentes. Resultado: 18 pruebas aprobadas. La compilación de frontend pasó con `npm run build -- --configLoader runner`; el comando habitual falló porque esbuild no puede leer un directorio superior en el entorno restringido.

El cálculo usa tres años de exposición declarada para todos los nodos y una distancia máxima de 500 m; no equivale a exposición real observada. Los pesos expertos y los efectos sintéticos no constituyen calibración con datos reales. Ranking estructural de la muestra: N2, N3, N4, N7, N5, N6, N1.
