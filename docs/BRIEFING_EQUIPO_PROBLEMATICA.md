# Briefing Técnico: Definición de Problemática y Enfoque de Solución

**Proyecto:** AITARA — Hackathon Silicon Misiones 2026 (Smart City - Movilidad Urbana)
**Equipo:** Ana Florencia Zayas, Joaquín Sanchez, Facundo Fraga, Santiago Nuñez
**Fecha:** 03/11/2026 (Día 2)

---

### 1. El Desafío Oficial (Pliego Hackathon)

El desafío exige utilizar Inteligencia Artificial para integrar, interpretar y analizar datos de movilidad urbana dispersos, con el fin de detectar situaciones relevantes, identificar patrones y anticipar problemas, funcionando estrictamente como herramienta de apoyo a la toma de decisiones (Decision Support System - DSS).

---

### 2. La Problemática Local Focalizada (Posadas)

> *"La gestión de movilidad de Posadas opera de forma reactiva debido a datos fragmentados, manuales y diferidos (relevados en planillas de 15 minutos o leídos tardíamente de noticias), lo que impide anticipar incidentes y coordinar operativos preventivos antes de que los corredores críticos colapsen."*

---

### 3. Problemática General y Segmentación en Subproblemáticas

#### Problemática General

**Ruptura en la cadena de transformación del dato en decisión operativa:**
El municipio genera y observa hechos en el territorio, pero carece de un pipeline técnico que eleve esos datos crónicos y dispersos hasta el nivel de sabiduría accionable para planificar recursos antes de los incidentes.

#### Subproblemáticas Específicas

* **Subproblemática 1 (Nivel Datos - Dispersión e Ingesta):**
  Las fuentes están desconectadas (planillas manuales, noticias en portales, registros del 911, clima y capas de IDE Posadas sin comunicación entre sí).
* **Subproblemática 2 (Nivel Información - Estructuración y Latencia):**
  Gran parte de los datos son texto no estructurado con alta latencia temporal (un choque se reporta en las noticias horas después y nadie lo geocodifica de inmediato).
* **Subproblemática 3 (Nivel Conocimiento - Correlación Causal):**
  Falta de modelos espaciotemporales capaces de cruzar variables exógenas (lluvias de la OPAD + horarios escolares + topografía de badenes) para entender por qué y cuándo colapsa una intersección.
* **Subproblemática 4 (Nivel Sabiduría - Despacho Operativo):**
  Los recursos humanos y móviles se asignan por intuición subjetiva ("a ojo") o llegan al lugar cuando el congestionamiento ya es irreversible.
