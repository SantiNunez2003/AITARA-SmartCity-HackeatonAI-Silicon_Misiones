# HACKATHON IA EN ACCIÓN — SILICON MISIONES 2026
## FICHA DE PROYECTO FINAL

---

### 1. IDENTIFICACIÓN DEL PROYECTO

- **Nombre del proyecto:** AITARA (Sistema de Soporte a Decisiones para la Movilidad Urbana Preventiva)
- **Track / Temática:** Smart City
- **Desafío Oficial:** Desafío 1 — IA para Entender y Anticipar la Movilidad Urbana

#### Integrantes del equipo:

| Nombre y apellido | Rol / función | Formación / experiencia |
| :--- | :--- | :--- |
| **Santiago Agustín Nuñez** | Lead Architect & ML Engineer | Arquitectura de software, pipelines de datos y sistemas distribuidos. |
| **Joaquin Sanchez** | Backend & Data Engineer | Desarrollo de APIs, bases de datos geoespaciales e ingesta de datos. |
| **Facundo Fraga** | Data Analyst & GIS Specialist | Análisis espacial, procesamiento de capas IDE y modelado territorial. |
| **Ana Florencia Zayas** | Product Owner & Referente | Gestión de proyectos, validación de usuario y comunicación institucional. |

- **Responsable y contacto oficial:**  
  Ana Florencia Zayas  
  Mail: `zayasflorenciaana@gmail.com`  
  Teléfono: `+54 9 3764 662524`

---

### 2. RESUMEN DEL PROYECTO (Exactamente 265 palabras / Máximo 300)

La gestión de la movilidad urbana en Posadas opera de forma reactiva debido a datos dispersos, relevamientos manuales en planillas de 15 minutos y lectura diferida de incidentes en noticias. Esta fragmentación impide a las autoridades anticipar anomalías y desplegar operativos preventivos antes de que los corredores colapsen. 

AITARA es un Sistema de Soporte a la Toma de Decisiones (Decision Support System - DSS) diseñado específicamente para los operadores de despacho y planificación de la Dirección de Tránsito y Movilidad Urbana de la Municipalidad de Posadas. Su propósito es emitir recomendaciones operativas con 30 a 60 minutos de anticipación para coordinar inspectores, balizas y desvíos preventivos.

La Inteligencia Artificial interviene de forma dual y explicable: primero, mediante procesamiento de lenguaje natural (NLP) con esquemas estructurados para minar y geocodificar incidentes viales reportados en portales periodísticos locales; segundo, a través de un motor de inferencia espaciotemporal (XAI) que cruza cuatro dimensiones complementarias (demanda escolar y comercial programada, meteorología en calzada de la OPAD, capacidad topográfica de la arteria y riesgo siniestral histórico). 

AITARA opera bajo una arquitectura ELT abierta, almacenando eventos crudos en un Data Lake y estructurándolos en un Data Warehouse local compatible con PostGIS, garantizando una integración no disruptiva con la infraestructura municipal preexistente. Cumple estrictamente las restricciones del pliego oficial: no interviene controladores físicos ni secuencias semafóricas, y no realiza peritajes legales.

El impacto directo radica en reducir el tiempo de respuesta municipal de horas a minutos, mitigando siniestros en nodos escolares críticos y garantizando fluidez sustentable para la ciudadanía.

---

### 3. PROBLEMÁTICA Y USUARIOS

#### Problemática
Ruptura en la cadena de transformación del dato en decisión operativa en el municipio de Posadas. La ciudad genera y registra hechos en el territorio, pero carece de un pipeline técnico unificado que transforme datos crónicos y dispersos en conocimiento accionable. 

Actualmente, las decisiones de tránsito se toman de forma subjetiva ("a ojo") o de manera reactiva: los inspectores acuden a un nudo vial cuando el embotellamiento ya se extendió cientos de metros o cuando el 911 reporta un siniestro que ocurrió media hora antes. 

Las consecuencias directas son:
1. Colapso recurrente en horarios pico en nodos con establecimientos educativos (ej. Av. Corrientes y Tucumán con el Colegio San Basilio Magno).
2. Alta siniestralidad diferida de usuarios vulnerables (motociclistas y peatones) en avenidas de acceso rápido (Av. Quaranta, Alicia M. de Justo).
3. Ineficiencia en la asignación del capital humano municipal (inspectores mal distribuidos en horarios de baja fricción mientras los puntos calientes quedan desatendidos).

