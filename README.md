# AITARA — Soporte a decisiones para la movilidad urbana

AITARA integra información en una memoria común de la movilidad de Posadas. Analiza seguridad vial y fluidez para recomendar prioridades con evidencia; la decisión es humana. Los datos simulados se identifican como tales y permiten demostrar el sistema y validar el m?todo.

## Caso piloto

El prototipo contempla incidentes georreferenciados, zonas críticas, escenarios de precipitación en horario escolar y variación del riesgo con aporte por factor.

## Puesta en marcha

```bash
pip install -r requirements.txt
uvicorn api:app --reload
```

En otra terminal:

```bash
cd frontend && npm ci && npm run dev
```

## Estructura

- `api.py`: API y entrega del frontend compilado.
- `frontend/`: interfaz.
- `src/warehouse/`, `src/engine/`: almacenamiento y análisis.
- `docs/`: documentación técnica.

## 👥 Equipo AITARA
- **Santiago Agustín Nuñez** — Lead Architect & ML Engineer
- **Joaquin Sanchez** — Backend & Data Engineer
- **Facundo Fraga** — Data Analyst & GIS Specialist
- **Ana Florencia Zayas** — Product Owner & Referente del Equipo (`zayasflorenciaana@gmail.com`)

**Mentores Asignados:** Enzo Mereles, Ulises.


## Despliegue en Render

1. En Render, crear un **Web Service** desde **Public Git Repository** con `https://github.com/SantiNunez2003/AITARA-SmartCity-HackeatonAI-Silicon_Misiones` y elegir la rama `master`.
2. Seleccionar runtime **Docker** y plan **Free**.
3. Opcionalmente, cargar `GEMINI_API_KEY` como variable secreta del servicio. Sin ella, la aplicación funciona en modo respaldo.
4. Configurar el health check en `/api/status` y realizar el deploy manual.

El servicio gratuito se duerme después de 15 minutos de inactividad; la primera solicitud posterior puede tardar mientras vuelve a iniciar. URL pública: https://aitara-smartcity-hackeatonai-silicon.onrender.com/
