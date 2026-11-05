# Marco Conceptual AITARA: Arquitectura DIKW y Modelo de Decisión

Fundamentación conceptual y metodológica para el Hackathon Silicon Misiones 2026 (Desafío 1: Movilidad Urbana).

---

## 1. El Desafío Oficial (Pliego Hackathon)
- **Consigna:** Utilizar Inteligencia Artificial para integrar, interpretar y analizar información de movilidad urbana que permita detectar situaciones relevantes, identificar patrones y anticipar problemas de tránsito o seguridad vial.
- **Condición excluyente:** Funcionar estrictamente como herramienta de apoyo a la toma de decisiones (Decision Support System - DSS), sin actuar sobre semáforos, infraestructura vial ni emitir dictámenes punitivos o peritajes.

---

## 2. La Problemática Local Focalizada (Posadas)
> *"La gestión de movilidad de Posadas opera de forma reactiva debido a datos fragmentados, manuales y diferidos (relevados en planillas de 15 minutos o leídos tardíamente de noticias), lo que impide anticipar incidentes y coordinar operativos preventivos antes de que los corredores críticos colapsen."*

---

## 3. Desglose Estructural: Problemática General y Subproblemáticas

### Problemática General
**Ruptura en la cadena de transformación del dato en decisión operativa.**  
El municipio genera y observa hechos en el territorio, pero carece de un pipeline automatizado que eleve esos datos discontinuos al nivel de sabiduría accionable para planificar recursos preventivos.

### Subproblemáticas Específicas
1. **Subproblemática 1 (Nivel Datos - Ingesta y Dispersión):**
   - Fuentes aisladas sin interoperabilidad: conteos manuales en papel, noticias periodísticas, registros del 911, clima y capas de IDE Posadas sin conexión entre sí.
2. **Subproblemática 2 (Nivel Información - Procesamiento y Estructuración):**
   - Datos no estructurados y de alta latencia: las noticias narrativas y planillas no están geocodificadas ni estandarizadas para el análisis en tiempo oportuno.
3. **Subproblemática 3 (Nivel Conocimiento - Correlación Causal):**
   - Carencia de modelos espaciotemporales: imposibilidad de cruzar variables exógenas (lluvias, horarios escolares, topografía, eventos) para comprender por qué y cuándo ocurre un colapso.
4. **Subproblemática 4 (Nivel Sabiduría - Acción Operativa):**
   - Asignación intuitiva de recursos: los inspectores y patrullas se despachan por experiencia subjetiva ("a ojo") o llegan tarde cuando el nudo ya colapsó.

---

## 4. La Solución Progresiva: De la Base DIKW a las 4 Preguntas Clave

La arquitectura de AITARA se construye respetando la pirámide del conocimiento (Data, Information, Knowledge, Wisdom $\rightarrow$ Decision/Action):

```
                   /\
                  /  \     SABIDURÍA      ---> DECISIÓN / ACCIÓN
                 /    \    (¿Qué mejorar?)     (Despacho Preventivo)
                /------\
               /        \    CONOCIMIENTO
              /          \   (¿Cómo y Cuándo?) (Correlación ML / Grafo)
             /------------\
            /              \   INFORMACIÓN
           /                \  (¿Qué patrones?) (Geocodificación / Limpieza)
          /------------------\
         /                    \  DATOS
        /                      \ (¿Qué hechos?)  (Scraping / IDE Posadas / Planillas)
       /------------------------\
```

### Mapeo Operativo

| Nivel DIKW | Pregunta Operativa | Rol Tecnológico de AITARA | Resultado Concreto |
| :--- | :--- | :--- | :--- |
| **1. DATOS** *(Business Operations)* | **¿QUÉ hechos ocurrieron?** | Ingesta multimodal resiliente: captura de noticias locales, capas WFS de IDE Posadas, feeds meteorológicos de OPAD/SMN y planillas de conteo. | Data Lake tabular estructurado con eventos georreferenciados. |
| **2. INFORMACIÓN** *(Business Operations)* | **¿QUÉ patrones se manifiestan?** | Normalización con NLP/NER (extracción de ubicaciones y vehículos en crónicas) y cálculo de densidades sobre el grafo vial (`OSMnx`). | Malla territorial con métricas de flujo, incidentes clasificados y anomalías detectadas. |
| **3. CONOCIMIENTO** *(Business Intelligence)* | **¿CÓMO y CUÁNDO se producirá el riesgo?** | Modelado predictivo (Gradient Boosting / Heurística espaciotemporal): inferencia del riesgo a $T+30$ y $T+60$ minutos cruzando clima, hora y calendario escolar. | Mapa de calor predictivo y explicabilidad de factores de riesgo ($XAI$). |
| **4. SABIDURÍA** *(Business Intelligence)* | **¿QUÉ y CÓMO MEJORAR?** | Motor de recomendación operativa (DSS): genera la directiva concreta de prevención para el funcionario municipal. | Matriz de despacho de inspectores, sugerencias de desvío y balizamiento disuasorio. |
