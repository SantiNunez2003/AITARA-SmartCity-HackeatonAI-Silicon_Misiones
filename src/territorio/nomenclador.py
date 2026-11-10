"""Funciones de consulta offline sobre el nomenclador local de Posadas (OpenStreetMap).

Lee exclusivamente los archivos versionados en data/territorio/:
- calles.json
- intersecciones.json
- lugares.json
"""

from difflib import SequenceMatcher
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from src.territorio.descargar_osm import DATA_DIR, distancia_metros, normalizar_nombre, quitar_tildes

_CACHE_CALLES: Optional[List[Dict[str, Any]]] = None
_CACHE_INTERSECCIONES: Optional[List[Dict[str, Any]]] = None
_CACHE_INDICE_INTER: Optional[Dict[Tuple[str, str], Dict[str, Any]]] = None
_CACHE_LUGARES: Optional[List[Dict[str, Any]]] = None

STOPWORDS_LUGAR = {
    "de", "del", "la", "las", "el", "los", "en", "al", "a", "y", "e",
    "por", "frente", "cerca", "metros", "inmediaciones", "zona",
    "country", "barrio", "complejo", "predio", "edificio", "sede",
}

TOKENS_GENERICOS_LUGAR = {
    "rotonda", "plaza", "plazoleta", "parque", "colegio", "escuela",
    "instituto", "hospital", "centro", "clinica", "sanatorio", "puente",
    "club", "estacion", "terminal", "transferencia", "acceso", "avenida", "calle",
}


def _cargar_calles() -> List[Dict[str, Any]]:
    global _CACHE_CALLES
    if _CACHE_CALLES is None:
        ruta = DATA_DIR / "calles.json"
        _CACHE_CALLES = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else []
    return _CACHE_CALLES


def _cargar_intersecciones() -> List[Dict[str, Any]]:
    global _CACHE_INTERSECCIONES
    if _CACHE_INTERSECCIONES is None:
        ruta = DATA_DIR / "intersecciones.json"
        _CACHE_INTERSECCIONES = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else []
    return _CACHE_INTERSECCIONES


def _cargar_indice_intersecciones() -> Dict[Tuple[str, str], Dict[str, Any]]:
    global _CACHE_INDICE_INTER
    if _CACHE_INDICE_INTER is None:
        _CACHE_INDICE_INTER = {}
        for item in _cargar_intersecciones():
            par = (item["calle_1_norm"], item["calle_2_norm"])
            _CACHE_INDICE_INTER[par] = item
            _CACHE_INDICE_INTER[(par[1], par[0])] = item
    return _CACHE_INDICE_INTER


def _cargar_lugares() -> List[Dict[str, Any]]:
    global _CACHE_LUGARES
    if _CACHE_LUGARES is None:
        ruta = DATA_DIR / "lugares.json"
        _CACHE_LUGARES = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else []
    return _CACHE_LUGARES


def _es_via_secundaria(nombre_norm: str) -> bool:
    return nombre_norm.startswith(("colectora ", "bicisenda ", "senda ciclable ", "enlace ", "ingreso a "))


def _tokens_significativos(texto_norm: str, stopwords: Optional[set] = None) -> List[str]:
    sw = stopwords if stopwords is not None else {"de", "del", "la", "las", "el", "los", "y", "a", "al", "en"}
    return [t for t in texto_norm.split() if t and t not in sw]


