"""AITARA — Lector de Noticias Viales con Soporte Dual (LLM Gemini + Heurística Determinística).

Transforma artículos de prensa en incidentes normalizados (IncidenteSilver),
georreferencia mediante el AgenteInvestigador (con fallback territorial)
y persiste de forma idempotente en la capa Silver y DuckDB.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from src.contracts import IncidenteSilver
from src.engine.investigador import AgenteInvestigador
from src.warehouse.db import DBWrapper, SILVER_JSONL_PATH, load_silver_incidents_from_jsonl

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
logger = logging.getLogger(__name__)

MODELO_GEMINI = "gemini-2.5-flash"


class AgenteLector:
    def __init__(self, investigador: Optional[AgenteInvestigador] = None):
        self.investigador = investigador or AgenteInvestigador()
        self._genai_client = None

    def _get_genai_client(self):
        clave = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not clave:
            return None
        if self._genai_client is None:
            try:
                from google import genai
                self._genai_client = genai.Client(api_key=clave)
            except Exception as e:
                logger.warning("No se pudo instanciar cliente GenAI: %s. Se usará modo determinístico.", e)
        return self._genai_client

    def _extraer_con_heuristica(self, titulo: str, texto: str) -> Dict[str, Any]:
        """Extracción determinística offline por reglas regex."""
        t = f"{titulo} {texto}".lower()

        # Tipo de incidente
        tipo = "choque"
        if "vuelco" in t or "volc" in t:
            tipo = "vuelco"
        elif "atropell" in t:
            tipo = "atropello"
        elif "corte" in t or "bloqueo" in t:
            tipo = "corte_vial"
        elif "inund" in t or "aneg" in t:
            tipo = "anegamiento"
        elif "sem[aá]foro" in t and ("apagad" in t or "roto" in t or "fuera de servicio" in t):
            tipo = "semaforo_apagado"

        # Severidad (0=sin daños, 1=material, 2=heridos, 3=fatal)
        severidad = 1
        if re.search(r"\b(muert[oe]|falleci|sin vida|fatal|terapia intensiva)\b", t):
            severidad = 3
        elif re.search(r"\b(herid[ao]s?|lesionad[ao]s?|fractur[ao]|hospital|trasladad[ao]s?)\b", t):
            severidad = 2

        # Vehículos
        vehiculos = []
        if re.search(r"\bmoto(s|ciclist[ao])?\b", t):
            vehiculos.append("moto")
        if re.search(r"\bauto(s|m[oó]vil)?|coche|fiat|ford|renault|toyota|chevrolet|volkswagen\b", t):
            vehiculos.append("auto")
        if re.search(r"\bcamioneta|oroch|hilux|amarok|ranger\b", t):
            vehiculos.append("camioneta")
        if re.search(r"\bcolectivo(s)?|urbano\b", t):
            vehiculos.append("colectivo")
        if re.search(r"\bcami[oó]n(es)?\b", t):
            vehiculos.append("camión")
        if not vehiculos:
            vehiculos = ["auto"]

        # Calles y referencias espaciales
        calle_1 = None
        calle_2 = None
        referencia = None

        if "moreau de justo" in t or "213" in t:
            calle_1 = "Av. Alicia Moreau de Justo"
        elif "quaranta" in t:
            calle_1 = "Av. Quaranta"
        elif "uruguay" in t:
            calle_1 = "Av. Uruguay"
        elif "san martin" in t or "san martín" in t:
            calle_1 = "Av. San Martín"
        elif "corrientes" in t:
            calle_1 = "Av. Corrientes"
        elif "mitre" in t:
            calle_1 = "Av. Mitre"
        elif "lavalle" in t:
            calle_1 = "Av. Lavalle"

        # Detección de hitos
        if "naranjos" in t or "country" in t:
            referencia = "Country Los Naranjos"
        elif "autodromo" in t or "autódromo" in t:
            referencia = "Autódromo Rosamonte"
        elif "unam" in t or "campus" in t:
            referencia = "Campus UNaM"
        elif "puente" in t:
            referencia = "Puente Internacional"
        elif "san basilio" in t:
            referencia = "Colegio San Basilio"

        # Segunda calle si existe explícita
        if "tucuman" in t or "tucumán" in t:
            calle_2 = "Calle Tucumán"
        elif "tomas guido" in t or "tomás guido" in t:
            calle_2 = "Av. Tomás Guido"
        elif "lopez torres" in t or "lópez torres" in t:
            calle_2 = "Av. López Torres"
        elif "cabred" in t:
            calle_2 = "Av. Cabred"
        elif "santa cruz" in t:
            calle_2 = "Av. Santa Cruz"
        elif "andresito" in t:
            calle_2 = "Av. Andresito"

        return {
            "tipo_incidente": tipo,
            "severidad": severidad,
            "vehiculos": vehiculos,
            "calle_1": calle_1,
            "calle_2": calle_2,
            "referencia_espacial": referencia,
            "resumen": (titulo[:150] + "...") if len(titulo) > 150 else titulo
        }

    def _extraer_con_gemini(self, titulo: str, texto: str) -> Optional[Dict[str, Any]]:
        """Extracción asistida por Gemini con esquema JSON estricto."""
        client = self._get_genai_client()
        if client is None:
            return None

        prompt = f"""Sos un analista de tránsito y movilidad urbana de Posadas, Misiones.
