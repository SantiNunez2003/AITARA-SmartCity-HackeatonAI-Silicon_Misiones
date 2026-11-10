"""AITARA — Recolector de Noticias Viales de Medios de Posadas.

Estrategias:
1. REST API de WordPress (/wp-json/wp/v2/posts) para portales compatibles.
2. Feeds RSS nativos parseados con xml.etree.ElementTree (sin dependencias pesadas).
3. Extracción web directa para notas enviadas por URL.
4. Pre-filtro léxico para descartar noticias sin impacto vial sin gastar tokens.
"""

import concurrent.futures
import hashlib
import json
import logging
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Pre-filtro léxico estricto sobre movilidad/siniestralidad
PATRON_VIAL = re.compile(
    r"(choque|colisi[oó]n|vuelco|atropell[oó]|despiste|siniestro|motociclist[ao]|"
    r"\bmoto\b|colectivo|tr[aá]nsito|sem[aá]foro|corte vial|anegamiento|inundaci[oó]n|"
    r"asfalto|calzada|traves[ií]a urbana|ruta 12|ruta 105|ruta 213|avenida)",
    re.IGNORECASE
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AITARA-Traffic-Monitor/2.1 (Posadas Misiones)"
}


def _limpiar_html(html: str) -> str:
    """Elimina tags HTML y entidades básicas."""
    if not html:
        return ""
    texto = re.sub(r"<[^>]+>", " ", html)
    texto = re.sub(r"&[a-zA-Z]+;", " ", texto)
    return " ".join(texto.split())


def _id_url(url: str) -> str:
    """Genera un hash determinístico a partir de la URL limpia."""
    url_limpia = url.split("?")[0].split("#")[0].strip()
    return f"inc-web-{hashlib.sha1(url_limpia.encode('utf-8')).hexdigest()[:10]}"


def es_noticia_vial(titulo: str, texto: str = "") -> bool:
    """Aplica pre-filtro para comprobar si el contenido trata sobre incidentes viales."""
    contenido = f"{titulo} {texto}"
    return bool(PATRON_VIAL.search(contenido))


def obtener_noticias_wordpress(base_url: str, nombre_fuente: str, termino: str = "accidente Posadas", limite: int = 5) -> List[Dict[str, Any]]:
    """Consulta el endpoint REST público de WordPress."""
    query = urllib.parse.urlencode({"search": termino, "per_page": limite, "_fields": "id,date,link,title,excerpt,content"})
    url = f"{base_url.rstrip('/')}/wp-json/wp/v2/posts?{query}"
    req = urllib.request.Request(url, headers=HEADERS)
    articulos = []
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                for post in data:
                    link = post.get("link", "")
                    titulo = _limpiar_html(post.get("title", {}).get("rendered", ""))
                    contenido = _limpiar_html(post.get("content", {}).get("rendered", "") or post.get("excerpt", {}).get("rendered", ""))
                    fecha = post.get("date") or datetime.now(timezone.utc).isoformat()
                    if es_noticia_vial(titulo, contenido):
                        articulos.append({
                            "id": _id_url(link),
                            "fuente": nombre_fuente,
                            "url": link,
                            "titulo": titulo,
                            "texto": contenido,
                            "fecha_publicacion": fecha
                        })
    except Exception as e:
        logger.warning("Fallo al consultar WordPress API en %s: %s", base_url, e)
    return articulos


def obtener_noticias_rss(url_feed: str, nombre_fuente: str, limite: int = 6) -> List[Dict[str, Any]]:
    """Descarga y parsea feeds RSS utilizando la librería estándar de Python."""
    req = urllib.request.Request(url_feed, headers=HEADERS)
    articulos = []
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                arbol = ET.fromstring(resp.read())
                items = arbol.findall(".//item")
                for item in items[:limite]:
                    titulo_elem = item.find("title")
                    link_elem = item.find("link")
                    desc_elem = item.find("description")
                    pub_date_elem = item.find("pubDate")

                    titulo = _limpiar_html(titulo_elem.text if titulo_elem is not None else "")
                    link = (link_elem.text if link_elem is not None else "").strip()
                    desc = _limpiar_html(desc_elem.text if desc_elem is not None else "")
                    pub_date = pub_date_elem.text if pub_date_elem is not None else datetime.now(timezone.utc).isoformat()

                    if link and es_noticia_vial(titulo, desc):
                        articulos.append({
                            "id": _id_url(link),
                            "fuente": nombre_fuente,
                            "url": link,
                            "titulo": titulo,
                            "texto": desc,
                            "fecha_publicacion": pub_date
                        })
    except Exception as e:
        logger.warning("Fallo al consultar feed RSS en %s: %s", url_feed, e)
    return articulos


def extraer_articulo_por_url(url: str) -> Optional[Dict[str, Any]]:
    """Descarga directamente una nota por URL y extrae título y cuerpo."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                html = resp.read().decode("utf-8", errors="ignore")
                # Extracción simple de título
                titulo_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
                titulo = _limpiar_html(titulo_match.group(1)) if titulo_match else "Noticia sin título"
                # Limpiar scripts y estilos
                sin_script = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.IGNORECASE | re.DOTALL)
                # Extraer párrafos
                parrafos = re.findall(r"<p[^>]*>(.*?)</p>", sin_script, re.IGNORECASE | re.DOTALL)
                cuerpo = " ".join(_limpiar_html(p) for p in parrafos if len(_limpiar_html(p)) > 30)

                # Identificar medio
                fuente = "web_local"
                if "misionesonline.net" in url:
                    fuente = "misiones_online"
                elif "primeraedicion.com.ar" in url:
                    fuente = "primera_edicion"
                elif "elterritorio.com.ar" in url:
                    fuente = "el_territorio"
                elif "canal12misiones.com" in url:
                    fuente = "canal_12"

                return {
                    "id": _id_url(url),
                    "fuente": fuente,
                    "url": url,
                    "titulo": titulo,
                    "texto": cuerpo or titulo,
                    "fecha_publicacion": datetime.now(timezone.utc).isoformat()
                }
    except Exception as e:
        logger.error("Error al extraer artículo de la URL %s: %s", url, e)
    return None


def recolectar_noticias_recientes(limite: int = 10) -> List[Dict[str, Any]]:
    """Consulta concurrentemente múltiples fuentes locales de Posadas y devuelve noticias viales candidatas."""
    candidatas: Dict[str, Dict[str, Any]] = {}

    tareas = [
        lambda: obtener_noticias_wordpress("https://misionesonline.net", "misiones_online", "accidente Posadas", limite=5),
        lambda: obtener_noticias_wordpress("https://canal12misiones.com", "canal_12", "accidente", limite=4),
        lambda: obtener_noticias_rss("https://www.elterritorio.com.ar/rss", "el_territorio", limite=5),
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futuros = [executor.submit(fn) for fn in tareas]
        for f in concurrent.futures.as_completed(futuros, timeout=8):
            try:
                for art in f.result():
                    if art.get("url"):
                        candidatas[art["url"]] = art
            except Exception as e:
                logger.warning("Fallo en tarea concurrente de recolección: %s", e)

    return list(candidatas.values())[:limite]