def buscar_calle(nombre: str) -> List[Dict[str, Any]]:
    """Busca calles por nombre con tolerancia a tildes, prefijos y errores de escritura."""
    if not nombre or not nombre.strip():
        return []
    q_norm = normalizar_nombre(nombre)
    if not q_norm:
        return []

    if q_norm in ("213", "rp213", "rp 213", "ex 213"):
        q_norm = "alicia moreau de justo"

    q_tokens = _tokens_significativos(q_norm)
    calles = _cargar_calles()
    resultados: List[Tuple[float, Dict[str, Any]]] = []

    for c in calles:
        c_norm = c["nombre_normalizado"]
        aliases_norm = [normalizar_nombre(a) for a in c.get("aliases", []) if a]
        todas_formas = [c_norm] + [a for a in aliases_norm if a]

        mejor_score = 0.0
        penalizacion = 0.05 if _es_via_secundaria(c_norm) else 0.0

        for forma in todas_formas:
            if q_norm == forma:
                mejor_score = max(mejor_score, 1.0 - penalizacion)
                break

            f_tokens = _tokens_significativos(forma)
            if q_tokens and f_tokens and all(qt in f_tokens for qt in q_tokens):
                ratio_len = len(q_tokens) / max(len(f_tokens), 1)
                mejor_score = max(mejor_score, 0.92 + 0.05 * ratio_len - penalizacion)
                continue

            if len(q_norm) >= 4 and re.search(rf"\b{re.escape(q_norm)}\b", forma):
                mejor_score = max(mejor_score, 0.88 - penalizacion)
                continue

            sim = SequenceMatcher(None, q_norm, forma).ratio()
            if sim >= 0.78:
                mejor_score = max(mejor_score, sim * 0.90 - penalizacion)
            elif q_tokens and f_tokens:
                comunes = sum(
                    1 for qt in q_tokens
                    if any(SequenceMatcher(None, qt, ft).ratio() >= 0.84 for ft in f_tokens)
                )
                if comunes == len(q_tokens) and comunes > 0:
                    mejor_score = max(mejor_score, 0.86 - penalizacion)
                elif comunes > 0 and comunes >= len(f_tokens) and len(f_tokens) > 0:
                    mejor_score = max(mejor_score, 0.85 - penalizacion)

        if mejor_score >= 0.72:
            resultados.append((
                mejor_score,
                {
                    "osm_id": c["osm_id"],
                    "nombre_oficial": c["nombre_oficial"],
                    "nombre_normalizado": c_norm,
                    "aliases": c.get("aliases", []),
                    "lat": c["lat"],
                    "lon": c["lon"],
                    "nodos": c.get("nodos", []),
                    "similitud": round(mejor_score, 4),
                    "fuente": "openstreetmap",
                },
            ))

    resultados.sort(key=lambda x: (-x[0], len(x[1]["nombre_normalizado"]), x[1]["osm_id"]))
    return [r[1] for r in resultados[:10]]


def buscar_interseccion(calle_1: str, calle_2: str) -> Dict[str, Any]:
    """Busca las coordenadas del cruce entre dos calles de Posadas en OpenStreetMap."""
    if not calle_1 or not calle_2:
        return {
            "encontrada": False,
            "osm_id": None,
            "nombre_oficial": "",
            "lat": None,
            "lon": None,
            "fuente": "openstreetmap",
            "mensaje": "Se requieren dos calles para buscar una intersección.",
        }

    cand_1 = buscar_calle(calle_1)
    cand_2 = buscar_calle(calle_2)

    if not cand_1 or not cand_2:
        return {
            "encontrada": False,
            "osm_id": None,
            "nombre_oficial": "",
            "lat": None,
            "lon": None,
            "fuente": "openstreetmap",
            "mensaje": f"No se encontraron calles coincidentes para '{calle_1}' y '{calle_2}'.",
        }

    indice_inter = _cargar_indice_intersecciones()

    # 1. Buscar cruce directo en intersecciones precalculadas entre los mejores candidatos
    for c1 in cand_1[:4]:
        for c2 in cand_2[:4]:
            n1 = c1["nombre_normalizado"]
            n2 = c2["nombre_normalizado"]
            if n1 == n2:
                continue
            cruce = indice_inter.get((n1, n2))
            if cruce:
                return {
                    "encontrada": True,
                    "osm_id": cruce["osm_id"],
                    "nombre_oficial": cruce["nombre_oficial"],
                    "calle_1_oficial": cruce["calle_1_oficial"],
                    "calle_2_oficial": cruce["calle_2_oficial"],
                    "subtipo": cruce.get("subtipo", "nodo"),
                    "lat": cruce["lat"],
                    "lon": cruce["lon"],
                    "fuente": "openstreetmap",
                    "mensaje": f"Intersección encontrada: {cruce['nombre_oficial']}.",
                }

    # 2. Proximidad inmediata de nodos (<= 35 m) en caso de enlaces divididos o colectoras
    mejor_prox: Optional[Tuple[float, Dict[str, Any], Dict[str, Any], List[Any]]] = None
    for c1 in cand_1[:3]:
        for c2 in cand_2[:3]:
            if c1["nombre_normalizado"] == c2["nombre_normalizado"]:
                continue
            for n1 in c1.get("nodos", []):
                for n2 in c2.get("nodos", []):
                    if abs(n1[0] - n2[0]) > 0.0005 or abs(n1[1] - n2[1]) > 0.0005:
                        continue
                    d = distancia_metros(n1[0], n1[1], n2[0], n2[1])
                    if d <= 35.0 and (mejor_prox is None or d < mejor_prox[0]):
                        mejor_prox = (d, c1, c2, n1)

    if mejor_prox is not None:
        _, c1, c2, nodo = mejor_prox
        nombre_cruce = f"{c1['nombre_oficial']} y {c2['nombre_oficial']}"
        return {
            "encontrada": True,
            "osm_id": int(nodo[2]),
            "nombre_oficial": nombre_cruce,
            "calle_1_oficial": c1["nombre_oficial"],
            "calle_2_oficial": c2["nombre_oficial"],
            "subtipo": "proximidad_osm",
            "lat": float(nodo[0]),
            "lon": float(nodo[1]),
            "fuente": "openstreetmap",
            "mensaje": f"Intersección encontrada: {nombre_cruce}.",
        }

    return {
        "encontrada": False,
        "osm_id": None,
        "nombre_oficial": "",
        "lat": None,
        "lon": None,
        "fuente": "openstreetmap",
        "mensaje": f"Las calles '{cand_1[0]['nombre_oficial']}' y '{cand_2[0]['nombre_oficial']}' no se cruzan en el nomenclador OSM.",
    }


