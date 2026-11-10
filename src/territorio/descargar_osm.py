"""Descarga única del nomenclador vial y lugares de referencia de Posadas desde OpenStreetMap (Overpass API).

Genera en data/territorio/:
- calles.json
- intersecciones.json
- lugares.json

Cada registro conserva su osm_id real y fuente="openstreetmap".
"""

import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
import urllib.parse
import urllib.request

LAT_MIN = -27.50
LAT_MAX = -27.33
LON_MIN = -56.05
LON_MAX = -55.85

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "territorio"


def quitar_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def normalizar_nombre(nombre: str) -> str:
    """Normaliza nombres de calles y lugares: minúsculas, sin tildes y sin prefijos viales."""
    if not nombre:
        return ""
    s = quitar_tildes(nombre.lower().strip())
    s = re.sub(r"[.,;()\"'/-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Soportar casos pegados como "calletucuman" o "avquaranta"
    s = re.sub(r"^(avenida|calle|pasaje|boulevard)(?=[a-z])", r"\1 ", s)
    prefijos = [
        "avenida ",
        "av ",
        "calle ",
        "pasaje ",
        "pje ",
        "boulevard ",
        "bv ",
        "ruta nacional ",
        "ruta provincial ",
        "ex ruta provincial ",
        "ex ruta ",
        "ruta ",
        "rn ",
        "rp ",
        "autovia ",
        "autopista ",
    ]
    cambio = True
    while cambio:
        cambio = False
        for pref in prefijos:
            if s.startswith(pref):
                s = s[len(pref):].strip()
                cambio = True
    return s


def distancia_metros(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def consultar_overpass(query: str) -> Dict[str, Any]:
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    ultimo_error = None
    for url in OVERPASS_ENDPOINTS:
        try:
            print(f"Consultando Overpass en {url} ...")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"User-Agent": "AITARA-Posadas-Nomenclador/1.0"},
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            print(f"Fallo en {url}: {exc}")
            ultimo_error = exc
    raise RuntimeError(f"No se pudo descargar desde Overpass: {ultimo_error}")


def construir_query_overpass() -> str:
    bbox = f"{LAT_MIN},{LON_MIN},{LAT_MAX},{LON_MAX}"
    return f"""
[out:json][timeout:90];
(
  way["highway"]["name"]({bbox});
  way["highway"]["ref"]({bbox});
  way["junction"="roundabout"]({bbox});
  nwr["name"]["amenity"]({bbox});
  nwr["name"]["leisure"]({bbox});
  nwr["name"]["landuse"]({bbox});
  nwr["name"]["place"]({bbox});
  nwr["name"]["tourism"]({bbox});
  nwr["name"]["shop"~"mall|supermarket|department_store"]({bbox});
  nwr["name"]["aeroway"]({bbox});
  nwr["name"]["bridge"]({bbox});
  nwr["name"]["man_made"="bridge"]({bbox});
  nwr["name"]["public_transport"]({bbox});
  nwr["name"]["healthcare"]({bbox});
  nwr["name"]["office"="government"]({bbox});
  nwr["name"]["historic"]({bbox});
);
out body center qt;
>;
out skel qt;
"""


def _es_en_paraguay(lat: float, lon: float, tags: Dict[str, str]) -> bool:
    """Descarta objetos ubicados en Encarnación (Paraguay) al noreste del río Paraná."""
    if tags.get("addr:country") == "PY" or tags.get("is_in:country_code") == "PY":
        return True
    # La costa de Posadas llega hasta lon ~ -55.878 al norte de -27.372; al este de -55.868 es Encarnación
    if lon > -55.868 and lat > -27.375:
        return True
    return False


def _determinar_tipo_lugar(tags: Dict[str, str]) -> str:
    for clave in (
        "amenity",
        "leisure",
        "place",
        "landuse",
        "aeroway",
        "tourism",
        "shop",
        "healthcare",
        "public_transport",
        "bridge",
        "man_made",
        "office",
        "historic",
        "junction",
        "highway",
    ):
        if clave in tags:
            return f"{clave}:{tags[clave]}"
    return "lugar"


def procesar_datos_osm(raw: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    elementos = raw.get("elements", [])

    nodos_coords: Dict[int, Tuple[float, float]] = {}
    for el in elementos:
        if el.get("type") == "node" and "lat" in el and "lon" in el:
            nodos_coords[int(el["id"])] = (round(float(el["lat"]), 6), round(float(el["lon"]), 6))

    calles_agrupadas: Dict[str, Dict[str, Any]] = {}
    nodo_a_calles: Dict[int, Set[str]] = defaultdict(set)
    rotondas_ways: List[Dict[str, Any]] = []
    lugares_dict: Dict[str, Dict[str, Any]] = {}

    for el in elementos:
        el_type = el.get("type")
        el_id = int(el["id"])
        tags = el.get("tags") or {}
        if not tags:
            continue

        if el_type == "way" and "highway" in tags:
            nd_ids = [int(n) for n in el.get("nodes", []) if int(n) in nodos_coords]
            if not nd_ids:
                continue

            lat_m, lon_m = nodos_coords[nd_ids[len(nd_ids) // 2]]
            if _es_en_paraguay(lat_m, lon_m, tags):
                continue

            if tags.get("junction") == "roundabout":
                rotondas_ways.append({
                    "osm_id": el_id,
                    "name": tags.get("name"),
                    "nodes": nd_ids,
                    "tags": tags,
                })

            nombre_oficial = (
                tags.get("name")
                or tags.get("official_name")
                or tags.get("alt_name")
                or tags.get("ref")
            )
            if nombre_oficial:
                norm = normalizar_nombre(nombre_oficial)
                # En OSM la traza sur de Av. Alicia Moreau de Justo figura como "Ruta Provincial 213" (ref RP213)
                if norm == "213" and ("213" in (tags.get("ref") or "") or "213" in nombre_oficial):
                    norm = "alicia moreau de justo"
                    nombre_oficial = "Avenida Alicia Moreau de Justo"

                if not norm:
                    continue

                aliases: Set[str] = set()
                for k in ("name", "alt_name", "old_name", "official_name", "short_name", "ref"):
                    val = tags.get(k)
                    if val:
                        for parte in str(val).split(";"):
                            parte_limpia = parte.strip()
                            if parte_limpia:
                                aliases.add(parte_limpia)

                if norm not in calles_agrupadas:
                    calles_agrupadas[norm] = {
                        "osm_id": el_id,
                        "nombre_oficial": nombre_oficial,
                        "nombre_normalizado": norm,
                        "aliases": set(aliases),
                        "nodos_map": {},
                        "fuente": "openstreetmap",
                    }
                else:
                    calles_agrupadas[norm]["aliases"].update(aliases)

                for nid in nd_ids:
                    lat, lon = nodos_coords[nid]
                    calles_agrupadas[norm]["nodos_map"][nid] = (lat, lon)
                    nodo_a_calles[nid].add(norm)

            if ("bridge" in tags or "puente" in (tags.get("name") or "").lower()) and tags.get("name"):
                lat_c, lon_c = nodos_coords[nd_ids[0]]
                clave_l = f"way:{el_id}"
                lugares_dict[clave_l] = {
                    "osm_id": el_id,
                    "osm_type": "way",
                    "nombre_oficial": tags["name"],
                    "nombre_normalizado": normalizar_nombre(tags["name"]),
                    "aliases": [tags[k] for k in ("alt_name", "short_name", "ref") if tags.get(k)],
                    "tipo": "bridge",
                    "lat": round(float(lat_c), 6),
                    "lon": round(float(lon_c), 6),
                    "fuente": "openstreetmap",
                }

        # Filtrar manzanas catastrales ("Manzana 1", etc.)
        if tags.get("place") == "city_block":
            continue

        nombre_lugar = tags.get("name") or tags.get("official_name") or tags.get("alt_name")
        es_hito = any(
            k in tags
            for k in (
                "amenity",
                "leisure",
                "landuse",
                "place",
                "tourism",
                "shop",
                "aeroway",
                "healthcare",
                "public_transport",
                "office",
                "historic",
            )
        ) or tags.get("man_made") == "bridge" or tags.get("junction") == "roundabout"

        if nombre_lugar and es_hito:
            lat_l = el.get("lat") if el_type == "node" else el.get("center", {}).get("lat")
            lon_l = el.get("lon") if el_type == "node" else el.get("center", {}).get("lon")
            if lat_l is None and el_type == "way":
                nds = [int(n) for n in el.get("nodes", []) if int(n) in nodos_coords]
                if nds:
                    lat_l = sum(nodos_coords[n][0] for n in nds) / len(nds)
                    lon_l = sum(nodos_coords[n][1] for n in nds) / len(nds)
            if lat_l is not None and lon_l is not None:
                lat_f, lon_f = round(float(lat_l), 6), round(float(lon_l), 6)
                if LAT_MIN <= lat_f <= LAT_MAX and LON_MIN <= lon_f <= LON_MAX and not _es_en_paraguay(lat_f, lon_f, tags):
                    clave_l = f"{el_type}:{el_id}"
                    aliases_l = []
                    for k in ("alt_name", "old_name", "short_name", "official_name"):
                        if tags.get(k):
                            aliases_l.append(tags[k])
                    lugares_dict[clave_l] = {
                        "osm_id": el_id,
                        "osm_type": el_type,
                        "nombre_oficial": nombre_lugar,
                        "nombre_normalizado": normalizar_nombre(nombre_lugar),
                        "aliases": aliases_l,
                        "tipo": _determinar_tipo_lugar(tags),
                        "lat": lat_f,
                        "lon": lon_f,
                        "fuente": "openstreetmap",
                    }

    # Consolidar lista de calles
    calles_lista: List[Dict[str, Any]] = []
    for norm, info in sorted(calles_agrupadas.items()):
        nodos_items = list(info["nodos_map"].items())
        if not nodos_items:
            continue
        avg_lat = sum(lat for _, (lat, _) in nodos_items) / len(nodos_items)
        avg_lon = sum(lon for _, (_, lon) in nodos_items) / len(nodos_items)
        _, (rep_lat, rep_lon) = min(
            nodos_items,
            key=lambda item: distancia_metros(avg_lat, avg_lon, item[1][0], item[1][1]),
        )
        nodos_serializados = [[lat, lon, nid] for nid, (lat, lon) in nodos_items]
        if len(nodos_serializados) > 250:
            importantes = [
                [lat, lon, nid]
                for nid, (lat, lon) in nodos_items
                if len(nodo_a_calles.get(nid, ())) > 1
            ]
            paso = max(1, len(nodos_serializados) // 180)
            muestra = nodos_serializados[::paso]
            vistos = {x[2] for x in importantes}
            for item in muestra:
                if item[2] not in vistos:
                    importantes.append(item)
                    vistos.add(item[2])
            nodos_serializados = importantes

        calles_lista.append({
            "osm_id": info["osm_id"],
            "nombre_oficial": info["nombre_oficial"],
            "nombre_normalizado": norm,
            "aliases": sorted(info["aliases"]),
            "lat": rep_lat,
            "lon": rep_lon,
            "nodos": nodos_serializados,
            "fuente": "openstreetmap",
        })

    # Construir intersecciones
    cruces_por_par: Dict[Tuple[str, str], List[Tuple[int, float, float, str]]] = defaultdict(list)

    # 1. Nodos compartidos directamente
    for nid, calles_en_nodo in nodo_a_calles.items():
        if len(calles_en_nodo) < 2:
            continue
        lat, lon = nodos_coords[nid]
        ordenadas = sorted(calles_en_nodo)
        for i in range(len(ordenadas)):
            for j in range(i + 1, len(ordenadas)):
                par = (ordenadas[i], ordenadas[j])
                cruces_por_par[par].append((nid, lat, lon, "nodo"))

    # 2. Calles que convergen en una rotonda (nodos de la rotonda o enlaces a <= 25 m del anillo)
    todos_nodos_con_calle = [
        (nid, nodos_coords[nid][0], nodos_coords[nid][1], calles_en_nodo)
        for nid, calles_en_nodo in nodo_a_calles.items()
    ]
    for rot in rotondas_ways:
        nodos_rot = [n for n in rot["nodes"] if n in nodos_coords]
        if not nodos_rot:
            continue
        avg_lat = sum(nodos_coords[n][0] for n in nodos_rot) / len(nodos_rot)
        avg_lon = sum(nodos_coords[n][1] for n in nodos_rot) / len(nodos_rot)
        nodo_rep = min(
            nodos_rot,
            key=lambda n: distancia_metros(avg_lat, avg_lon, nodos_coords[n][0], nodos_coords[n][1]),
        )
        rep_lat, rep_lon = nodos_coords[nodo_rep]

        calles_rot: Set[str] = set()
        for nid in nodos_rot:
            calles_rot.update(nodo_a_calles.get(nid, set()))

        # Incluir arterias cuyos nodos de enlace están a <= 25m del anillo de la rotonda
        for _, nlat, nlon, cset in todos_nodos_con_calle:
            if abs(nlat - rep_lat) < 0.0008 and abs(nlon - rep_lon) < 0.0008:
                if any(distancia_metros(nlat, nlon, nodos_coords[rn][0], nodos_coords[rn][1]) <= 25.0 for rn in nodos_rot):
                    calles_rot.update(cset)

        ordenadas = [c for c in sorted(calles_rot) if c != "la rotonda"]
        for i in range(len(ordenadas)):
            for j in range(i + 1, len(ordenadas)):
                par = (ordenadas[i], ordenadas[j])
                cruces_por_par[par].append((rot["osm_id"], rep_lat, rep_lon, "rotonda"))

        if ordenadas:
            nombres_ofi = [
                calles_agrupadas[c]["nombre_oficial"]
                for c in ordenadas
                if c in calles_agrupadas and not c.startswith("colectora")
            ][:3]
            if not nombres_ofi:
                nombres_ofi = [calles_agrupadas[c]["nombre_oficial"] for c in ordenadas[:2] if c in calles_agrupadas]
            nombre_rot = rot.get("name")
            if not nombre_rot or nombre_rot.lower().strip() == "la rotonda":
                nombre_rot = f"Rotonda {' y '.join(nombres_ofi)}"
            clave_r = f"roundabout:{rot['osm_id']}"
            lugares_dict[clave_r] = {
                "osm_id": rot["osm_id"],
                "osm_type": "way",
                "nombre_oficial": nombre_rot,
                "nombre_normalizado": normalizar_nombre(nombre_rot),
                "aliases": [f"rotonda {c}" for c in ordenadas],
                "tipo": "junction:roundabout",
                "lat": rep_lat,
                "lon": rep_lon,
                "fuente": "openstreetmap",
            }

    intersecciones_lista: List[Dict[str, Any]] = []
    for (c1, c2), candidatos in sorted(cruces_por_par.items()):
        avg_lat = sum(x[1] for x in candidatos) / len(candidatos)
        avg_lon = sum(x[2] for x in candidatos) / len(candidatos)
        osm_id, lat, lon, subtipo = min(
            candidatos,
            key=lambda x: distancia_metros(avg_lat, avg_lon, x[1], x[2]),
        )
        n1_ofi = calles_agrupadas[c1]["nombre_oficial"]
        n2_ofi = calles_agrupadas[c2]["nombre_oficial"]
        intersecciones_lista.append({
            "osm_id": osm_id,
            "calle_1_oficial": n1_ofi,
            "calle_2_oficial": n2_ofi,
            "calle_1_norm": c1,
            "calle_2_norm": c2,
            "nombre_oficial": f"{n1_ofi} y {n2_ofi}",
            "subtipo": subtipo,
            "lat": lat,
            "lon": lon,
            "fuente": "openstreetmap",
        })

    lugares_lista = sorted(lugares_dict.values(), key=lambda x: (x["nombre_normalizado"], x["osm_id"]))
    return calles_lista, intersecciones_lista, lugares_lista


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    query = construir_query_overpass()
    raw = consultar_overpass(query)
    calles, intersecciones, lugares = procesar_datos_osm(raw)

    (DATA_DIR / "calles.json").write_text(
        json.dumps(calles, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    (DATA_DIR / "intersecciones.json").write_text(
        json.dumps(intersecciones, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    (DATA_DIR / "lugares.json").write_text(
        json.dumps(lugares, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    print(
        f"Descarga OSM completada: {len(calles)} calles, "
        f"{len(intersecciones)} intersecciones, {len(lugares)} lugares guardados en {DATA_DIR}."
    )


if __name__ == "__main__":
    main()