#### Usuarios y actores involucrados
- **Usuario Principal:** Operador de Despacho y Planificación Operativa de la Dirección de Tránsito / Centro de Monitoreo. Requiere una consola unificada que le indique qué nodo requiere intervención en los próximos 30-60 minutos y por qué causa (explicabilidad).
- **Ejecutores en Territorio:** Cuerpo de inspectores de tránsito y patrullas de balizamiento, que se benefician al recibir directivas anticipadas y claras de posicionamiento.
- **Beneficiarios Finales:** Conductores, usuarios del transporte público colectivo urbano y peatones (especialmente comunidades educativas).

---

### 4. SOLUCIÓN PROPUESTA

#### Producto / Servicio
AITARA es una plataforma analítica y operativa de soporte a decisiones compuesta por:
1. **Pipeline de Ingesta y Normalización ELT:** Centraliza datos en un Data Lake (Bronze) y genera capas analíticas en un Data Warehouse relacional (Silver y Gold).
2. **Motor de Inferencia de Riesgo Multivariado (XAI):** Evalúa probabilísticamente cada nodo vial ponderando variables exógenas y topológicas sin depender de sensores vehiculares continuos.
3. **Consola Web Interactiva (DSS Streamlit + PyDeck/Folium):** Tablero con mapa de Posadas con semaforización de riesgo por nodo, selector de ventana de anticipación ($T+30 / T+60\text{ min}$), y la **Matriz de Despacho Preventivo** con asignación sugerida de recursos.

#### Diferencial frente a alternativas existentes
- **Frente a simuladores físicos de microtráfico (SUMO / Aimsun):** No exige matrices Origen-Destino ni sensores IoT por carril inexistentes en Posadas.
- **Frente a tableros de BI tradicionales (PowerBI / Metabase):** No es un visor retroactivo de lo que pasó ayer; modela riesgo prospectivo y accionable para los próximos 60 minutos.
- **Frente a cajas negras de Machine Learning:** Es 100% explicable (XAI). El operador municipal ve la causa raíz de la alerta (ej. *"Lluvia 15 mm/h + Ingreso escolar + Cuello de botella 2 carriles"*).

#### MVP (Producto Mínimo Viable)
- Ingesta y geocodificación de fuentes abiertas (IDE Posadas, OSMnx, noticias y OPAD).
- Esquema relacional Bronze/Silver/Gold en DuckDB Spatial / SQLite.
- Motor de cálculo sobre 5 nodos testigos de Posadas, con foco en el caso piloto de **Av. Corrientes y Tucumán**.
- Matriz operativa de despacho con cálculo automático de inspectores, conos y rutas de desvío sugeridas.

---

### 5. INTELIGENCIA ARTIFICIAL

#### ¿Qué tarea realiza la IA?
1. **Extracción y Estructuración de Texto No Estructurado (NLP):** Minería de artículos periodísticos de portales de Posadas (Canal 12, El Territorio, Misiones Online). Utiliza modelos de lenguaje con salida estructurada (JSON Schema) para extraer: intersección exacta, fecha/hora, tipos de vehículos involucrados, gravedad y condiciones de calzada.
2. **Motor de Inferencia de Riesgo Espaciotemporal:** Algoritmo ponderado de clasificación de riesgo no lineal que evalúa la interacción dinámica entre la demanda programada y las restricciones de capacidad vial.

#### ¿Es central o complementaria?
Es un componente **central en la generación de inteligencia territorial**, ya que permite transformar señales territoriales dispersas en variables numéricas de riesgo, resolviendo la falta de sensores físicos en la vía pública.

#### ¿Qué beneficio aporta frente a una solución tradicional?
Una solución tradicional mediante reglas estáticas o consultas SQL aisladas es incapaz de procesar el lenguaje natural de las crónicas periodísticas y no puede ponderar de forma flexible cómo una lluvia de 15 mm/h afecta diferencialmente a una esquina escolar respecto a una avenida rápida. La IA unifica estas fuentes heterogéneas en un índice probabilístico continuo.

---