def _prioridad_tipo_lugar(tipo: str, texto_norm: str) -> float:
    bonus = 0.0
    if "puente" in texto_norm and "bridge" in tipo:
        bonus += 0.12
    if "rotonda" in texto_norm and "roundabout" in tipo:
        bonus += 0.12
    if ("hospital" in texto_norm or "salud" in texto_norm or "madariaga" in texto_norm) and (
        "hospital" in tipo or "clinic" in tipo or "healthcare" in tipo
    ):
        bonus += 0.10
    if ("colegio" in texto_norm or "escuela" in texto_norm or "san basilio" in texto_norm) and "school" in tipo:
        bonus += 0.10
    if ("campus" in texto_norm or "unam" in texto_norm or "universidad" in texto_norm) and (
        "university" in tipo or "college" in tipo
    ):
        bonus += 0.10
    if ("country" in texto_norm or "barrio" in texto_norm or "naranjos" in texto_norm) and (
        "residential" in tipo or "neighbourhood" in tipo or "suburb" in tipo
    ):
        bonus += 0.10
    if "autodromo" in texto_norm and ("stadium" in tipo or "track" in tipo or "sports_centre" in tipo or "leisure" in tipo):
        bonus += 0.10
    return bonus


def buscar_lugar(texto: str) -> List[Dict[str, Any]]:
    """Busca lugares de referencia en Posadas por nombre y devuelve coincidencias con coordenadas y tipo."""
    if not texto or not texto.strip():
        return []
    q_raw_norm = quitar_tildes(texto.lower().strip())
    q_raw_norm = re.sub(r"[.,;()\"'/-]+", " ", q_raw_norm)
    q_raw_norm = re.sub(r"\s+", " ", q_raw_norm).strip()
    q_norm = normalizar_nombre(texto)
    if not q_norm:
        return []

    q_tokens = _tokens_significativos(q_raw_norm, STOPWORDS_LUGAR)
    if not q_tokens:
        q_tokens = _tokens_significativos(q_norm)
    q_tokens_especificos = [t for t in q_tokens if t not in TOKENS_GENERICOS_LUGAR]

    lugares = _cargar_lugares()
    candidatos: List[Tuple[float, Dict[str, Any]]] = []

    for l in lugares:
        l_norm = l["nombre_normalizado"]
        l_ofi_norm = quitar_tildes(l["nombre_oficial"].lower().strip())
        aliases_norm = [normalizar_nombre(a) for a in l.get("aliases", []) if a]
        todas_formas = [l_norm, l_ofi_norm] + [a for a in aliases_norm if a]

        mejor_score = 0.0
        for forma in todas_formas:
            if q_norm == forma or q_raw_norm == forma:
                mejor_score = max(mejor_score, 1.0)
                break

            f_tokens = _tokens_significativos(forma, STOPWORDS_LUGAR)
            if not f_tokens:
                f_tokens = _tokens_significativos(forma)
            f_tokens_especificos = [t for t in f_tokens if t not in TOKENS_GENERICOS_LUGAR]

            if q_tokens and f_tokens:
                if q_tokens == f_tokens:
                    mejor_score = max(mejor_score, 0.96)
                    continue
                if all(qt in f_tokens for qt in q_tokens):
                    cobertura = len(q_tokens) / max(len(f_tokens), 1)
                    mejor_score = max(mejor_score, 0.85 + 0.10 * cobertura)
                    continue
                if (
                    f_tokens_especificos
                    and q_tokens_especificos
                    and all(ft in q_tokens_especificos for ft in f_tokens_especificos)
                ):
                    cobertura = len(f_tokens_especificos) / max(len(q_tokens_especificos), 1)
                    if len(f_tokens_especificos[0]) >= 5 or len(f_tokens_especificos) >= 2:
                        mejor_score = max(mejor_score, 0.82 + 0.10 * cobertura)
                        continue

            sim = SequenceMatcher(None, q_norm, forma).ratio()
            if sim >= 0.80:
                mejor_score = max(mejor_score, sim * 0.90)

        if mejor_score >= 0.75:
            score_final = mejor_score + _prioridad_tipo_lugar(l.get("tipo", ""), q_raw_norm)
            candidatos.append((
                score_final,
                {
                    "osm_id": l["osm_id"],
                    "nombre_oficial": l["nombre_oficial"],
                    "nombre_normalizado": l_norm,
                    "tipo": l.get("tipo", "lugar"),
                    "lat": l["lat"],
                    "lon": l["lon"],
                    "similitud": round(min(1.0, score_final), 4),
                    "fuente": "openstreetmap",
                },
            ))

    candidatos.sort(key=lambda x: (-x[0], len(x[1]["nombre_oficial"]), x[1]["osm_id"]))

    deduplicados: List[Dict[str, Any]] = []
    for _, item in candidatos:
        es_duplicado_cercano = False
        for existente in deduplicados:
            misma_raiz = (
                item["nombre_normalizado"] == existente["nombre_normalizado"]
                or item["nombre_normalizado"] in existente["nombre_normalizado"]
                or existente["nombre_normalizado"] in item["nombre_normalizado"]
            )
            if misma_raiz and distancia_metros(item["lat"], item["lon"], existente["lat"], existente["lon"]) < 250.0:
                es_duplicado_cercano = True
                break
        if not es_duplicado_cercano:
            deduplicados.append(item)
        if len(deduplicados) >= 10:
            break

    return deduplicados


