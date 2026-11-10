"""Contratos de datos tipados (Pydantic) de AITARA.

Garantiza desacoplamiento limpio entre Ingesta (Ana), Almacén/Modelos (Joaquín/Core)
y la interfaz y el Analista.
"""
from datetime import datetime
from typing import List, Optional, Literal
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
    referencia_espacial: Optional[str] = None
    tipo_ubicacion: Literal["interseccion", "corredor_hito", "punto_singular", "indeterminado"] = "interseccion"
    ubicacion_texto: str
    lat: float
    lon: float
    confianza: float = Field(ge=0.0, le=1.0)
    estado_verificacion: str = "curado"  # 'curado', 'investigado', 'pendiente'
    resumen: str
    origen: Literal["real", "simulado"] = "real"


class ParametrosEscenario(BaseModel):
    """Parámetros operacionales definidos por el usuario."""
    dia_semana: int = 1  # 0=Lunes ... 4=Viernes
    franja_horaria: str = "07:00"  # '07:00', '12:00', '18:00'
    precipitacion_mm_h: float = 0.0  # Dato ingresado por el usuario
    actividad_escolar: bool = True


class EvaluacionNodo(BaseModel):
    """Salida del motor de riesgo y modelos analíticos de Joaquín."""
    nodo_id: str
    nombre: str
    lat: float
    lon: float
    riesgo_estructural: float  # Base histórica (0.0 a 1.0)
    variacion_escenario: float  # Variación porcentual respecto del riesgo habitual.
    riesgo_final: float  # Ponderación combinada
    es_critico: bool
    factores: List[str]


class AporteFactor(BaseModel):
    nombre: str
    aporte: float
    descripcion: str


class Evidencia(BaseModel):
    id: str
    fecha: datetime
    tipo: str
    fuente: str
    url: Optional[str] = None
    origen: Literal["real", "simulado"]


class Prioridad(BaseModel):
    nodo: EvaluacionNodo
    nivel: Literal["critico", "no_critico"]
    riesgo_estructural: float
    variacion_escenario: float
    riesgo_escenario: float
    aportes: List[AporteFactor]
    evidencia: List[Evidencia]
    total_evidencia: int = 0
    evidencia_real: int = 0
    evidencia_simulada: int = 0


class InformeOperativoAnalista(BaseModel):
    """Informe de turno generado por el Agente Analista (solo lectura a DuckDB)."""
    fecha_emision: datetime
    turno: str
    alerta_meteorologica: str
    nodos_criticos: List[EvaluacionNodo]
    prioridades: List[Prioridad]
    recomendacion_estrategica: str
