# AITARA — Propuesta técnica

Documento de referencia del producto. Las reglas obligatorias para el código están en `PRINCIPIOS.md`; si este documento y los principios no coinciden, mandan los principios.

## 1. Resumen

AITARA es un **sistema de soporte a decisiones (DSS)** para la movilidad urbana de Posadas. Integra fuentes territoriales, meteorológicas, de agenda urbana, de tránsito en tiempo real e incidentes reportados, y los organiza en una memoria única de la ciudad.

Opera sobre dos ejes:

- **Seguridad vial:** dónde, cuándo y bajo qué condiciones aumenta el riesgo de siniestros.
- **Fluidez:** dónde se forma congestión, cuándo se aparta de lo habitual y qué corredores absorben un desvío.

La inteligencia artificial se aplica en cuatro componentes: un **Lector** que estructura texto no estructurado, **modelos analíticos** de riesgo y fluidez, un agente **Investigador** que resuelve datos dudosos y un agente **Analista** que produce informes, responde consultas y redacta avisos. El sistema recomienda y explica; la decisión corresponde a la autoridad competente.

El prototipo combina datos públicos reales con datos simulados, identificados como tales, que representan fuentes institucionales a gestionar.

## 2. Definiciones

| Término | Definición |
| --- | --- |
| Incidente vial | Evento que altera la circulación (siniestro, corte, congestión anómala) con ubicación y momento identificables |
| Memoria de la ciudad | Registro histórico unificado, georreferenciado y deduplicado de incidentes y mediciones de tránsito, enriquecido con su contexto |
| Nodo | Intersección de la red vial obtenida de OpenStreetMap |
| Corredor | Secuencia de tramos de una vía principal; unidad de análisis cuando el volumen de datos por nodo es insuficiente |
| Franja horaria | Intervalo de una hora; unidad temporal de análisis |
| Escenario | Combinación de condiciones (día, hora, lluvia, actividad escolar, eventos, cortes) sobre la que se calcula el riesgo |
| Riesgo estructural | Propensión habitual de un nodo o corredor a registrar siniestros, independiente del escenario |
| Variación por escenario | Cuánto aumenta o disminuye el riesgo bajo un escenario respecto de un día habitual; base de los avisos |
| Índice de congestión | Relación entre el tiempo de viaje actual de un corredor y su tiempo habitual en la misma franja |
| Zona crítica | Nodo o corredor con riesgo estructural alto y sostenido, corregido por el efecto del azar en lugares con pocos registros |
| Nivel de confianza | Medida de 0 a 1 de la fiabilidad de un incidente, según la precisión de su ubicación y la cantidad de fuentes que lo reportan |
| Dato simulado | Registro sintético generado con reglas declaradas, que representa una fuente real aún no disponible y se identifica como tal |
| Revisión humana | Validación por una persona de los datos de baja confianza y de las recomendaciones antes de su uso |
| Trazabilidad | Posibilidad de rastrear cualquier resultado hasta los datos y fuentes que lo originaron |
| Aviso | Notificación emitida cuando la variación por escenario o el índice de congestión supera un umbral definido |

## 3. Problemática

La gestión de la movilidad en Posadas es reactiva. La información existe, pero presenta tres déficits estructurales:

| Déficit | Descripción | Efecto |
| --- | --- | --- |
| Fragmentación | Datos en silos: aforos en papel, siniestros en medios y 911, reclamos vecinales, clima (OPAD), capas de IDE Posadas | Ninguna área dispone de una visión integral |
| Ausencia de registro histórico | No existe una base georreferenciada y consolidada de incidentes | No pueden identificarse patrones ni zonas críticas con evidencia |
| Latencia y desacople en la decisión | La información llega con retraso y cada área decide con la propia | Las intervenciones se priorizan por intuición y después del hecho |

**Resultado:** recurrencia de congestiones y siniestros en los mismos puntos, asignación ineficiente de recursos y priorización de obras sin respaldo cuantitativo.

## 4. Propuesta y alcance

**Objetivo general.** Proveer al municipio una base de conocimiento común sobre la movilidad urbana que permita anticipar situaciones de riesgo y congestión, y priorizar intervenciones con evidencia.

**Objetivos específicos.**

