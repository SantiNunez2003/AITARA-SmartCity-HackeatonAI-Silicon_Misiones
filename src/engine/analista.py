"""Redacción de prioridades a partir de resultados analíticos trazables."""

import logging
import os
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from src.contracts import InformeOperativoAnalista, ParametrosEscenario
from src.engine.risk_model import ExplainableRiskEngine
from src.warehouse.db import get_db_connection

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
logger = logging.getLogger(__name__)
MODELO_GEMINI_PREDETERMINADO = "gemini-3.5-flash-lite"

# Se reconocen también números junto a letras y guiones bajos.
_NUMERO = re.compile(r"[-+]?\d+(?:[.,]\d+)?\s*%?")
_HORA = re.compile(r"\b\d{1,2}:\d{2}\b")
_LISTA = re.compile(r"^\s*(\d+)[.)][ \t]+")


def _numeros(texto):
    numeros = []
    for coincidencia in _NUMERO.finditer(texto):
        valor = coincidencia.group().strip()
        porcentaje = valor.endswith("%")
        try:
            numero = Decimal(valor.rstrip("% ").replace(",", "."))
        except InvalidOperation:
            continue
        numeros.append(numero / Decimal(100) if porcentaje else numero)
    return numeros


def _numeros_validos(respuesta, contexto):
    # Las horas solo se omiten si aparecen literalmente en el contexto.
    horas = set(_HORA.findall(contexto))
    lineas = []
    esperado = 1
    for linea in respuesta.splitlines():
        marcador = _LISTA.match(linea)
        if marcador and int(marcador.group(1)) == esperado:
            linea = linea[marcador.end():]
            esperado += 1
        else:
            esperado = 1
        lineas.append(linea)
    respuesta = "\n".join(lineas)
    respuesta = _HORA.sub(lambda m: "" if m.group() in horas else m.group(), respuesta)
    permitidos = set(_numeros(contexto))
    permitidos.update(n.quantize(Decimal("0.01")) for n in tuple(permitidos))
    return all(numero in permitidos for numero in _numeros(respuesta))


def _contexto(params, prioridades):
    lineas = [
        f"Escenario: franja {params.franja_horaria}; precipitación {params.precipitacion_mm_h:.2f} mm/h; "
        f"actividad escolar: {_si_no(params.actividad_escolar)}.",
    ]
    lineas.append(f"Nodos evaluados: {len(prioridades)}.")
    for prioridad in prioridades:
        lineas.append(
            f"Nodo: {prioridad.nodo.nombre}; nivel: {_nivel(prioridad)}; "
            f"riesgo estructural: {prioridad.riesgo_estructural:.2f}; "
            f"riesgo de escenario: {prioridad.riesgo_escenario:.2f}; "
            f"variación de escenario: {prioridad.variacion_escenario:.2f} %."
        )
        for aporte in prioridad.aportes:
            lineas.append(f"Aporte {aporte.nombre}: {aporte.aporte:.2f} ({aporte.descripcion}).")
        lineas.append(f"Incidentes de evidencia: {len(prioridad.evidencia)}.")
        if not prioridad.evidencia:
            lineas.append("Este nodo no tiene evidencia de incidentes.")
        for evidencia in prioridad.evidencia:
            enlace = evidencia.url or "enlace no disponible"
            lineas.append(f"Incidente {evidencia.id}: {evidencia.tipo}; fuente: {evidencia.fuente}; "
                          f"origen: {evidencia.origen}; enlace: {enlace}.")
    if not prioridades:
        lineas.append("No hay prioridades disponibles.")
    return "\n".join(lineas)


def _si_no(valor):
    return "sí" if valor else "no"


def _nivel(prioridad):
    return "crítico" if prioridad.nivel == "critico" else "no crítico"


def _normalizar(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", texto.casefold())
                   if not unicodedata.combining(c))


def _coincide_nodo(pregunta, nombre):
    pregunta = _normalizar(pregunta)
    nombre = _normalizar(nombre)
    if nombre in pregunta:
        return True
    palabras = re.findall(r"\w+", nombre)
    comunes = {"avenida", "calle", "cruce", "entre", "interseccion", "nodo", "ruta"}
    return any(len(palabra) >= 4 and palabra not in comunes
               and re.search(r"(?<!\w)" + re.escape(palabra) + r"(?!\w)", pregunta)
               for palabra in palabras)


