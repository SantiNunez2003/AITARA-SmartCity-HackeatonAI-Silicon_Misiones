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

from src.contracts import FuenteRelacionada, IncidenteSilver
from src.engine.investigador import AgenteInvestigador
from src.ingesta.deduplicador import ZONA_POSADAS, buscar_duplicado, parsear_fecha
from src.ingesta.recolector import PATRON_EXCLUSION_NO_VIAL
from src.warehouse.db import DBWrapper, SILVER_JSONL_PATH, load_silver_incidents_from_jsonl

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
logger = logging.getLogger(__name__)

MODELOS_GEMINI = [
    os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite"
]


def _normalizar_prefijo_calle(calle: Optional[str]) -> Optional[str]:
    """Estandariza prefijos y nombres canónicos de arterias clave de Posadas."""
    if not calle:
        return None
    c = calle.strip()
    # Mapeo a formas canónicas de corredores clave
    if re.search(r"alicia moreau de justo", c, re.IGNORECASE):
        return "Av. Alicia Moreau de Justo"
    if re.search(r"\bquaranta\b", c, re.IGNORECASE):
        return "Av. Quaranta"
    if re.search(r"\buruguay\b", c, re.IGNORECASE):
        return "Av. Uruguay"
    if re.search(r"\bsan mart[ií]n\b", c, re.IGNORECASE):
        return "Av. San Martín"
    if re.search(r"\bcorrientes\b", c, re.IGNORECASE):
        return "Av. Corrientes"
    if re.search(r"\bmitre\b", c, re.IGNORECASE):
        return "Av. Mitre"
    if re.search(r"\blavalle\b", c, re.IGNORECASE):
        return "Av. Lavalle"
    if re.search(r"\btrincheras\b", c, re.IGNORECASE):
        return "Av. Trincheras de San José"
    if re.search(r"\bl[oó]pez torres\b", c, re.IGNORECASE):
        return "Av. López Torres"
    if re.search(r"\bcabred\b", c, re.IGNORECASE):
        return "Av. Cabred"
    if re.search(r"\bsanta cruz\b", c, re.IGNORECASE):
        return "Av. Santa Cruz"
    if re.search(r"\bandresito\b", c, re.IGNORECASE):
        return "Av. Andresito"
    if re.search(r"\btucum[aá]n\b", c, re.IGNORECASE):
        return "Calle Tucumán"
    if re.search(r"\bsan lorenzo\b", c, re.IGNORECASE):
        return "Calle San Lorenzo"
    if re.search(r"\bsanta fe\b", c, re.IGNORECASE):
        return "Calle Santa Fe"
    if re.search(r"\bbuenos aires\b", c, re.IGNORECASE):
        return "Calle Buenos Aires"
    if re.search(r"\bulises l[oó]pez\b", c, re.IGNORECASE):
        return "Av. Ulises López"
    if re.search(r"\bchacabuco\b", c, re.IGNORECASE):
        return "Av. Chacabuco"

    if re.match(r"^avenida\b", c, re.IGNORECASE):
        c = re.sub(r"^avenida\s+", "Av. ", c, flags=re.IGNORECASE)
    elif re.match(r"^av\.?\s*", c, re.IGNORECASE):
        c = re.sub(r"^av\.?\s*", "Av. ", c, flags=re.IGNORECASE)
    elif re.match(r"^calle\b", c, re.IGNORECASE):
        c = re.sub(r"^calle\s+", "Calle ", c, flags=re.IGNORECASE)
    return c