1. Construir y mantener la memoria de la ciudad a partir de fuentes heterogéneas.
2. Identificar zonas críticas de siniestralidad y los factores que explican el riesgo.
3. Medir la fluidez por corredor y detectar desvíos respecto del comportamiento habitual.
4. Estimar el efecto de escenarios futuros: pronóstico meteorológico, agenda urbana y cortes.
5. Entregar resultados explicables, trazables y adaptados a cada área usuaria.

**Ejes del sistema.**

| Eje | Pregunta que responde | Fuentes principales | Resultado |
| --- | --- | --- | --- |
| Seguridad vial | ¿Dónde y cuándo es más probable un siniestro? | Siniestros (noticias, policía, 911), reclamos, contexto territorial y climático | Riesgo estructural, variación por escenario, zonas críticas |
| Fluidez | ¿Dónde se forma congestión y cuándo es anómala? | Tiempos de viaje (Waze, Google, TomTom), aforos, agenda de eventos y cortes | Índice de congestión, anomalías, rutas alternativas probables |

**Capacidades.**

| Capacidad | Definición | Horizonte |
| --- | --- | --- |
| Recordar | Consolidar incidentes y mediciones en un registro único y confiable | Pasado |
| Entender | Identificar dónde, cuándo y bajo qué condiciones se concentran el riesgo y la congestión | Pasado y presente |
| Anticipar | Estimar el efecto de un escenario y detectar desvíos en curso | Minutos a días, según la fuente |

**Alcance.** Incluye la detección, organización, análisis y anticipación de situaciones de movilidad. Excluye el control de semáforos, la intervención sobre infraestructura, los peritajes, la determinación de responsabilidades y el reemplazo de decisiones de la autoridad.

## 5. Arquitectura del sistema

El sistema se organiza en tres capas (ingesta, procesamiento y explotación) y los datos avanzan por tres niveles de refinamiento: **crudo**, **estructurado** y **analítico**.

```
INGESTA                     PROCESAMIENTO                     EXPLOTACIÓN (DSS)
Territorio ───────────┐
Incidentes (texto) ───┼──► Lector e Investigador ──┐
Clima ────────────────┤                            ▼
Agenda de la ciudad ──┼──────────────────► Memoria de la ciudad
Tránsito (APIs, aforos)┤                            │
Reportes de calle ────┘                            ▼
                                        Modelos analíticos ──► Mapa de riesgo, zonas críticas,
                                        (riesgo vial y fluidez)  simulador, fluidez
                                                   │
                                                   ▼
                                        Analista (agente) ────► Informes, consultas, avisos
```

### 5.1 Capa de ingesta

Adquiere los datos y los preserva sin modificación.

| Dominio | Fuentes | Mecanismo de adquisición |
| --- | --- | --- |
| Territorial | IDE Posadas (escuelas, semaforización, transporte), OpenStreetMap (red vial) | Servicios geoespaciales (WFS) y descarga del grafo |
| Meteorológico | OPAD, SMN, series históricas de precipitación | API y descarga |
| Incidentes | Medios digitales locales; registros de policía y 911; reclamos vecinales | Recolección automatizada; convenio institucional |
| Tránsito en tiempo real | Waze for Cities (alertas, embotellamientos, irregularidades); Google Maps Routes o TomTom Traffic (tiempos de viaje por corredor) | Feed de socio municipal; consulta periódica a API |
| Aforos | Planillas de conteo manual | Digitalización y lectura automática |
| Agenda urbana | Calendario escolar, eventos masivos, obras y cortes | Carga desde el municipio |
| Operativo | Reportes de inspectores | Formulario móvil |

**Almacenamiento:** zona cruda (data lake) inmutable. Cada registro conserva origen, fecha de captura, huella de contenido y su condición de dato real o simulado.

### 5.2 Capa de procesamiento

| Etapa | Función | Resultado | IA |
| --- | --- | --- | --- |
| Estructuración | Extracción de entidades desde texto, georreferenciación, deduplicación entre fuentes, nivel de confianza | Incidentes estructurados | Lector e Investigador |
| Integración | Consolidación por nodo, corredor y franja horaria; enriquecimiento con clima, actividad escolar, eventos, tránsito y atributos viales | Memoria de la ciudad | No |
| Análisis | Riesgo estructural, variación por escenario, zonas críticas, índice de congestión, anomalías y rutas alternativas | Resultados analíticos | Modelos analíticos, salvo rutas alternativas |