def _resumen_prioridades(prioridades):
    lineas = []
    for prioridad in prioridades[:3]:
        mayor = max(prioridad.aportes, key=lambda a: a.aporte, default=None)
        factor = f"{mayor.nombre} ({mayor.aporte:.2f})" if mayor else "sin aportes disponibles"
        lineas.append(f"{prioridad.nodo.nombre}: {_nivel(prioridad)}; riesgo "
                      f"{prioridad.riesgo_escenario:.2f}; mayor aporte: {factor}; "
                      f"incidentes: {len(prioridad.evidencia)}.")
    return "\n".join(lineas) if lineas else "No hay prioridades disponibles."


def _respaldo(pregunta, params, prioridades):
    normalizada = _normalizar(pregunta)
    if re.search(r"\b(rutas?|desvios?|alternativ[ao]s?|recorridos?)\b", normalizada):
        return ("Las rutas alternativas no están en el contexto; sí hay prioridades de riesgo "
                "y evidencia de incidentes.\n" + _resumen_prioridades(prioridades)
                + f"\nNodos evaluados: {len(prioridades)}.")
    seleccion = next((p for p in prioridades if _coincide_nodo(pregunta, p.nodo.nombre)), None)
    if seleccion:
        return _contexto(params, [seleccion])
    return _resumen_prioridades(prioridades) + f"\nNodos evaluados: {len(prioridades)}."


class AgenteAnalista:
    def __init__(self, db=None):
        self.db = db or get_db_connection()
        self.risk_engine = ExplainableRiskEngine(self.db)
        self._genai_client = None

    def _get_genai_client(self):
        clave = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not clave:
            return None
        if self._genai_client is None:
            try:
                from google import genai
                self._genai_client = genai.Client(api_key=clave)
            except Exception:
                logger.exception("No se pudo inicializar Gemini; se usará el respaldo")
        return self._genai_client

    def generar_informe_turno(self, params: ParametrosEscenario) -> InformeOperativoAnalista:
        nodos, prioridades = self.risk_engine.evaluate_all_nodes(params)
        return InformeOperativoAnalista(
            fecha_emision=datetime.now(),
            turno=f"Turno ({params.franja_horaria} hs)",
            alerta_meteorologica=f"Precipitación del escenario: {params.precipitacion_mm_h:.2f} mm/h",
            nodos_criticos=[p.nodo for p in prioridades if p.nivel == "critico"],
            prioridades=prioridades,
            recomendacion_estrategica=_resumen_prioridades(prioridades),
        )

    def responder_consulta_operador(self, pregunta: str, params: ParametrosEscenario) -> str:
        _, prioridades = self.risk_engine.evaluate_all_nodes(params)
        contexto = _contexto(params, prioridades)
        respaldo = _respaldo(pregunta, params, prioridades)
        cliente = self._get_genai_client()
        modelo = os.getenv("GEMINI_MODEL") or MODELO_GEMINI_PREDETERMINADO
        if cliente is None:
            return respaldo
        prompt = (
            "Sos un analista que explica prioridades para apoyar decisiones humanas. "
            "Usá solamente los datos del contexto, citá los incidentes y sus enlaces, "
            "indicá si un nodo no tiene evidencia y si el dato solicitado no está disponible. "
            "No des órdenes ni cantidades de recursos. No inventes valores ni causas.\n\n"
            f"Contexto:\n{contexto}\n\nPregunta: {pregunta}"
        )
        try:
            resultado = cliente.interactions.create(model=modelo, input=prompt, store=False)
            respuesta = getattr(resultado, "output_text", "") or ""
            if respuesta.strip() and _numeros_validos(respuesta, contexto):
                return respuesta.strip()
            logger.warning("Respuesta de Gemini vacía o con números ajenos al contexto; se usará el respaldo")
        except Exception:
            logger.exception("Falló la consulta a Gemini; se usará el respaldo")
        return respaldo
