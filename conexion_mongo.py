from __future__ import annotations

import os
from typing import Optional

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, PyMongoError

from esquemas_log import LogError, LogGeneracionExitosa, LogWarning, ResumenEjecucion

# Nombres de las colecciones (unica fuente de verdad de nombres)
COLECCION_GENERACION_EXITOSA = "logs_generacion_exitosa"
COLECCION_ERRORES = "logs_errores"
COLECCION_WARNINGS = "logs_warnings"
COLECCION_RESUMEN_EJECUCIONES = "resumen_ejecuciones"

URI_POR_DEFECTO = "mongodb://stori_admin:changeme_dev@127.0.0.1:27017/?authSource=admin&authMechanism=SCRAM-SHA-1"

class ConexionMongo:

    def __init__(
        self,
        uri: Optional[str] = None,
        nombre_bd: str = "stori_logs",
        timeout_ms: int = 5000,
    ):
        self.uri = uri or os.environ.get("MONGO_URI", URI_POR_DEFECTO)
        self.nombre_bd = nombre_bd
        self._cliente: MongoClient = MongoClient(
            self.uri, serverSelectionTimeoutMS=timeout_ms
        )
        self._bd: Database = self._cliente[self.nombre_bd]

    @property
    def bd(self) -> Database:
        return self._bd

    def coleccion(self, nombre: str) -> Collection:
        return self._bd[nombre]

    def verificar_conexion(self) -> bool:
        try:
            self._cliente.admin.command("ping")
            return True
        except (ConnectionFailure, PyMongoError) as e:
            print(f"\n--- ERROR: {e} ---\n")  
            return False

    def cerrar(self) -> None:
        self._cliente.close()

    def __enter__(self) -> "ConexionMongo":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cerrar()


class RegistradorEventos:
 
    def __init__(self, conexion: ConexionMongo):
        self.conexion = conexion

    def registrar_generacion_exitosa(self, **kwargs) -> str:
        log = LogGeneracionExitosa(**kwargs)
        coleccion = self.conexion.coleccion(COLECCION_GENERACION_EXITOSA)
        resultado = coleccion.insert_one(log.model_dump())
        return str(resultado.inserted_id)

    def registrar_error(self, **kwargs) -> str:
        log = LogError(**kwargs)
        coleccion = self.conexion.coleccion(COLECCION_ERRORES)
        resultado = coleccion.insert_one(log.model_dump())
        return str(resultado.inserted_id)

    def registrar_warning(self, **kwargs) -> str:
        log = LogWarning(**kwargs)
        coleccion = self.conexion.coleccion(COLECCION_WARNINGS)
        resultado = coleccion.insert_one(log.model_dump())
        return str(resultado.inserted_id)

    def registrar_resumen_ejecucion(self, **kwargs) -> str:
        resumen = ResumenEjecucion(**kwargs)
        coleccion = self.conexion.coleccion(COLECCION_RESUMEN_EJECUCIONES)
        resultado = coleccion.insert_one(resumen.model_dump())
        return str(resultado.inserted_id)