**Almacenamiento:** almacén analítico espacial. DuckDB Spatial en el prototipo; PostGIS como destino de implementación, compatible con estándares OGC.

### 5.3 Capa de explotación

AITARA es un DSS en sentido estricto: **base de datos** (memoria de la ciudad), **base de modelos** (riesgo, fluidez, rutas alternativas) e **interfaz de diálogo** (escenarios, consultas e informes).

| Salida | Descripción |
| --- | --- |
| Mapa de riesgo | Riesgo estructural y variación por escenario, por nodo o corredor |
| Mapa de fluidez | Índice de congestión por corredor y anomalías en curso |
| Ranking de zonas críticas | Nodos y corredores priorizados, con los incidentes que los respaldan |
| Simulador de escenarios | Recalcula riesgo y rutas alternativas al modificar condiciones |
| Avisos | Notificaciones por umbral, dirigidas a cada área |
| Informes automáticos | Informe diario operativo, informe mensual de tendencias, ficha técnica de zona crítica |
| Evaluación de intervenciones | Comparación antes y después de una obra o cambio de circulación |
| Interoperabilidad | Exportación en GeoJSON y WFS hacia el GIS municipal |

## 6. Estrategia de datos

El prototipo distingue tres categorías de datos. Cada registro lleva su categoría y el tablero identifica visiblemente los datos simulados.

| Categoría | Datos | Uso |
| --- | --- | --- |
| Reales y públicos | Red vial, capas de IDE Posadas, clima histórico, noticias locales | Base territorial y fuente real del Lector |
| Simulados | Ver tabla siguiente | Demostrar capacidades que dependen de fuentes institucionales |
| A gestionar | Registros de policía y 911, aforos, Waze for Cities, agenda municipal | Reemplazan a los simulados en el piloto |

### 6.1 Datos simulados

Se simula un dato solo si existe en la realidad, si habilita una capacidad que de otro modo no puede demostrarse y si su generación respeta la geografía real de Posadas.

| Dataset simulado | Contenido | Capacidad que habilita |
| --- | --- | --- |
| Registro de siniestros (policía y 911) | Dos a tres años de eventos con fecha, hora, intersección, tipo, vehículos y gravedad | Volumen para el modelo de riesgo; deduplicación con noticias reales |
| Aforos digitalizados | Conteos cada 15 minutos en esquinas testigo, incluida una planilla con aspecto de escaneo | Exposición vehicular; lectura automática de documentos |
| Reclamos vecinales | Textos libres sobre cruces peligrosos, señalización o semáforos | Segunda fuente de texto; riesgo percibido previo al siniestro |
| Feed de tránsito con formato Waze | Alertas y embotellamientos con la estructura del feed oficial | Fluidez en tiempo real y avisos en curso; conector listo para la fuente real |
| Agenda de eventos y cortes | Eventos, obras y cortes con ubicación y horario | Escenarios de evento y corte |
| Reportes de inspectores | Formularios desde la calle | Avisos en curso |
| Historial de intervenciones | Obras realizadas y sus fechas | Evaluación antes y después |

### 6.2 Generador de datos sintéticos

Los datos simulados se producen con un generador parametrizado que concentra los eventos en vías principales y franjas pico, respeta la ubicación de escuelas y aplica efectos declarados (por ejemplo, un multiplicador por lluvia).

El generador cumple dos funciones:

- **Demostración:** muestra el sistema funcionando de punta a punta.
- **Prueba del método:** se inyectan efectos conocidos y se verifica que los modelos los recuperan. Esto valida el método, no la precisión en Posadas, que se mide en el piloto con datos reales.

## 7. Componentes de inteligencia artificial

La IA se organiza por **función**, no por área. Hay dos componentes deterministas, que deben ser estables y auditables, y dos agentes, donde la autonomía y el uso de herramientas están justificados.