def _normalizar_referencia_espacial(ref: Optional[str]) -> Optional[str]:
    """Estandariza hitos urbanos reconocibles."""
    if not ref:
        return None
    r = ref.strip()
    if re.search(r"naranjos", r, re.IGNORECASE):
        return "Country Los Naranjos"
    if re.search(r"campus|unam", r, re.IGNORECASE):
        return "Campus UNaM"
    if re.search(r"puente", r, re.IGNORECASE):
        return "Puente Internacional"
    if re.search(r"san basilio", r, re.IGNORECASE):
        return "Colegio San Basilio"
    if re.search(r"hospital|madariaga|salud", r, re.IGNORECASE):
        return "Hospital Madariaga"
    if re.search(r"aeropuerto", r, re.IGNORECASE):
        return "Aeropuerto Posadas"
    if re.search(r"brete", r, re.IGNORECASE):
        return "Bahía El Brete"
    if re.search(r"villa cabello", r, re.IGNORECASE):
        return "Villa Cabello"
    return r


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

    def _extraer_con_heuristica(self, titulo: str, texto: str) -> Optional[Dict[str, Any]]:
        """Extracción determinística offline por reglas regex con filtro de exclusión."""
        t = f"{titulo} {texto}".lower()

        # Descartar si coincide con patrón de exclusión no vial
        if PATRON_EXCLUSION_NO_VIAL.search(t):
            return None

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

        # Detección de hitos urbanos válidos
        if "naranjos" in t or "country" in t:
            referencia = "Country Los Naranjos"
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

        # REGLA OBLIGATORIA: Si no hay arteria ni hito identificado, se rechaza
        if not calle_1 and not referencia:
            return None

        return {
            "es_siniestro_vial_urbano": True,
            "tiene_ubicacion_identificable": True,
            "tipo_incidente": tipo,
            "severidad": severidad,
            "vehiculos": vehiculos,
            "calle_1": calle_1,
            "calle_2": calle_2,
            "referencia_espacial": referencia,
            "resumen": (titulo[:150] + "...") if len(titulo) > 150 else titulo
        }

    def _extraer_con_gemini(self, titulo: str, texto: str) -> Optional[Dict[str, Any]]:
        """Extracción asistida por Gemini con filtro estricto de movilidad urbana y ubicación."""
        client = self._get_genai_client()
        if client is None:
            return None

        prompt = f"""Sos un analista de ingeniería vial y movilidad urbana de Posadas, Misiones.
Tu rol es evaluar si la siguiente noticia periodística reporta un siniestro vial o incidente en la vía pública con impacto en la movilidad urbana de Posadas.

CRITERIOS ESTRICTOS DE FILTRADO:
1. Siniestro Vial Urbano: DEBE ser un hecho de tránsito ocurrido en la red vial pública (calles, avenidas, travesías urbanas, rutas provinciales/nacionales dentro del ejido urbano de Posadas).
   - RECHAZAR terminantemente (es_siniestro_vial_urbano = false):
     * Accidentes aéreos (alas delta, planeadores, aeronaves, avionetas).
     * Accidentes náuticos o en el río Paraná.
     * Accidentes en circuitos de competición cerrados (autódromos como Rosamonte, kartódromos) durante carreras o entrenamientos deportivos.
     * Homenajes, vigilias, cadenas de oración o notas emotivas sin que haya ocurrido un corte o siniestro vial nuevo.
     * Hechos ocurridos fuera del municipio de Posadas (ej. Garupá, Candelaria, Oberá, etc.).
2. Ubicación Obligatoria en Posadas: DEBE contener al menos una arteria vial, cruce o hito urbano reconocible de Posadas. Si el hecho no especifica ninguna calle, avenida o hito territorial en Posadas, marcar tiene_ubicacion_identificable = false.

Título: {titulo}
Texto: {texto[:2500]}

Respondé ÚNICAMENTE un JSON con este esquema (sin bloques ni texto adicional):
{{
  "es_siniestro_vial_urbano": true|false,
  "tiene_ubicacion_identificable": true|false,
  "tipo_incidente": "choque"|"vuelco"|"atropello"|"corte_vial"|"anegamiento"|"semaforo_apagado",
  "severidad": 0|1|2|3,
  "vehiculos": ["auto", "moto", etc.],
  "calle_1": "nombre de avenida o calle principal o null",
  "calle_2": "nombre de calle transversal si cruza o null",
  "referencia_espacial": "hito o punto de interés urbano en Posadas o null",
  "resumen": "síntesis ejecutiva de 1 a 2 oraciones del hecho vial"
}}

IMPORTANTE: Si 'es_siniestro_vial_urbano' es false o 'tiene_ubicacion_identificable' es false, calle_1 y calle_2 deben ser null."""

        for modelo in MODELOS_GEMINI:
            try:
                if hasattr(client, "interactions") and hasattr(client.interactions, "create"):
                    res = client.interactions.create(model=modelo, input=prompt, store=False)
                    raw = getattr(res, "output_text", "") or ""
                else:
                    resp = client.models.generate_content(
                        model=modelo,
                        contents=prompt
                    )
                    raw = (resp.text or "").strip()
                raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
                if raw:
                    return json.loads(raw)
            except Exception as e:
                logger.warning("Fallo en extracción con modelo %s: %s. Probando fallback.", modelo, e)
                continue
        return None

    def estructurar_noticia(self, articulo: Dict[str, Any]) -> Optional[IncidenteSilver]:
        """Convierte una noticia cruda en un IncidenteSilver georreferenciado o None si no califica."""
        titulo = articulo.get("titulo", "")
        texto = articulo.get("texto", "")
        contenido_completo = f"{titulo} {texto}"

        # 0. Pre-filtro de exclusión estricto (ala delta, deportes, autódromo, oraciones, etc.)
        if PATRON_EXCLUSION_NO_VIAL.search(contenido_completo):
            logger.info("Noticia descartada por coincidir con exclusión no vial: '%s'", titulo[:60])
            return None

        # 1. Extracción de entidades (Gemini si está disponible, o heurística determinística)
        datos = self._extraer_con_gemini(titulo, texto)
        if datos:
            if not datos.get("es_siniestro_vial_urbano", True) or not datos.get("tiene_ubicacion_identificable", True):
                logger.info("Gemini determinó que la noticia no es un incidente vial urbano con ubicación: '%s'", titulo[:60])
                return None
        else:
            datos = self._extraer_con_heuristica(titulo, texto)

        if not datos:
            logger.info("Noticia descartada por no contener datos viales estructurables: '%s'", titulo[:60])
            return None

        calle_1 = _normalizar_prefijo_calle(datos.get("calle_1"))
        calle_2 = _normalizar_prefijo_calle(datos.get("calle_2"))
        referencia = _normalizar_referencia_espacial(datos.get("referencia_espacial"))

        # REGLA OBLIGATORIA: Todo incidente debe tener una arteria vial o hito identificado
        if not calle_1 and not referencia:
            logger.info("Noticia descartada por carecer de ubicación vial identificable: '%s'", titulo[:60])
            return None

        # 2. Resolución territorial y georreferenciación mediante AgenteInvestigador
        res_geo = self.investigador.resolver_georreferenciacion(
            calle_1=calle_1,
            calle_2=calle_2,
            referencia_espacial=referencia,
            texto_completo=contenido_completo
        )

        tipo_ubi = res_geo.get("tipo_ubicacion", "interseccion")
        if tipo_ubi not in ("interseccion", "corredor_hito", "punto_singular"):
            tipo_ubi = "indeterminado"

        raw_ubi = res_geo.get("ubicacion_resuelta") or f"{calle_1 or ''} {calle_2 or ''}".strip()
        if not raw_ubi or len(raw_ubi) > 80:
            raw_ubi = f"{calle_1 or ''} y {calle_2 or ''}".strip() or referencia or "Posadas"
        ubicacion_texto = raw_ubi[:80]

        requiere_revision = bool(res_geo.get("requiere_revision_humana", False))
        lat_res = res_geo.get("lat")
        lon_res = res_geo.get("lon")
        ubicacion_valida = bool(lat_res is not None and lon_res is not None and not requiere_revision)

        if requiere_revision or not ubicacion_valida:
            estado_verif = "pendiente"
        elif res_geo.get("confianza", 0.0) < 0.8:
            estado_verif = "investigado"
        else:
            estado_verif = "curado"

        # 3. Construcción del contrato IncidenteSilver
        return IncidenteSilver(
            id=articulo.get("id") or f"inc-web-{abs(hash(articulo.get('url', '')))}",
            fuente=articulo.get("fuente", "web_local"),
            titulo=titulo,
            url=articulo.get("url"),
            # Fecha de la nota; si el medio no la informa, la de captura.
            fecha_publicacion=parsear_fecha(articulo.get("fecha_publicacion"))
            or datetime.now(ZONA_POSADAS).replace(tzinfo=None),
            # La hora del hecho no se extrae del texto: queda nula.
            fecha_evento=None,
            tipo_incidente=datos.get("tipo_incidente", "choque"),
            severidad=datos.get("severidad", 1),
            vehiculos=datos.get("vehiculos", ["auto"]),
            calle_1=calle_1,
            calle_2=calle_2,
            referencia_espacial=referencia,
            tipo_ubicacion=tipo_ubi,
            ubicacion_texto=ubicacion_texto,
            lat=lat_res,
            lon=lon_res,
            ubicacion_valida=ubicacion_valida,
            confianza=res_geo.get("confianza", 0.0),
            estado_verificacion=estado_verif,
            requiere_revision_humana=requiere_revision,
            metodo=res_geo.get("metodo", "nomenclador"),
            pasos_resolucion=res_geo.get("pasos_resolucion", []),
            resumen=datos.get("resumen") or titulo,
            origen="real"
        )


