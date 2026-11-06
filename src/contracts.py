"""Contratos de datos tipados (Pydantic) de AITARA.

Garantiza desacoplamiento limpio entre Ingesta (Ana), Almacén/Modelos (Joaquín/Core)
y la Interfaz/Agente de Despacho (Persona 2).
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class IncidenteSilver(BaseModel):
    """Contrato del incidente estructurado tras la extracción del Lector/Investigador."""
    id: str
    fuente: str  # 'primera_edicion', 'el_territorio', 'misiones_online', 'parte_policial'
    titulo: str
    url: Optional[str] = None
    fecha_publicacion: datetime
    fecha_evento: Optional[datetime] = None
    tipo_incidente: str  # 'choque', 'vuelco', 'atropello', 'corte_vial', 'anegamiento', 'semaforo_apagado'
    severidad: int = Field(ge=0, le=3)  # 0=sin daños, 1=material, 2=heridos, 3=fatal
    vehiculos: List[str] = Field(default_factory=list)
    calle_1: Optional[str] = None
    calle_2: Optional[str] = None
    ubicacion_texto: str
    lat: float
    lon: float
    confianza: float = Field(ge=0.0, le=1.0)
    estado_verificacion: str = "curado"  # 'curado', 'investigado', 'pendiente'
    resumen: str


class ParametrosEscenario(BaseModel):
    """Parámetros operacionales definidos en la interfaz por el despachador."""
    dia_semana: int = 1  # 0=Lunes ... 4=Viernes
    franja_horaria: str = "07:00"  # '07:00', '12:00', '18:00'
    precipitacion_mm_h: float = 0.0  # Dato OPAD
    actividad_escolar: bool = True
    dotacion_patrullas: int = 4  # Capacidad de móviles disponibles


class EvaluacionNodo(BaseModel):
    """Salida del motor de riesgo y modelos analíticos de Joaquín."""
    nodo_id: str
    nombre: str
    lat: float
    lon: float
    riesgo_estructural: float  # Base histórica (0.0 a 1.0)
    variacion_escenario: float  # Cociente vs habitual (ej. 1.52 = +52%)
    riesgo_final: float  # Ponderación combinada
    es_critico: bool
    factores: List[str]  # ['lluvia_opad', 'ingreso_escolar', 'motos_recurrentes']
    desvio_sugerido: Optional[str] = None


class OrdenDespacho(BaseModel):
    """Instrucción prescriptiva para una patrulla en calle."""
    movil_id: str
    nodo_objetivo: str
    hora_presentacion: str
    instruccion_tactica: str
    desvio_transporte: Optional[str] = None


class InformeOperativoAnalista(BaseModel):
    """Informe de turno generado por el Agente Analista (solo lectura a DuckDB)."""
    fecha_emision: datetime
    turno: str
    alerta_meteorologica: str
    nodos_criticos: List[EvaluacionNodo]
    ordenes_despacho: List[OrdenDespacho]
    recomendacion_estrategica: str
