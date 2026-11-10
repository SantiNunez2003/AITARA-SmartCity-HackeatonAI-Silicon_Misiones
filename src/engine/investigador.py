"""AITARA - Agente Investigador con Nomenclador OpenStreetMap y Function Calling de Gemini.

Resuelve la ubicación de incidentes viales en Posadas:
1. Primero consulta directamente el nomenclador local de OpenStreetMap (data/territorio/).
2. Si el caso es ambiguo, utiliza Gemini con function calling (máximo 5 consultas) sobre las funciones del nomenclador.
3. Aplica guardrails estrictos: nunca inventa coordenadas ni usa coordenadas por defecto; toda coordenada final debe provenir exactamente de un resultado del nomenclador dentro del área de Posadas.
"""

from difflib import SequenceMatcher
import json
import logging
import math
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv

from src.territorio.descargar_osm import (
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    normalizar_nombre,
    quitar_tildes,
)
from src.territorio.nomenclador import (
    STOPWORDS_LUGAR,
    TOKENS_GENERICOS_LUGAR,
    _cargar_calles,
    _cargar_lugares,
    buscar_calle,
    buscar_interseccion,
    buscar_lugar,
    punto_sobre_calle_cerca_de,
)

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
logger = logging.getLogger(__name__)

# Constantes de confianza por reglas (no las decide Gemini)
CONFIANZA_INTERSECCION_OSM = 0.95
CONFIANZA_LUGAR_UNICO = 0.85
CONFIANZA_PUNTO_SOBRE_CALLE_CERCA_DE_LUGAR = 0.75
CONFIANZA_SOLO_CALLE = 0.50
CONFIANZA_SIN_RESOLVER = 0.0

MAX_CONSULTAS_GEMINI = 5
DISTANCIA_MAX_CORREDOR_METROS = 1500.0
DISTANCIA_VALIDACION_CORREDOR_METROS = 500.0

_VOCABULARIO_TERRITORIAL: Optional[Set[str]] = None

PALABRAS_VIALES_PERMITIDAS = {
    "av", "avenida", "calle", "pasaje", "pje", "boulevard", "bv", "ruta",
    "ex", "rn", "rp", "nacional", "provincial", "acceso", "rotonda", "puente",
    "internacional", "campus", "hospital", "parque", "salud", "colegio",
    "escuela", "instituto", "universidad", "unam", "country", "barrio",
    "club", "casino", "autodromo", "terminal", "transferencia", "estacion",
    "aeropuerto", "bahia", "villa", "plaza", "plazoleta", "centro", "microcentro",
    "frente", "cerca", "metros", "esquina", "cruce", "interseccion", "sobre",
    "entre", "casi", "llegando", "altura", "norte", "sur", "este", "oeste",
    "de", "del", "la", "las", "el", "los", "y", "e", "a", "al", "en", "por",
    "posadas", "misiones",
}


def _obtener_vocabulario_territorial() -> Set[str]:
    global _VOCABULARIO_TERRITORIAL
    if _VOCABULARIO_TERRITORIAL is None:
        vocab: Set[str] = set(PALABRAS_VIALES_PERMITIDAS)
        for c in _cargar_calles():
            for texto in [c.get("nombre_oficial", ""), c.get("nombre_normalizado", "")] + list(c.get("aliases", [])):
                for tok in re.findall(r"[a-z0-9]+", quitar_tildes(str(texto).lower())):
                    if tok:
                        vocab.add(tok)
        for l in _cargar_lugares():
            for texto in [l.get("nombre_oficial", ""), l.get("nombre_normalizado", "")] + list(l.get("aliases", [])):
                for tok in re.findall(r"[a-z0-9]+", quitar_tildes(str(texto).lower())):
                    if tok:
                        vocab.add(tok)
        _VOCABULARIO_TERRITORIAL = vocab
    return _VOCABULARIO_TERRITORIAL


def _sanitizar_texto_con_entidades(texto: str, nombres_osm_coincidentes: List[str]) -> str:
    """Conserva únicamente palabras viales y tokens presentes en las entidades OSM encontradas."""
    if not isinstance(texto, str) or not texto.strip():
        return ""
    tokens_osm: Set[str] = set(PALABRAS_VIALES_PERMITIDAS)
    for nombre in nombres_osm_coincidentes:
        for tok in re.findall(r"[a-z0-9]+", quitar_tildes(str(nombre).lower())):
            if tok:
                tokens_osm.add(tok)

    palabras = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9.]+", texto)
    limpias: List[str] = []
    for p in palabras:
        tok = re.sub(r"[^a-z0-9]", "", quitar_tildes(p.lower()))
        if not tok:
            continue
        if tok.isdigit() or tok in tokens_osm:
            limpias.append(p)
        elif len(tok) >= 5 and any(
            abs(len(tok) - len(v)) <= 2 and SequenceMatcher(None, tok, v).ratio() >= 0.82
            for v in tokens_osm
            if len(v) >= 5
        ):
            limpias.append(p)
    return " ".join(limpias) if limpias else "[consulta_territorial]"