### 6. DATOS Y FUNCIONAMIENTO

#### Datos necesarios y origen
- **Infraestructura y Geografía (Públicos / Abiertos):** Capas vectoriales del Geoportal IDE Posadas (`ide.posadas.gob.ar`): semáforos, establecimientos educativos, paradas de colectivos y curvas de nivel/drenaje.
- **Red Vial (Público):** Topología vial extraída de OpenStreetMap (OSMnx).
- **Incidentes y Señales Territoriales (Público):** Portales locales de noticias para scoring de siniestralidad.
- **Meteorología (Público / Abierto):** Datos de estaciones meteorológicas de la OPAD (Posadas) y Open-Meteo.

#### Consideraciones de privacidad y sesgo
La solución no utiliza datos personales sensibles, patentes ni reconocimiento facial. Trabaja con datos públicos anonimizados y agregados a nivel de nodo vial. Para mitigar sesgos de cobertura mediática, las frecuencias de siniestros se combinan con la vulnerabilidad física intrínseca de cada intersección.

#### Flujo de funcionamiento
```
[Fuentes: IDE + OPAD + Noticias + Escuelas]
                    │
                    ▼ (Extracción y Carga)
        [Data Lake - Capa Bronze]
                    │
                    ▼ (Normalización y Geocodificación)
      [Data Warehouse - Capa Silver (DuckDB)]
                    │
                    ▼ (Agregación de Features)
      [Feature Store - Capa Gold]
                    │
                    ▼ (Motor de Inferencia XAI)
     [Evaluación 4D de Riesgo Espaciotemporal]
                    │
                    ▼ (Dashboard DSS)
[Matriz de Despacho: Inspectores, Balizas, Desvíos]
                    │
                    ▼ (Acción Humana)
 [Despliegue Preventivo del Inspector en Territorio]
```

---

### 7. MERCADO, COMPETENCIA Y MODELO DE NEGOCIO

#### Industria y Mercado
Sector GovTech / Smart Cities / Movilidad Urbana Sostenible. Aplicable inicialmente al Municipio de Posadas y extensible a ciudades intermedias de la región NEA (Oberá, Eldorado, Corrientes, Encarnación) que carecen de infraestructura de sensores IoT pero cuentan con datos abiertos y necesidad de optimizar recursos humanos.

#### Comparativa de Competencia

| Alternativa / Competidor | Fortalezas | Debilidades | Diferencial de AITARA |
| :--- | :--- | :--- | :--- |
| **Waze for Cities / Google Maps** | Gran volumen de usuarios y datos de velocidad en tiempo real. | No integra capas institucionales locales (escuelas, IDE) ni emite matrices operativas de despacho para inspectores. | Diseñado a medida del flujo de trabajo de la Dirección de Tránsito local con matriz de despacho preventivo. |
| **Simuladores de Tráfico (SUMO / Aimsun)** | Modelado físico vehicular microscópico muy detallado. | Inviables en Posadas por requerir matrices O-D y conteos continuos que la ciudad no posee. | Funciona sobre datos exógenos y proxies de riesgo sin requerir sensores continuos por carril. |
| **Dashboards de BI Tradicional (PowerBI)** | Fáciles de implementar sobre bases de datos SQL estándar. | Son retrospectivos (muestran lo que pasó); no poseen motor predictivo ni explicabilidad en tiempo real. | Proyección anticipada ($T+30 / T+60\text{ min}$) con recomendación de acción física concreta. |

#### Modelo de adopción y canales
- **Modelo de Despliegue:** SaaS institucional o despliegue On-Premise dentro de los servidores del Centro de Cómputos municipal, sin costos de licenciamiento privativo (construido sobre Python, DuckDB y Streamlit).
- **Canal de Implementación:** Articulación directa con la Secretaría de Movilidad Urbana y Silicon Misiones en etapas de pilotaje.

---

### 8. FACTIBILIDAD E IMPLEMENTACIÓN

#### Recursos y tecnología
- **Lenguaje y Entorno:** Python 3.12.
- **Motor de Datos:** DuckDB Spatial / SQLite (1:1 compatible con PostgreSQL/PostGIS municipal).
- **Frontend / Visualización:** Streamlit + Folium / PyDeck.
- **Infraestructura requerida:** Mínima; corre en cualquier servidor o workstation estándar con 4GB de RAM sin necesidad de GPUs dedicadas para la inferencia de despacho.