| Componente | Naturaleza | Entrada | Salida |
| --- | --- | --- | --- |
| Lector | Modelo de lenguaje con salida estructurada; paso fijo, no autónomo | Texto no estructurado: crónicas, reclamos, partes, aforos | Incidentes estructurados, georreferenciados y con nivel de confianza |
| Modelos analíticos | Estadística y aprendizaje automático | Memoria de la ciudad y escenario | Riesgo, zonas críticas, congestión, anomalías y aporte por factor |
| Investigador | Agente con herramientas de consulta territorial | Incidentes de baja confianza o en conflicto | Incidente resuelto o derivado a revisión humana |
| Analista | Agente con acceso de solo lectura a los modelos | Consultas, plantillas de informe y condiciones previstas | Informes, respuestas y avisos redactados, con fuentes citadas |

### 7.1 Lector

- **Extracción:** tipo de incidente, vehículos, gravedad, fecha, hora y ubicación descrita, validados contra un esquema fijo.
- **Georreferenciación:** resolución contra un nomenclador derivado de OpenStreetMap, con validación topológica (las calles mencionadas deben intersecarse).
- **Evidencia:** cada dato se acompaña del fragmento de texto que lo respalda.
- **Privacidad:** no extrae datos personales.
- **Despliegue:** admite un modelo abierto ejecutado en infraestructura propia, lo que reduce costo y evita transferir datos a terceros.

### 7.2 Modelos analíticos

**Seguridad vial**

- **Riesgo estructural:** intensidad de siniestros por nodo o corredor, ponderada por gravedad y confianza, con un **modelo jerárquico**: los lugares con pocos registros toman información de lugares de su mismo tipo (jerarquía vial, semaforización, entorno escolar).
- **Efecto de los factores:** lluvia, actividad escolar y eventos se estiman a nivel ciudad con el conjunto de los datos, no lugar por lugar, porque el volumen por nodo es insuficiente.
- **Variación por escenario:** cociente entre el riesgo bajo el escenario y el riesgo de un día habitual. Es la magnitud que dispara avisos.
- **Explicabilidad:** el resultado se descompone de forma exacta en el aporte de cada factor.

**Fluidez**

- **Índice de congestión:** tiempo de viaje actual frente al tiempo habitual de cada corredor y franja.
- **Detección de anomalías:** desvíos del índice o de los embotellamientos respecto del patrón esperado para ese día y hora.

**Calibración progresiva:** pesos iniciales por criterio experto; reestimación con el histórico; ajuste con la retroalimentación de uso.

### 7.3 Investigador

Resuelve los casos que el Lector no puede cerrar con confianza: ubicaciones vagas ("a metros de la rotonda"), calles que no se cruzan o posibles duplicados. Consulta el nomenclador, las capas de IDE y otras fuentes del mismo hecho, y decide o deriva a revisión humana. Es un agente porque la secuencia de consultas depende de lo que encuentra en cada paso.

### 7.4 Analista

- **Informes automáticos:** informe diario operativo, informe mensual de tendencias y ficha técnica de zona crítica.
- **Consultas:** responde preguntas en lenguaje natural ejecutando escenarios.
- **Avisos:** redacta las notificaciones cuando se supera un umbral.
- **Restricción:** no genera valores propios; todo dato proviene de los modelos y se cita su fuente.
- **Áreas:** cada área define una **plantilla** (qué informe recibe, con qué frecuencia y qué indicadores). La especialización reside en las plantillas, no en agentes separados.

### 7.5 Componentes sin IA

| Componente | Técnica |
| --- | --- |
| Rutas alternativas probables | Recálculo de caminos mínimos sobre el grafo vial ante un corte; indica por dónde puede desviarse el tránsito, no cuánto |
| Conectores | Integración de fuentes estructuradas (clima, IDE, OpenStreetMap, APIs de tránsito, agenda) |
| Curaduría por reglas | Controles de calidad previos a la intervención del Investigador |
| Programación | Ejecución periódica de modelos, informes y avisos |

### 7.6 Por qué no agentes por área

Las áreas consultan los mismos modelos; varía la pregunta y la presentación, no el razonamiento. Un agente por área multiplicaría prompts, pruebas y puntos de falla sin agregar capacidad. Se justificaría una arquitectura multiagente si un área incorpora datos o permisos propios, o si necesita ejecutar acciones en sus sistemas.

## 8. Usuarios y decisiones que apoya

Los datos y modelos son comunes; cada área accede mediante una plantilla que define su vista inicial, sus informes y sus avisos. La Dirección de Movilidad Urbana es el usuario validado; el resto son usuarios potenciales a validar en el piloto.

