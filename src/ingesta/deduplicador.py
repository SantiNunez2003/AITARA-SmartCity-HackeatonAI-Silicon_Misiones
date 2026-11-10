"""Deduplicación de incidentes reportados por más de un medio.

Dos notas de medios distintos describen el mismo hecho cuando coinciden en
lugar, momento y tipo. En ese caso no se crea un incidente nuevo: la nota se
registra como fuente adicional del incidente existente.

Reglas declaradas:
- Lugar: a menos de DISTANCIA_DUPLICADO_METROS. Si alguna ubicación quedó
  indeterminada (coordenadas por defecto), se exige la misma calle principal.
- Momento: fechas a menos de VENTANA_DUPLICADO_HORAS. Se usa la fecha del
  evento y, si falta, la de publicación.
- Tipo: el mismo, o ambos siniestros (choque, vuelco, atropello), porque los
  medios suelen nombrar distinto el mismo hecho.
"""

import unicodedata
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Iterable, Optional

from src.engine.risk_model import distancia_metros

DISTANCIA_DUPLICADO_METROS = 300
VENTANA_DUPLICADO_HORAS = 48
TIPOS_SINIESTRO = {"choque", "vuelco", "atropello"}
# Los incidentes reales guardados están en hora local de Posadas.
ZONA_POSADAS = timezone(timedelta(hours=-3))


def parsear_fecha(valor: Any) -> Optional[datetime]:
    """Convierte ISO 8601, RFC 2822 (RSS) o datetime a hora local de Posadas sin zona."""
    if valor is None or valor == "":
        return None
    fecha = None
    if isinstance(valor, datetime):
        fecha = valor
    else:
        texto = str(valor).strip()
        try:
            fecha = datetime.fromisoformat(texto.replace("Z", "+00:00"))
        except ValueError:
            try:
                fecha = parsedate_to_datetime(texto)
            except (TypeError, ValueError):
                return None
    if fecha.tzinfo is not None:
        fecha = fecha.astimezone(ZONA_POSADAS).replace(tzinfo=None)
    return fecha


def _normalizar(texto: Optional[str]) -> str:
    if not texto:
        return ""
    texto = "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                    if unicodedata.category(c) != "Mn")
    for prefijo in ("avenida ", "av. ", "av ", "calle "):
        if texto.startswith(prefijo):
            texto = texto[len(prefijo):]
    return texto.strip()


def _momento(incidente: Dict[str, Any]) -> Optional[datetime]:
    return parsear_fecha(incidente.get("fecha_evento")) or parsear_fecha(incidente.get("fecha_publicacion"))


def _tipos_compatibles(a: Optional[str], b: Optional[str]) -> bool:
    return a == b or (a in TIPOS_SINIESTRO and b in TIPOS_SINIESTRO)


def _mismo_lugar(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    indeterminado = "indeterminado" in (a.get("tipo_ubicacion"), b.get("tipo_ubicacion"))
    if indeterminado:
        calle = _normalizar(a.get("calle_1"))
        return bool(calle) and calle == _normalizar(b.get("calle_1"))
    try:
        distancia = distancia_metros(float(a["lat"]), float(a["lon"]), float(b["lat"]), float(b["lon"]))
    except (KeyError, TypeError, ValueError):
        return False
    return distancia <= DISTANCIA_DUPLICADO_METROS


def es_mismo_hecho(nuevo: Dict[str, Any], existente: Dict[str, Any]) -> bool:
    if existente.get("origen", "real") != "real":
        return False
    if not _tipos_compatibles(nuevo.get("tipo_incidente"), existente.get("tipo_incidente")):
        return False
    t_nuevo, t_existente = _momento(nuevo), _momento(existente)
    if t_nuevo is None or t_existente is None:
        return False
    if abs(t_nuevo - t_existente) > timedelta(hours=VENTANA_DUPLICADO_HORAS):
        return False
    return _mismo_lugar(nuevo, existente)


def buscar_duplicado(nuevo: Dict[str, Any], existentes: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Devuelve el incidente existente que describe el mismo hecho, o None."""
    return next((e for e in existentes if es_mismo_hecho(nuevo, e)), None)