def punto_sobre_calle_cerca_de(calle: str, lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Devuelve el nodo real de una calle en OSM más cercano a (lat, lon)."""
    calles = buscar_calle(calle)
    if not calles:
        return None

    norm_principal = calles[0]["nombre_normalizado"]
    candidatas = [
        c for c in calles
        if c["nombre_normalizado"] == norm_principal
        or norm_principal in c["nombre_normalizado"]
        or c["similitud"] >= 0.90
    ][:3]

    mejor_nodo: Optional[Tuple[float, Dict[str, Any], List[Any]]] = None
    for c in candidatas:
        for nodo in c.get("nodos", []):
            d = distancia_metros(lat, lon, float(nodo[0]), float(nodo[1]))
            if mejor_nodo is None or d < mejor_nodo[0]:
                mejor_nodo = (d, c, nodo)

    if mejor_nodo is None:
        c0 = calles[0]
        d0 = distancia_metros(lat, lon, c0["lat"], c0["lon"])
        return {
            "osm_id": c0["osm_id"],
            "calle_osm_id": c0["osm_id"],
            "nombre_oficial": c0["nombre_oficial"],
            "lat": c0["lat"],
            "lon": c0["lon"],
            "distancia_metros": round(d0, 2),
            "fuente": "openstreetmap",
        }

    dist, c_ganadora, nodo_ganador = mejor_nodo
    return {
        "osm_id": int(nodo_ganador[2]),
        "calle_osm_id": c_ganadora["osm_id"],
        "nombre_oficial": c_ganadora["nombre_oficial"],
        "lat": float(nodo_ganador[0]),
        "lon": float(nodo_ganador[1]),
        "distancia_metros": round(dist, 2),
        "fuente": "openstreetmap",
    }