| Área | Decisión que apoya | Salida principal | Estado |
| --- | --- | --- | --- |
| Tránsito y Movilidad Urbana | Asignación preventiva de presencia en calle; respuesta a congestión anómala | Informe diario, mapa de fluidez, avisos | Validado |
| Planificación y Obras | Priorización de intervenciones y evaluación de su efecto | Ranking de zonas críticas, ficha técnica, evaluación antes y después | A validar |
| Eventos y cortes | Autorización y programación de cortes y eventos | Rutas alternativas probables por escenario | A validar |
| Transporte público | Ajuste de recorridos y frecuencias ante condiciones adversas | Riesgo y congestión sobre recorridos | A validar |
| Seguridad vial | Focalización de campañas y controles | Zonas, franjas y tipologías de siniestro | A validar |

El sistema no controla semáforos, no interviene infraestructura ni asigna responsabilidades en siniestros. Toda recomendación requiere decisión humana.

## 9. Escenarios y avisos

### 9.1 Escenarios

Un escenario es un conjunto de condiciones definidas por el usuario o tomadas del pronóstico y la agenda. Al modificarlas, el sistema recalcula la variación de riesgo y las rutas alternativas.

| Variable | Valores | Fuente |
| --- | --- | --- |
| Día y franja horaria | Calendario y hora | Usuario |
| Precipitación | mm/h previstos u observados | Pronóstico OPAD/SMN o usuario |
| Actividad escolar | Con o sin clases; entrada o salida | Calendario escolar |
| Evento | Ubicación, horario y magnitud | Agenda municipal o usuario |
| Corte de calle | Tramos afectados | Agenda de obras o usuario |

Los parámetros de los modelos no son modificables por el usuario operativo; los ajusta un rol técnico o se reestiman con los datos.

### 9.2 Avisos

Se emiten por umbral para evitar la fatiga de alertas. Los umbrales son parámetros configurables por área.

| Tipo | Disparador | Destinatario | Fuente requerida |
| --- | --- | --- | --- |
| Anticipado | La variación de riesgo prevista en una zona crítica supera el umbral (por ejemplo, +50 % sobre un día habitual) | Tránsito, Transporte | Pronóstico y agenda; disponible desde el inicio |
| Congestión anómala | El índice de congestión de un corredor supera el umbral durante un período sostenido | Tránsito | Waze o API de tiempos de viaje |
| Incidente en curso | Alerta de Waze, reporte de inspector o nueva noticia en un nodo crítico | Tránsito | Fuentes en tiempo real |
| De tendencia | Aumento sostenido del riesgo estructural de un nodo o corredor | Planificación, Seguridad vial | Histórico acumulado |

Cada aviso incluye su explicación y admite validación (útil o no útil), que se registra para calibrar umbrales y modelos.

## 10. Validación y métricas

La validación tiene dos niveles: **del método**, con datos simulados, y **de los resultados**, con datos reales en el piloto.

| Objeto | Métrica | Método | Nivel |
| --- | --- | --- | --- |
| Modelos analíticos | Recuperación de efectos inyectados | Generador sintético con efectos conocidos | Método |
| Lector | Precisión de extracción y de georreferenciación | Muestra de artículos reales anotada manualmente | Resultado |
| Investigador | Proporción de casos dudosos resueltos correctamente | Contraste con revisión humana | Resultado |
| Zonas críticas | Concordancia con el criterio experto | Contraste con la Dirección de Movilidad Urbana | Resultado |
| Riesgo | Precisión en los k nodos de mayor riesgo frente a la línea base | Validación temporal; línea base de frecuencia histórica por día y hora | Resultado |
| Fluidez | Coincidencia de anomalías detectadas con eventos reportados | Contraste con alertas de Waze y reportes de inspectores | Resultado |
| Analista | Trazabilidad total | Verificación de que cada valor citado proviene de un modelo | Método |
| Uso | Tasa de avisos validados como útiles | Registro de validaciones | Resultado |

## 11. Limitaciones y riesgos