def _leer_guardados(ruta: Path) -> List[Tuple[str, Dict[str, Any]]]:
    """Lee las líneas guardadas, conservando el texto original de cada una."""
    if not ruta.exists():
        return []
    guardados = []
    with ruta.open("r", encoding="utf-8") as f:
        for linea in f:
            if not linea.strip():
                continue
            try:
                guardados.append((linea.rstrip("\n"), json.loads(linea)))
            except json.JSONDecodeError:
                guardados.append((linea.rstrip("\n"), {}))
    return guardados


def _urls_guardadas(guardados: List[Tuple[str, Dict[str, Any]]]) -> set:
    """URLs ya procesadas: la principal de cada incidente y las de sus fuentes relacionadas."""
    urls = set()
    for _, item in guardados:
        for url in [item.get("url")] + [f.get("url") for f in item.get("fuentes_relacionadas") or []]:
            if url:
                urls.add(url.strip().lower())
    return urls


def _agregar_fuente_relacionada(ruta: Path, guardados, existente: Dict[str, Any], incidente: IncidenteSilver) -> Dict[str, Any]:
    """Registra la nota como otra fuente del incidente existente y reescribe solo esa línea."""
    actualizado = dict(existente)
    relacionadas = list(actualizado.get("fuentes_relacionadas") or [])
    relacionadas.append(FuenteRelacionada(fuente=incidente.fuente, url=incidente.url, titulo=incidente.titulo).model_dump())
    actualizado["fuentes_relacionadas"] = relacionadas
    lineas = [json.dumps(actualizado, ensure_ascii=False) if item.get("id") == existente.get("id") else texto
              for texto, item in guardados]
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    temporal.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    temporal.replace(ruta)
    return actualizado


