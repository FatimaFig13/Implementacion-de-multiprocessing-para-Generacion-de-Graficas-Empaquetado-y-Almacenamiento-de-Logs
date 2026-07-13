from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NivelLog(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class OrigenEvento(BaseModel):
    modulo: str                      
    proceso_id: str                  
    proyecto: str = "STORI"


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class LogGeneracionExitosa(BaseModel):
    timestamp: datetime = Field(default_factory=_ahora_utc)
    nivel: NivelLog = NivelLog.INFO
    origen: OrigenEvento
    nombre_tarea: str
    tipo_grafico: Optional[str] = None
    n_filas: Optional[int] = None
    columnas: list[str] = Field(default_factory=list)
    archivos: dict[str, str] = Field(default_factory=dict)
    duracion_ms: float


class LogError(BaseModel):
    timestamp: datetime = Field(default_factory=_ahora_utc)
    nivel: NivelLog = NivelLog.ERROR
    origen: OrigenEvento
    nombre_tarea: str
    tipo_excepcion: Optional[str] = None
    mensaje_error: str
    duracion_ms: Optional[float] = None


class LogWarning(BaseModel):
    timestamp: datetime = Field(default_factory=_ahora_utc)
    nivel: NivelLog = NivelLog.WARNING
    origen: OrigenEvento
    nombre_tarea: Optional[str] = None
    mensaje: str
    contexto: dict = Field(default_factory=dict)


class ResumenEjecucion(BaseModel):
    run_id: str
    timestamp_inicio: datetime
    timestamp_fin: datetime
    n_procesos: int
    total_tareas: int
    exitosas: int
    fallidas: int
    duracion_total_seg: float