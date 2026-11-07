# T08 — Lector real con caché

## Objetivo
Que el Lector exista en el código: convierte una noticia en un incidente estructurado y georreferenciado, y guarda el resultado para usarlo sin conexión.

## Contexto
- Los 12 incidentes de `data/silver/incidentes_posadas.jsonl` llegan ya estructurados; no hay código de extracción.
- `IncidenteSilver` en `src/contracts.py` ya define el formato de salida.

## Archivos permitidos
- `src/lector/` (nuevo)
- `src/ingesta/recolector_noticias.py` (nuevo)
- `data/bronze/` (nuevo)
- `data/silver/`
- `tests/`

## Qué hacer
1. **Recolector** (`src/ingesta/recolector_noticias.py`): descarga notas de los portales locales respetando sus términos de uso, y guarda título, texto, URL y fecha en `data/bronze/`.
2. **Lector** (`src/lector/`):
   - envía el texto al LLM con un esquema de salida fijo basado en `IncidenteSilver`;
   - exige un fragmento de evidencia por campo;
   - devuelve `null` en lo que no está en el texto;
   - no extrae nombres de personas;
   - resuelve la ubicación contra el nomenclador; si la confianza es baja, deriva al Investigador.
3. **Caché:** cada nota procesada se guarda en `data/silver/`, identificada por la URL, y no se vuelve a enviar al LLM.
4. **Modo demo:** sin clave de Gemini, el Lector lee la caché.

## Criterios de aceptación
- [ ] Hay un comando que procesa una nota y produce un `IncidenteSilver` válido.
- [ ] Sin conexión, el sistema arranca con la caché.
- [ ] Test con una nota de ejemplo y una respuesta simulada del LLM.
- [ ] Ningún incidente guardado contiene nombres de personas.

## Cómo verificar
```bash
python -m src.lector --url <url-de-una-nota>
python -m pytest -q tests
```

## Fuera de alcance
Programar la recolección periódica.