def procesar_noticia(articulo: Dict[str, Any], db: DBWrapper, lector: Optional[AgenteLector] = None,
                     ruta: Path = SILVER_JSONL_PATH) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Procesa una nota y devuelve (estado, incidente).

    Estados: 'nuevo', 'duplicado_url' (la nota ya se procesó), 'duplicado_medio'
    (otro medio ya reportó el mismo hecho; se agrega como fuente relacionada),
    'descartado' (no es un incidente vial urbano con ubicación) o 'sin_url'.
    """
    url = (articulo.get("url") or "").strip().lower()
    if not url:
        return "sin_url", None

    guardados = _leer_guardados(ruta)
    if url in _urls_guardadas(guardados):
        logger.info("La noticia ya existe en la base (%s), se omite duplicado.", url)
        return "duplicado_url", None

    lector = lector or AgenteLector()
    try:
        incidente = lector.estructurar_noticia(articulo)
    except Exception as e:
        logger.error("Error al estructurar noticia '%s': %s", url, e)
        return "descartado", None

    if incidente is None:
        logger.info("Noticia descartada por filtros de movilidad/ubicación: %s", url)
        return "descartado", None

    existente = buscar_duplicado(incidente.model_dump(mode="json"), [item for _, item in guardados if item])
    if existente:
        actualizado = _agregar_fuente_relacionada(ruta, guardados, existente, incidente)
        logger.info("Mismo hecho que %s; se agrega %s como fuente relacionada.", existente.get("id"), incidente.fuente)
        return "duplicado_medio", actualizado

    with ruta.open("a", encoding="utf-8") as f:
        f.write(json.dumps(incidente.model_dump(mode="json"), ensure_ascii=False) + "\n")

    load_silver_incidents_from_jsonl(db)
    logger.info("Nuevo incidente vial persistido e indexado: %s", incidente.titulo)
    return "nuevo", incidente.model_dump(mode="json")


def procesar_e_ingestar_noticia(articulo: Dict[str, Any], db: DBWrapper, lector: Optional[AgenteLector] = None) -> Optional[IncidenteSilver]:
    """Compatibilidad: devuelve el incidente solo si es nuevo."""
    estado, incidente = procesar_noticia(articulo, db, lector)
    return IncidenteSilver(**incidente) if estado == "nuevo" else None