| Limitación o riesgo | Impacto | Mitigación |
| --- | --- | --- |
| Volumen histórico incierto | Si hay pocos incidentes, los modelos por nodo no son confiables | Modelo jerárquico, efectos a nivel ciudad y agregación por corredor |
| Sesgo de cobertura mediática | Sobrerrepresentación de siniestros graves, del centro y de los ocurridos con lluvia | Ponderación por gravedad; contraste con registros oficiales |
| Circularidad de los datos simulados | Un modelo puede "descubrir" lo que se inyectó | Los simulados validan el método, no la precisión; se declara |
| Error de georreferenciación | Ubicaciones imprecisas en textos ambiguos | Nivel de confianza, Investigador y revisión humana |
| Dependencia de APIs comerciales | Costo variable y términos de uso que restringen el almacenamiento | Consulta limitada a corredores fijos; Waze for Cities como fuente institucional gratuita |
| Costo de los modelos de lenguaje | Gasto recurrente por uso | Modelo abierto en infraestructura propia como alternativa |
| Marco legal | Términos de uso de los medios; protección de datos personales (Ley 25.326) | Recolección respetuosa de los términos; exclusión de datos personales por diseño |
| Adopción institucional | Resistencia al cambio de procesos | Informes listos para usar, explicabilidad y decisión siempre humana |
| Operación y mantenimiento | Requiere un responsable técnico municipal | Despliegue simple, documentación y capacitación |

## 12. Prototipo y hoja de ruta

### 12.1 Alcance del prototipo

1. **Memoria de la ciudad:** noticias reales y partes simulados convertidos en incidentes georreferenciados, unificados entre fuentes y con enlace a su origen.
2. **Zonas críticas:** ranking por nodo y corredor, con evidencia.
3. **Escenario:** precipitación en horario escolar y su variación de riesgo, con aporte por factor.
4. **Fluidez:** índice de congestión por corredor sobre el feed simulado con formato Waze.
5. **Corte de calle:** rutas alternativas probables.
6. **Analista:** informe diario generado automáticamente y una consulta en lenguaje natural.
7. **Investigador:** resolución de un caso de ubicación ambigua.

### 12.2 Hoja de ruta

| Etapa | Incorporaciones |
| --- | --- |
| Siguiente paso | Recolección del histórico real de noticias y medición de su volumen; prueba de cobertura de TomTom y costo de Google Routes en corredores seleccionados |
| Piloto | Adhesión del municipio a Waze for Cities; registros oficiales de siniestros; digitalización de aforos; agenda de eventos y cortes |
| Operación | Reportes de inspectores, avisos en curso, retroalimentación sistemática, validación de nuevas áreas usuarias |
| Expansión | Evaluación de intervenciones, GPS del transporte público, integración con el GIS municipal, mapa público |

### 12.3 Mensaje central

> Posadas ya genera los datos de su movilidad, pero dispersos. AITARA los integra en una memoria común y en modelos de riesgo y fluidez que cualquier área municipal puede consultar antes de decidir dónde intervenir, qué autorizar y cómo prepararse.

## 13. Decisiones de diseño

| Versión anterior | Versión actual | Fundamento |
| --- | --- | --- |
| Predicción a 30–60 minutos sin fuentes en vivo | Escenarios con pronóstico; anticipación de corto plazo solo con fuentes de tránsito en tiempo real | La anticipación debe estar respaldada por datos |
| Congestión prometida sin datos | Eje de fluidez con Waze, APIs de tiempos de viaje y aforos | Cada promesa tiene una fuente |
| Usuario único | Múltiples áreas mediante plantillas; una validada, el resto a validar | Valor compartido, sin sobreafirmar |
| Nodos críticos definidos a priori | Calculados y validados con el experto | El sistema debe descubrir, no confirmar |
| Índice único por percentiles | Riesgo estructural y variación por escenario | Distingue dónde es peligroso de cuándo empeora |
| Modelo por nodo y franja | Modelo jerárquico, efectos a nivel ciudad, agregación por corredor | Robustez ante pocos datos |
| Asistente conversacional | Analista que produce informes; el chat es secundario | Ahorra trabajo real a quien decide |
| Agentes por área | Agentes por función: Investigador y Analista | Autonomía solo donde se justifica |
| Datos inventados sin declarar | Estrategia de datos reales, simulados y a gestionar | Transparencia y validación del método |
| Simulación de impacto de cortes | Rutas alternativas probables | Sin datos de origen y destino no se cuantifica el desvío |