def _en_posadas(lat: Optional[float], lon: Optional[float]) -> bool:
    if lat is None or lon is None:
        return False
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    if not (math.isfinite(lat_f) and math.isfinite(lon_f)):
        return False
    return (LAT_MIN <= lat_f <= LAT_MAX) and (LON_MIN <= lon_f <= LON_MAX)


def _clave_coord(lat: float, lon: float) -> Tuple[float, float]:
    return (round(float(lat), 6), round(float(lon), 6))


def _es_referencia_vaga(referencia: Optional[str]) -> bool:
    if not referencia or not referencia.strip():
        return True
    norm = normalizar_nombre(referencia)
    tokens = [
        t for t in norm.split()
        if t and t not in STOPWORDS_LUGAR and t not in TOKENS_GENERICOS_LUGAR
    ]
    return len(tokens) == 0


class AgenteInvestigador:
    def __init__(self):
        self._genai_client = None

    def _get_genai_client(self):
        if self._genai_client is not None:
            return self._genai_client
        clave = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not clave:
            return None
        try:
            from google import genai
            self._genai_client = genai.Client(api_key=clave)
            return self._genai_client
        except Exception as exc:
            logger.warning("No se pudo inicializar cliente Gemini en Investigador: %s", exc)
            return None

    def _obtener_modelo(self) -> str:
        return os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite"

    def validar_consistencia_corredor(self, calle: str, lat: float, lon: float) -> bool:
        """Verifica con la geometría real de OSM que (lat, lon) se encuentre dentro del corredor de la calle."""
        if not _en_posadas(lat, lon):
            return False
        punto = punto_sobre_calle_cerca_de(calle, lat, lon)
        if not punto:
            return False
        return float(punto.get("distancia_metros", 999999.0)) <= DISTANCIA_VALIDACION_CORREDOR_METROS

    def _ejecutar_herramienta(
        self,
        nombre_fn: str,
        parametros: Dict[str, Any],
        pasos_resolucion: List[Dict[str, Any]],
        coordenadas_validas: Dict[Tuple[float, float], Dict[str, Any]],
    ) -> Any:
        if nombre_fn == "buscar_calle":
            nombre = str(parametros.get("nombre", ""))
            res = buscar_calle(nombre)
            res_sin_nodos = [
                {
                    "osm_id": r["osm_id"],
                    "nombre_oficial": r["nombre_oficial"],
                    "lat": r["lat"],
                    "lon": r["lon"],
                    "similitud": r["similitud"],
                    "fuente": r["fuente"],
                }
                for r in res[:5]
            ]
            for r in res_sin_nodos:
                if _en_posadas(r["lat"], r["lon"]):
                    k = _clave_coord(r["lat"], r["lon"])
                    coordenadas_validas.setdefault(
                        k,
                        {
                            "lat": r["lat"],
                            "lon": r["lon"],
                            "osm_id": r["osm_id"],
                            "nombre_oficial": r["nombre_oficial"],
                            "origen_herramienta": "buscar_calle",
                        },
                    )
            nombres_osm = [r["nombre_oficial"] for r in res_sin_nodos]
            params_limpios = {"nombre": _sanitizar_texto_con_entidades(nombre, nombres_osm)}
            resumen = (
                f"{len(res)} calles encontradas: "
                + ", ".join(f"{r['nombre_oficial']} (osm_id={r['osm_id']})" for r in res_sin_nodos[:3])
                if res_sin_nodos
                else "Sin coincidencias de calle"
            )
            pasos_resolucion.append({
                "funcion": "buscar_calle",
                "parametros": params_limpios,
                "resumen_resultado": resumen,
            })
            return res_sin_nodos

        if nombre_fn == "buscar_interseccion":
            c1 = str(parametros.get("calle_1", ""))
            c2 = str(parametros.get("calle_2", ""))
            res = buscar_interseccion(c1, c2)
            nombres_osm = [
                res.get("nombre_oficial", ""),
                res.get("calle_1_oficial", ""),
                res.get("calle_2_oficial", ""),
            ]
            if not res.get("encontrada"):
                nombres_osm.extend(r["nombre_oficial"] for r in (buscar_calle(c1)[:1] + buscar_calle(c2)[:1]))
            params_limpios = {
                "calle_1": _sanitizar_texto_con_entidades(c1, nombres_osm),
                "calle_2": _sanitizar_texto_con_entidades(c2, nombres_osm),
            }
            if res.get("encontrada") and _en_posadas(res.get("lat"), res.get("lon")):
                k = _clave_coord(res["lat"], res["lon"])
                coordenadas_validas[k] = {
                    "lat": res["lat"],
                    "lon": res["lon"],
                    "osm_id": res["osm_id"],
                    "nombre_oficial": res["nombre_oficial"],
                    "origen_herramienta": "buscar_interseccion",
                }
                resumen = (
                    f"Cruce encontrado: {res['nombre_oficial']} "
                    f"({res['lat']}, {res['lon']}, osm_id={res['osm_id']})"
                )
            else:
                resumen = res.get("mensaje", "Las calles no se cruzan")
            pasos_resolucion.append({
                "funcion": "buscar_interseccion",
                "parametros": params_limpios,
                "resumen_resultado": resumen,
            })
            return res

        if nombre_fn == "buscar_lugar":
            texto = str(parametros.get("texto", ""))
            res = buscar_lugar(texto)
            res_recortado = res[:5]
            for r in res_recortado:
                if _en_posadas(r["lat"], r["lon"]):
                    k = _clave_coord(r["lat"], r["lon"])
                    coordenadas_validas.setdefault(
                        k,
                        {
                            "lat": r["lat"],
                            "lon": r["lon"],
                            "osm_id": r["osm_id"],
                            "nombre_oficial": r["nombre_oficial"],
                            "origen_herramienta": "buscar_lugar",
                            "cantidad_coincidencias": len(res),
                        },
                    )
            nombres_osm = [r["nombre_oficial"] for r in res_recortado]
            params_limpios = {"texto": _sanitizar_texto_con_entidades(texto, nombres_osm)}
            resumen = (
                f"{len(res)} lugares encontrados: "
                + ", ".join(
                    f"{r['nombre_oficial']} ({r['lat']}, {r['lon']}, osm_id={r['osm_id']})"
                    for r in res_recortado[:3]
                )
                if res_recortado
                else "Sin coincidencias de lugar"
            )
            pasos_resolucion.append({
                "funcion": "buscar_lugar",
                "parametros": params_limpios,
                "resumen_resultado": resumen,
            })
            return res_recortado

        if nombre_fn == "punto_sobre_calle_cerca_de":
            calle = str(parametros.get("calle", ""))
            lat = float(parametros.get("lat", 0.0))
            lon = float(parametros.get("lon", 0.0))
            res = punto_sobre_calle_cerca_de(calle, lat, lon)
            nombres_osm = [res["nombre_oficial"]] if res else []
            params_limpios = {
                "calle": _sanitizar_texto_con_entidades(calle, nombres_osm),
                "lat": lat,
                "lon": lon,
            }
            if res and _en_posadas(res.get("lat"), res.get("lon")):
                k = _clave_coord(res["lat"], res["lon"])
                coordenadas_validas[k] = {
                    "lat": res["lat"],
                    "lon": res["lon"],
                    "osm_id": res["osm_id"],
                    "nombre_oficial": res["nombre_oficial"],
                    "origen_herramienta": "punto_sobre_calle_cerca_de",
                    "distancia_metros": res.get("distancia_metros", 0.0),
                }
                resumen = (
                    f"Punto sobre {res['nombre_oficial']} en ({res['lat']}, {res['lon']}, "
                    f"osm_id={res['osm_id']}, dist={res['distancia_metros']}m)"
                )
            else:
                resumen = "No se encontró punto sobre la calle"
            pasos_resolucion.append({
                "funcion": "punto_sobre_calle_cerca_de",
                "parametros": params_limpios,
                "resumen_resultado": resumen,
            })
            return res

        raise ValueError(f"Herramienta desconocida: {nombre_fn}")

    def _construir_respuesta(
        self,
        *,
        estado: str,
        lat: Optional[float],
        lon: Optional[float],
        ubicacion_resuelta: str,
        tipo_ubicacion: str,
        confianza: float,
        metodo: str,
        requiere_revision_humana: bool,
        pasos_resolucion: List[Dict[str, Any]],
        osm_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        return {
            "estado": estado,
            "lat": lat,
            "lon": lon,
            "osm_id": osm_id,
            "ubicacion_resuelta": ubicacion_resuelta[:80] if ubicacion_resuelta else "Posadas (En revisión humana)",
            "tipo_ubicacion": tipo_ubicacion,
            "confianza": confianza,
            "metodo": metodo,
            "requiere_revision_humana": requiere_revision_humana,
            "pasos_resolucion": pasos_resolucion,
        }

    def _derivar_revision_humana(
        self,
        calle_1: Optional[str],
        calle_2: Optional[str],
        referencia_espacial: Optional[str],
        pasos_resolucion: List[Dict[str, Any]],
        coordenadas_validas: Dict[Tuple[float, float], Dict[str, Any]],
        metodo: str,
    ) -> Dict[str, Any]:
        # Si hay una sola calle identificada en el nomenclador, la confianza es 0.50; de lo contrario 0.0.
        # En ambos casos va a revisión humana y SIN coordenadas inventadas ni por defecto (lat=None, lon=None).
        calle_encontrada = None
        for info in coordenadas_validas.values():
            if info.get("origen_herramienta") == "buscar_calle":
                calle_encontrada = info
                break

        if calle_encontrada is None and calle_1 and not any(p["funcion"] == "buscar_calle" for p in pasos_resolucion):
            res_c = self._ejecutar_herramienta(
                "buscar_calle",
                {"nombre": calle_1},
                pasos_resolucion,
                coordenadas_validas,
            )
            if res_c:
                calle_encontrada = res_c[0]

        if calle_encontrada is not None:
            confianza = CONFIANZA_SOLO_CALLE
            ubi = f"{calle_encontrada.get('nombre_oficial', calle_1)} (sin punto preciso)"
        else:
            confianza = CONFIANZA_SIN_RESOLVER
            partes = [x for x in (calle_1, calle_2, referencia_espacial) if x]
            ubi = " - ".join(partes) if partes else "Posadas (ubicación sin resolver)"

        return self._construir_respuesta(
            estado="revisión humana",
            lat=None,
            lon=None,
            ubicacion_resuelta=ubi,
            tipo_ubicacion="indeterminado",
            confianza=confianza,
            metodo=metodo,
            requiere_revision_humana=True,
            pasos_resolucion=pasos_resolucion,
        )

    def _validar_coordenada_de_herramientas(
        self,
        lat: Any,
        lon: Any,
        coordenadas_validas: Dict[Tuple[float, float], Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        try:
            lat_f, lon_f = float(lat), float(lon)
        except (TypeError, ValueError):
            return None
        if not _en_posadas(lat_f, lon_f):
            return None
        clave = _clave_coord(lat_f, lon_f)
        if clave in coordenadas_validas:
            return coordenadas_validas[clave]
        # Tolerancia únicamente por redondeo de punto flotante de 6 decimales (1e-6)
        for (k_lat, k_lon), meta in coordenadas_validas.items():
            if abs(lat_f - k_lat) <= 1e-6 and abs(lon_f - k_lon) <= 1e-6:
                return meta
        return None

    def _extraer_function_calls(self, resp: Any) -> List[Any]:
        fcs = getattr(resp, "function_calls", None)
        if fcs:
            return list(fcs)
        extraidos = []
        for cand in getattr(resp, "candidates", []) or []:
            content = getattr(cand, "content", None)
            for part in getattr(content, "parts", []) or []:
                fc = getattr(part, "function_call", None)
                if fc and getattr(fc, "name", None):
                    extraidos.append(fc)
        return extraidos

    def _declarar_herramientas_gemini(self):
        from google.genai import types

        return [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="buscar_calle",
                        description="Busca calles de Posadas en OpenStreetMap con tolerancia a errores de escritura.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "nombre": types.Schema(type="STRING", description="Nombre de la calle o avenida.")
                            },
                            required=["nombre"],
                        ),
                    ),
                    types.FunctionDeclaration(
                        name="buscar_interseccion",
                        description="Busca las coordenadas de la intersección o rotonda entre dos calles de Posadas en OpenStreetMap.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "calle_1": types.Schema(type="STRING", description="Primera calle o avenida."),
                                "calle_2": types.Schema(type="STRING", description="Segunda calle o avenida."),
                            },
                            required=["calle_1", "calle_2"],
                        ),
                    ),
                    types.FunctionDeclaration(
                        name="buscar_lugar",
                        description="Busca lugares de referencia (rotondas, escuelas, hospitales, puentes, casinos, barrios) en Posadas.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "texto": types.Schema(type="STRING", description="Nombre del lugar o hito de referencia.")
                            },
                            required=["texto"],
                        ),
                    ),
                    types.FunctionDeclaration(
                        name="punto_sobre_calle_cerca_de",
                        description="Obtiene el punto sobre una calle más cercano a unas coordenadas (lat, lon) de un lugar de referencia.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "calle": types.Schema(type="STRING", description="Nombre de la calle o avenida."),
                                "lat": types.Schema(type="NUMBER", description="Latitud del lugar de referencia."),
                                "lon": types.Schema(type="NUMBER", description="Longitud del lugar de referencia."),
                            },
                            required=["calle", "lat", "lon"],
                        ),
                    ),
                ]
            )
        ]

    def _resolver_con_gemini(
        self,
        calle_1: Optional[str],
        calle_2: Optional[str],
        referencia_espacial: Optional[str],
        texto_completo: str,
        pasos_resolucion: List[Dict[str, Any]],
        coordenadas_validas: Dict[Tuple[float, float], Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        client = self._get_genai_client()
        if client is None:
            return None

        modelo = self._obtener_modelo()
        prompt = f"""Sos el Agente Investigador geoespacial de AITARA en Posadas, Misiones.
Debés determinar la ubicación exacta del incidente vial usando EXCLUSIVAMENTE las herramientas del nomenclador OpenStreetMap (buscar_calle, buscar_interseccion, buscar_lugar, punto_sobre_calle_cerca_de).

Datos extraídos:
- calle_1: {calle_1 or 'no especificada'}
- calle_2: {calle_2 or 'no especificada'}
- referencia_espacial: {referencia_espacial or 'no especificada'}
- texto de la nota: {texto_completo[:1500]}

REGLAS OBLIGATORIAS:
1. Consultá las funciones del nomenclador para encontrar la intersección, el lugar de referencia o el punto sobre la calle cerca del lugar.
2. Tenés como máximo {MAX_CONSULTAS_GEMINI} consultas en total.
3. NO inventes coordenadas. Al finalizar las consultas, respondé ÚNICAMENTE un JSON con las coordenadas EXACTAS devueltas por alguna de las funciones consultadas:
{{
  "resuelto": true | false,
  "lat": <latitud exacta devuelta por la herramienta o null>,
  "lon": <longitud exacta devuelta por la herramienta o null>,
  "ubicacion_resuelta": "<descripción breve de la ubicación oficial>",
  "modo_resolucion": "interseccion" | "lugar_unico" | "punto_sobre_calle" | "solo_calle" | "sin_resolver"
}}"""

        try:
            from google.genai import types

            herramientas = self._declarar_herramientas_gemini()
            config = types.GenerateContentConfig(
                tools=herramientas,
                temperature=0.0,
            )
            contenidos: List[Any] = [
                types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
            ]
        except Exception:
            herramientas = None
            config = None
            contenidos = [prompt]

        consultas_realizadas = 0

        try:
            for _ in range(MAX_CONSULTAS_GEMINI + 1):
                resp = client.models.generate_content(
                    model=modelo,
                    contents=contenidos,
                    config=config,
                )
                fcs = self._extraer_function_calls(resp)

                if fcs:
                    partes_respuesta_fn = []
                    cand_content = None
                    if getattr(resp, "candidates", None):
                        cand_content = getattr(resp.candidates[0], "content", None)
                    if cand_content is not None:
                        contenidos.append(cand_content)

                    for fc in fcs:
                        consultas_realizadas += 1
                        if consultas_realizadas > MAX_CONSULTAS_GEMINI:
                            logger.warning("Gemini superó el máximo de %d consultas.", MAX_CONSULTAS_GEMINI)
                            return self._derivar_revision_humana(
                                calle_1, calle_2, referencia_espacial, pasos_resolucion, coordenadas_validas, metodo="gemini"
                            )
                        nombre_fn = getattr(fc, "name", "")
                        args_fn = dict(getattr(fc, "args", {}) or {})
                        resultado_fn = self._ejecutar_herramienta(
                            nombre_fn, args_fn, pasos_resolucion, coordenadas_validas
                        )
                        try:
                            from google.genai import types

                            partes_respuesta_fn.append(
                                types.Part.from_function_response(
                                    name=nombre_fn,
                                    response={"result": resultado_fn},
                                )
                            )
                        except Exception:
                            partes_respuesta_fn.append({"name": nombre_fn, "response": {"result": resultado_fn}})

                    try:
                        from google.genai import types

                        contenidos.append(types.Content(role="user", parts=partes_respuesta_fn))
                    except Exception:
                        contenidos.append(partes_respuesta_fn)
                    continue

                # Respuesta final de Gemini (sin más function calls)
                raw = (getattr(resp, "text", "") or "").strip()
                raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
                match_json = re.search(r"\{.*\}", raw, flags=re.DOTALL)
                if not match_json:
                    return self._derivar_revision_humana(
                        calle_1, calle_2, referencia_espacial, pasos_resolucion, coordenadas_validas, metodo="gemini"
                    )
                datos = json.loads(match_json.group(0))
                if not datos.get("resuelto") or datos.get("modo_resolucion") in ("solo_calle", "sin_resolver"):
                    return self._derivar_revision_humana(
                        calle_1, calle_2, referencia_espacial, pasos_resolucion, coordenadas_validas, metodo="gemini"
                    )

                meta_coord = self._validar_coordenada_de_herramientas(
                    datos.get("lat"), datos.get("lon"), coordenadas_validas
                )
                if meta_coord is None:
                    logger.warning(
                        "Guardrail Investigador: Gemini propuso coordenadas (%s, %s) que no provienen del nomenclador o están fuera de Posadas.",
                        datos.get("lat"),
                        datos.get("lon"),
                    )
                    return self._derivar_revision_humana(
                        calle_1, calle_2, referencia_espacial, pasos_resolucion, coordenadas_validas, metodo="gemini"
                    )

                origen_h = meta_coord.get("origen_herramienta")
                if origen_h == "buscar_calle":
                    # Solo una calle sin punto preciso -> revisión humana con confianza 0.50
                    return self._derivar_revision_humana(
                        calle_1, calle_2, referencia_espacial, pasos_resolucion, coordenadas_validas, metodo="gemini"
                    )

                if origen_h == "buscar_interseccion":
                    confianza = CONFIANZA_INTERSECCION_OSM
                    tipo_ubi = "interseccion"
                elif origen_h == "punto_sobre_calle_cerca_de":
                    confianza = CONFIANZA_PUNTO_SOBRE_CALLE_CERCA_DE_LUGAR
                    tipo_ubi = "corredor_hito"
                else:
                    confianza = CONFIANZA_LUGAR_UNICO
                    tipo_ubi = "punto_singular"

                ubi_resuelta = datos.get("ubicacion_resuelta") or meta_coord.get("nombre_oficial") or "Posadas"
                return self._construir_respuesta(
                    estado="resuelto",
                    lat=meta_coord["lat"],
                    lon=meta_coord["lon"],
                    osm_id=meta_coord.get("osm_id"),
                    ubicacion_resuelta=ubi_resuelta,
                    tipo_ubicacion=tipo_ubi,
                    confianza=confianza,
                    metodo="gemini",
                    requiere_revision_humana=False,
                    pasos_resolucion=pasos_resolucion,
                )

            return self._derivar_revision_humana(
                calle_1, calle_2, referencia_espacial, pasos_resolucion, coordenadas_validas, metodo="gemini"
            )
        except Exception as exc:
            logger.warning("Fallo al consultar Gemini en Investigador: %s. Se usa respaldo del nomenclador.", exc)
            return None

    def _intentar_desambiguar_texto_con_nomenclador(
        self,
        calle_1: Optional[str],
        calle_2: Optional[str],
        referencia_espacial: Optional[str],
        texto_completo: str,
        pasos_resolucion: List[Dict[str, Any]],
        coordenadas_validas: Dict[Tuple[float, float], Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Desambiguación determinística offline sobre el nomenclador cuando Gemini no está disponible."""
        texto_norm = normalizar_nombre(f"{referencia_espacial or ''} {texto_completo}")
        if not texto_norm:
            return None

        # Detectar calles mencionadas en el texto (ej. "rotonda de Quaranta y Uruguay")
        calles_principales = [
            c for c in _cargar_calles()
            if len(c["nombre_normalizado"]) >= 5
            and c["nombre_normalizado"] not in TOKENS_GENERICOS_LUGAR
            and not c["nombre_normalizado"].startswith(("colectora ", "bicisenda ", "senda ", "rotonda"))
            and re.search(rf"\b{re.escape(c['nombre_normalizado'])}\b", texto_norm)
        ]
        # Ordenar por longitud de nombre descendente para preferir nombres completos
        calles_principales.sort(key=lambda x: -len(x["nombre_normalizado"]))
        nombres_detectados: List[str] = []
        if calle_1:
            nombres_detectados.append(calle_1)
        if calle_2 and calle_2 not in nombres_detectados:
            nombres_detectados.append(calle_2)
        for c in calles_principales:
            if not any(
                normalizar_nombre(existente) == c["nombre_normalizado"]
                or c["nombre_normalizado"] in normalizar_nombre(existente)
                for existente in nombres_detectados
            ):
                nombres_detectados.append(c["nombre_oficial"])
            if len(nombres_detectados) >= 3:
                break

        if len(nombres_detectados) >= 2:
            cruce = self._ejecutar_herramienta(
                "buscar_interseccion",
                {"calle_1": nombres_detectados[0], "calle_2": nombres_detectados[1]},
                pasos_resolucion,
                coordenadas_validas,
            )
            if cruce.get("encontrada") and _en_posadas(cruce.get("lat"), cruce.get("lon")):
                return self._construir_respuesta(
                    estado="resuelto",
                    lat=cruce["lat"],
                    lon=cruce["lon"],
                    osm_id=cruce.get("osm_id"),
                    ubicacion_resuelta=cruce["nombre_oficial"],
                    tipo_ubicacion="interseccion",
                    confianza=CONFIANZA_INTERSECCION_OSM,
                    metodo="nomenclador",
                    requiere_revision_humana=False,
                    pasos_resolucion=pasos_resolucion,
                )

        # Si hay lugares mencionados en texto_completo y aún no se consultó buscar_lugar, buscarlos
        lugares_cand = [
            info for info in coordenadas_validas.values()
            if info.get("origen_herramienta") == "buscar_lugar"
        ]
        if not lugares_cand and texto_completo:
            self._ejecutar_herramienta(
                "buscar_lugar",
                {"texto": texto_completo},
                pasos_resolucion,
                coordenadas_validas,
            )
            lugares_cand = [
                info for info in coordenadas_validas.values()
                if info.get("origen_herramienta") == "buscar_lugar"
            ]

        if lugares_cand and nombres_detectados:
            calle_ref = nombres_detectados[0]
            mejor_punto = None
            for lug in lugares_cand:
                p = self._ejecutar_herramienta(
                    "punto_sobre_calle_cerca_de",
                    {"calle": calle_ref, "lat": lug["lat"], "lon": lug["lon"]},
                    pasos_resolucion,
                    coordenadas_validas,
                )
                if p and _en_posadas(p.get("lat"), p.get("lon")):
                    if mejor_punto is None or p["distancia_metros"] < mejor_punto[0]["distancia_metros"]:
                        mejor_punto = (p, lug)
            if mejor_punto and mejor_punto[0]["distancia_metros"] <= DISTANCIA_MAX_CORREDOR_METROS:
                p, lug = mejor_punto
                return self._construir_respuesta(
                    estado="resuelto",
                    lat=p["lat"],
                    lon=p["lon"],
                    osm_id=p.get("osm_id"),
                    ubicacion_resuelta=f"{p['nombre_oficial']} cerca de {lug['nombre_oficial']}",
                    tipo_ubicacion="corredor_hito",
                    confianza=CONFIANZA_PUNTO_SOBRE_CALLE_CERCA_DE_LUGAR,
                    metodo="nomenclador",
                    requiere_revision_humana=False,
                    pasos_resolucion=pasos_resolucion,
                )

        return None

    def resolver_georreferenciacion(
        self,
        calle_1: Optional[str] = None,
        calle_2: Optional[str] = None,
        referencia_espacial: Optional[str] = None,
        texto_completo: str = "",
    ) -> Dict[str, Any]:
        """Resuelve la ubicación de un incidente vial en Posadas:
        1. Primero sin Gemini usando el nomenclador local de OpenStreetMap.
        2. Si es ambiguo, consulta a Gemini con function calling (máximo 5 consultas) y valida sus coordenadas.
        3. Si no se puede determinar con certeza, deriva a revisión humana sin coordenadas inventadas.
        """
        pasos_resolucion: List[Dict[str, Any]] = []
        coordenadas_validas: Dict[Tuple[float, float], Dict[str, Any]] = {}

        # --- PASO 1: Resolución directa con el nomenclador local (sin Gemini) ---
        # 1A. Intersección explícita entre calle_1 y calle_2
        if calle_1 and calle_2:
            cruce = self._ejecutar_herramienta(
                "buscar_interseccion",
                {"calle_1": calle_1, "calle_2": calle_2},
                pasos_resolucion,
                coordenadas_validas,
            )
            if cruce.get("encontrada") and _en_posadas(cruce.get("lat"), cruce.get("lon")):
                return self._construir_respuesta(
                    estado="resuelto",
                    lat=cruce["lat"],
                    lon=cruce["lon"],
                    osm_id=cruce.get("osm_id"),
                    ubicacion_resuelta=cruce["nombre_oficial"],
                    tipo_ubicacion="interseccion",
                    confianza=CONFIANZA_INTERSECCION_OSM,
                    metodo="nomenclador",
                    requiere_revision_humana=False,
                    pasos_resolucion=pasos_resolucion,
                )

        # 1B. Lugar de referencia explícito y no vago
        if referencia_espacial and not _es_referencia_vaga(referencia_espacial):
            lugares = self._ejecutar_herramienta(
                "buscar_lugar",
                {"texto": referencia_espacial},
                pasos_resolucion,
                coordenadas_validas,
            )
            es_unico_y_claro = (
                len(lugares) == 1
                or (
                    len(lugares) > 1
                    and lugares[0].get("similitud", 0.0) >= 0.95
                    and (lugares[0].get("similitud", 0.0) - lugares[1].get("similitud", 0.0)) >= 0.08
                )
            )
            if es_unico_y_claro:
                lugar = lugares[0]
                if calle_1:
                    punto = self._ejecutar_herramienta(
                        "punto_sobre_calle_cerca_de",
                        {"calle": calle_1, "lat": lugar["lat"], "lon": lugar["lon"]},
                        pasos_resolucion,
                        coordenadas_validas,
                    )
                    if (
                        punto
                        and _en_posadas(punto.get("lat"), punto.get("lon"))
                        and float(punto.get("distancia_metros", 999999.0)) <= DISTANCIA_MAX_CORREDOR_METROS
                    ):
                        return self._construir_respuesta(
                            estado="resuelto",
                            lat=punto["lat"],
                            lon=punto["lon"],
                            osm_id=punto.get("osm_id"),
                            ubicacion_resuelta=f"{punto['nombre_oficial']} frente a {lugar['nombre_oficial']}",
                            tipo_ubicacion="corredor_hito",
                            confianza=CONFIANZA_PUNTO_SOBRE_CALLE_CERCA_DE_LUGAR,
                            metodo="nomenclador",
                            requiere_revision_humana=False,
                            pasos_resolucion=pasos_resolucion,
                        )
                elif _en_posadas(lugar.get("lat"), lugar.get("lon")):
                    return self._construir_respuesta(
                        estado="resuelto",
                        lat=lugar["lat"],
                        lon=lugar["lon"],
                        osm_id=lugar.get("osm_id"),
                        ubicacion_resuelta=lugar["nombre_oficial"],
                        tipo_ubicacion="punto_singular",
                        confianza=CONFIANZA_LUGAR_UNICO,
                        metodo="nomenclador",
                        requiere_revision_humana=False,
                        pasos_resolucion=pasos_resolucion,
                    )

        # --- PASO 2: Caso ambiguo -> Resolución asistida por Gemini con Function Calling ---
        if calle_1 or calle_2 or referencia_espacial or (texto_completo and texto_completo.strip()):
            res_gemini = self._resolver_con_gemini(
                calle_1=calle_1,
                calle_2=calle_2,
                referencia_espacial=referencia_espacial,
                texto_completo=texto_completo,
                pasos_resolucion=pasos_resolucion,
                coordenadas_validas=coordenadas_validas,
            )
            if res_gemini is not None:
                return res_gemini

        # --- PASO 3: Respaldo offline cuando Gemini no está disponible o falla ---
        if not calle_1 and not calle_2 and not referencia_espacial and texto_completo:
            res_desambiguado = self._intentar_desambiguar_texto_con_nomenclador(
                calle_1=calle_1,
                calle_2=calle_2,
                referencia_espacial=referencia_espacial,
                texto_completo=texto_completo,
                pasos_resolucion=pasos_resolucion,
                coordenadas_validas=coordenadas_validas,
            )
            if res_desambiguado is not None:
                return res_desambiguado

        return self._derivar_revision_humana(
            calle_1=calle_1,
            calle_2=calle_2,
            referencia_espacial=referencia_espacial,
            pasos_resolucion=pasos_resolucion,
            coordenadas_validas=coordenadas_validas,
            metodo="nomenclador",
        )

    def investigar_ubicacion(self, texto_ubicacion: str) -> Dict[str, Any]:
        """Compatibilidad con interfaz de consulta por texto libre."""
        return self.resolver_georreferenciacion(texto_completo=texto_ubicacion)


if __name__ == "__main__":
    inv = AgenteInvestigador()
    r1 = inv.resolver_georreferenciacion(
        calle_1="Av. Alicia Moreau de Justo",
        referencia_espacial="Country Los Naranjos",
        texto_completo="Choque frente al Country Los Naranjos sobre ex Ruta 213",
    )
    print("Caso Country Los Naranjos:", r1)
