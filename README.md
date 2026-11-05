# AITARA — Sistema de Soporte a Decisiones para la Movilidad Urbana Preventiva
**Hackathon Silicon Misiones 2026 | Track: Smart City | Desafío 1: Movilidad Urbana**

---

## 🚦 Visión General
**AITARA** es un Decision Support System (DSS) diseñado para los operadores de despacho y planificación de la **Dirección de Tránsito y Movilidad Urbana de la Municipalidad de Posadas**.

Su objetivo es transformar datos territoriales fragmentados en **decisiones operativas preventivas con 30 a 60 minutos de anticipación**, permitiendo asignar inspectores, balizas y desvíos antes de que los corredores críticos colapsen.

> **Regla de Oro (Cumplimiento de Pliego):** AITARA es 100% una herramienta de apoyo a la decisión humana. No interviene físicamente controladores semafóricos, no altera secuencias de tránsito y no realiza peritajes legales.

---

## 🏗️ Arquitectura Técnica (Pipeline ELT)

AITARA opera bajo un esquema ELT (Extract-Load-Transform) abierto y desacoplado:

```
[Fuentes: IDE Posadas + OPAD + Noticias Locales + Escuelas]
                          │
                          ▼ (Ingesta Cruda)
              [Data Lake - Capa Bronze]
                          │
                          ▼ (Normalización Geoespacial)
            [Data Warehouse - Capa Silver (DuckDB)]
                          │
                          ▼ (Feature Store de Riesgo)
            [Data Warehouse - Capa Gold]
                          │
                          ▼ (Inferencia Explicable XAI)
          [Motor Multivariado de 4 Dimensiones]
                          │
                          ▼ (Visualización y Despacho)
        [Consola Interactiva Streamlit + Folium]
```

### Las 4 Dimensiones del Motor de Riesgo (XAI):
1. **Dimensión Temporal y Demanda (Event-Driven):** Horarios escolares y picos comerciales. *(Determinístico)*
2. **Dimensión Meteorológica de Calzada (Context-Driven):** Precipitaciones de la OPAD y anegamiento de cuencas bajas. *(Dinámico)*
3. **Dimensión Topológica y Capacidad Vial (Network-Driven):** Anchos de calzada, badenes, paradas de colectivos y giros. *(Cuasi-estático)*
4. **Dimensión de Riesgo Siniestral (Safety-Driven):** Minado y clustering de siniestros desde noticias de portales locales. *(Probabilístico)*

---

## 🎯 Caso Piloto Foco: Av. Corrientes y Tucumán
- **Nodo:** Colegio San Basilio Magno (Posadas).
- **Escenario Crítico:** 06:45 AM en jornada de lluvia (15 mm/h).
- **Proyección del Motor ($T+30\text{ min}$):** Alerta **CRÍTICA (Score: 0.86)** por confluencia de ingreso escolar y calzada resbaladiza en calzada de 2 carriles.
- **Acción Recomendada:** Despacho de 2 inspectores y 6 conos para encauzar la dársena de ascenso/descenso 30 minutos antes del colapso.

---

## 🚀 Puesta en Marcha Local

### 1. Clonar el repositorio e instalar dependencias
```powershell
cd AITARA-Hackathon-Silicon-Misiones-2026
python -m pip install -r requirements.txt
```

### 2. Inicializar la base de datos (DuckDB / SQLite)
```powershell
python src/warehouse/db.py
```

### 3. Ejecutar la consola interactiva (Streamlit)
```powershell
streamlit run app.py
```
Abrir el navegador en `http://localhost:8501`.

---

## 📁 Estructura del Proyecto

```
AITARA/
├── app.py                      # Tablero interactivo DSS en Streamlit
├── requirements.txt            # Dependencias del proyecto
├── data/                       # Almacenamiento local (DuckDB / SQLite)
├── docs/                       # Documentación técnica, marcos teóricos y guías
│   ├── GUIA_RESPUESTAS_EQUIPO.md       # Respuestas para la Guía Dinámica (Días 1, 2, 3)
│   ├── FICHA_DE_PROYECTO_AITARA_FINAL.md # Ficha oficial de entrega (Día 5)
│   ├── PITCH_DEMO_DAY_3_MINUTOS.md     # Guion del pitch y defensa Q&A
│   ├── MARCO_CONCEPTUAL_DIKW.md        # Marco teórico (DIKW y preguntas clave)
│   ├── architecture/                   # Diagramas Archify (HTML interactivo y PNG)
│   └── Organizacion/                   # Plantillas oficiales y versión completada (.docx)
└── src/
    ├── warehouse/              # Motor de base de datos dual (DuckDB / SQLite)
    │   └── db.py
    └── engine/                 # Motor de inferencia explicable (XAI)
        └── risk_model.py
```

---

## 👥 Equipo AITARA
- **Santiago Agustín Nuñez** — Lead Architect & ML Engineer
- **Joaquin Sanchez** — Backend & Data Engineer
- **Facundo Fraga** — Data Analyst & GIS Specialist
- **Ana Florencia Zayas** — Product Owner & Referente del Equipo (`zayasflorenciaana@gmail.com`)

**Mentores Asignados:** Enzo Mereles, Ulises.