Analizá la siguiente noticia vial y extraé los datos en formato JSON estricto:
Título: {titulo}
Texto: {texto[:2500]}

Respondé ÚNICAMENTE un JSON con este esquema (sin markdown ni código extra):
{{
  "tipo_incidente": "choque"|"vuelco"|"atropello"|"corte_vial"|"anegamiento"|"semaforo_apagado",
  "severidad": 0|1|2|3,
  "vehiculos": ["auto", "moto", etc.],
  "calle_1": "nombre de avenida o calle principal o null",
  "calle_2": "nombre de calle transversal si cruza o null",
  "referencia_espacial": "hito o punto de interés (ej: Country Los Naranjos, Autódromo, etc.) o null",
  "resumen": "síntesis de 1 a 2 oraciones del hecho vial"
}}
IMPORTANTE: Si no hay una segunda calle que corte la vía transversalmente, calle_2 DEBE ser null. Jamás inventes esquinas."""

        try:
            resp = client.models.generate_content(
                model=MODELO_GEMINI,
                contents=prompt
            )
            raw = (resp.text or "").strip()
            raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
            return json.loads(raw)
        except Exception as e:
            logger.warning("Fallo en extracción con Gemini: %s. Se recurre a heurística determinística.", e)
            return None

    def estructurar_noticia(self, articulo: Dict[str, Any]) -> IncidenteSilver:
        """Convierte una noticia cruda en un IncidenteSilver georreferenciado."""
        titulo = articulo.get("titulo", "")
        texto = articulo.get("texto", "")

        # 1. Extracción de entidades (Gemini si está disponible, o heurística)
        datos = self._extraer_con_gemini(titulo, texto)
        if not datos:
            datos = self._extraer_con_heuristica(titulo, texto)

        # 2. Resolución territorial y georreferenciación mediante AgenteInvestigador
        res_geo = self.investigador.resolver_georreferenciacion(
            calle_1=datos.get("calle_1"),
            calle_2=datos.get("calle_2"),
            referencia_espacial=datos.get("referencia_espacial"),
            texto_completo=f"{titulo} {texto}"
        )

        ubicacion_texto = res_geo.get("ubicacion_resuelta") or f"{datos.get('calle_1') or ''} {datos.get('calle_2') or ''}".strip()
        if not ubicacion_texto:
            ubicacion_texto = "Posadas (Ubicación en proceso de verificación)"

        # 3. Construcción del contrato IncidenteSilver
        return IncidenteSilver(
            id=articulo.get("id") or f"inc-web-{abs(hash(articulo.get('url', '')))}",
            fuente=articulo.get("fuente", "web_local"),
            titulo=titulo,
            url=articulo.get("url"),
            fecha_publicacion=datetime.now(timezone.utc),
            fecha_evento=datetime.now(timezone.utc),
            tipo_incidente=datos.get("tipo_incidente", "choque"),
            severidad=datos.get("severidad", 1),
            vehiculos=datos.get("vehiculos", ["auto"]),
            calle_1=datos.get("calle_1"),
            calle_2=datos.get("calle_2"),
            referencia_espacial=datos.get("referencia_espacial"),
            tipo_ubicacion=res_geo.get("tipo_ubicacion", "interseccion"),
            ubicacion_texto=ubicacion_texto,
            lat=res_geo["lat"],
            lon=res_geo["lon"],
            confianza=res_geo.get("confianza", 0.90),
            estado_verificacion="investigado" if res_geo.get("confianza", 0.9) < 0.8 else "curado",
            resumen=datos.get("resumen") or titulo,
            origen="real"
        )


def _obtener_urls_existentes() -> set:
    """Lee las URLs ya persistidas para deduplicación idempotente."""
    urls = set()
    if not SILVER_JSONL_PATH.exists():
        return urls
    with SILVER_JSONL_PATH.open("r", encoding="utf-8") as f:
        for linea in f:
            if not linea.strip():
                continue
            try:
                item = json.loads(linea)
                if item.get("url"):
                    urls.add(item["url"].strip().lower())
            except Exception:
                continue
    return urls


def procesar_e_ingestar_noticia(articulo: Dict[str, Any], db: DBWrapper, lector: Optional[AgenteLector] = None) -> Optional[IncidenteSilver]:
    """Procesa una nota, la deduplica por URL, la escribe a disco y actualiza DuckDB."""
    url = (articulo.get("url") or "").strip().lower()
    if not url:
        return None

    existentes = _obtener_urls_existentes()
    if url in existentes:
        logger.info("La noticia ya existe en la base (%s), se omite duplicado.", url)
        return None

    lector = lector or AgenteLector()
    incidente = lector.estructurar_noticia(articulo)

    # Persistir en JSONL
    linea_dict = incidente.model_dump(mode="json")
    with SILVER_JSONL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(linea_dict, ensure_ascii=False) + "\n")

    # Actualizar DuckDB inmediatamente
    load_silver_incidents_from_jsonl(db)
    logger.info("Nuevo incidente vial persistido e indexado: %s", incidente.titulo)
    return incidente