#### Complejidad técnica y plazos estimados
- **Complejidad:** Media-Baja para el despliegue del MVP (arquitectura modular desacoplada).
- **Tiempos de evolución:**
  - *Fase 1 (Completada en Hackathon):* Prototipo funcional y motor heurístico con 5 nodos críticos.
  - *Fase 2 (30 días):* Conexión directa a base de datos de Posadas y pipeline continuo de noticias.
  - *Fase 3 (60 días):* Prueba piloto operativa con inspectores en el nodo San Basilio Magno.

#### Actores y aliados estratégicos
- Municipalidad de Posadas (Dirección de Movilidad Urbana y Semaforización).
- Silicon Misiones (Incubación y vinculación tecnológica).
- OPAD (Provisión de feeds de datos meteorológicos).
- IDE Misiones / IDE Posadas (Cartografía y capas GIS oficiales).

#### Riesgos y mitigación
- **Riesgo:** Resistencia al cambio del personal de calle.  
  *Mitigación:* La herramienta no reemplaza al inspector; sugiere posicionamiento preventivo con justificación clara, aliviando el estrés de intervenir cuando el nudo ya colapsó.
- **Riesgo:** Variaciones en formatos periodísticos.  
  *Mitigación:* Uso de esquemas de validación estrictos (Pydantic / Structured Outputs) que descartan notas sin georreferenciación fidedigna.

---

### 9. IMPACTO Y ESCALABILIDAD

#### Impacto social y urbano
- **Seguridad Vial:** Reducción sustancial del riesgo de atropellos y colisiones de motos en accesos escolares en horarios pico.
- **Ahorro de Tiempo Ciudadano:** Descongestionamiento de arterias troncales antes de que la cola de espera supere los 100 metros.
- **Sustentabilidad Ambiental:** Menor tiempo de motores en ralentí en embotellamientos, reduciendo emisiones de CO₂ en el casco urbano.

#### Escalabilidad
Arquitectura 100% transferible a cualquier municipio de Misiones o del país que cuente con red vial en OpenStreetMap y portales informativos locales. No requiere cambiar el equipamiento semafórico existente, lo que permite replicar la solución en ciudades como Oberá, Eldorado o Puerto Rico con mínima inversión.

---

### 10. SÍNTESIS FINAL

- **Problema que resolvemos:** Gestión de tránsito reactiva y desarticulada por falta de integración anticipada del dato territorial.
- **Usuarios / beneficiarios:** Operadores de despacho de tránsito (directo) y la comunidad de Posadas (indirecto).
- **Solución propuesta:** AITARA — DSS web con pipeline ELT, capas analíticas en DuckDB y motor de inferencia explicable (XAI).
- **Uso de Inteligencia Artificial:** NLP estructurado para minería de incidentes en noticias locales e inferencia espaciotemporal en 4 dimensiones.
- **Datos necesarios:** Capas IDE Posadas, red OSMnx, crónicas de noticias locales y alertas climáticas OPAD.
- **Principal impacto esperado:** Reducción del tiempo de respuesta municipal de horas a minutos, previniendo siniestros y cuellos de botella en corredores escolares y troncales.
- **Próximo paso para implementar la solución:** Correr la prueba piloto en calle en el corredor de Av. Corrientes y Tucumán junto al equipo de inspectores de la Municipalidad de Posadas.

---

### ANEXOS

1. **Diagrama de Arquitectura Interactivo:** Archivo compilado con Archify en `docs/architecture/aitara-archify.html` y captura PNG en `docs/architecture/aitara-archify.png`.
2. **Prototipo Funcional Operativo:** Servidor local activo en `http://localhost:8501` (`app.py`).
3. **Evidencia Primaria con Referente:** Transcripción y análisis técnico de la entrevista con Matías Ruiz (Director de Movilidad Urbana) en `docs/TRANSCRIPCION_AUDIO_RUIZ.md` y `docs/STAKEHOLDER_BRIEF.md`.
4. **Marco Teórico de la Solución:** Pirámide DIKW y formulación de preguntas de decisión en `docs/MARCO_CONCEPTUAL_DIKW.md`.
