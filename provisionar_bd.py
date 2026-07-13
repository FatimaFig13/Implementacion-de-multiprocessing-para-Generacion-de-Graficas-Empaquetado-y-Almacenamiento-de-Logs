from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()


from pymongo import ASCENDING
from pymongo.errors import OperationFailure

from conexion_mongo import (
    COLECCION_ERRORES,
    COLECCION_GENERACION_EXITOSA,
    COLECCION_RESUMEN_EJECUCIONES,
    COLECCION_WARNINGS,
    ConexionMongo,
)

DIAS_RETENCION_LOGS = 90
SEGUNDOS_RETENCION_LOGS = DIAS_RETENCION_LOGS * 24 * 60 * 60

# Validadores $jsonSchema (deben reflejar los esquemas Pydantic de esquemas_log.py)

_ORIGEN_SCHEMA = {
    "bsonType": "object",
    "required": ["modulo", "proceso_id", "proyecto"],
    "properties": {
        "modulo": {"bsonType": "string"},
        "proceso_id": {"bsonType": "string"},
        "proyecto": {"bsonType": "string"},
    },
}

VALIDADOR_GENERACION_EXITOSA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["timestamp", "nivel", "origen", "nombre_tarea", "duracion_ms"],
        "properties": {
            "timestamp": {"bsonType": "date"},
            "nivel": {"enum": ["INFO", "WARNING", "ERROR"]},
            "origen": _ORIGEN_SCHEMA,
            "nombre_tarea": {"bsonType": "string"},
            "duracion_ms": {"bsonType": ["double", "int", "long"]},
        },
    }
}

VALIDADOR_ERRORES = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["timestamp", "nivel", "origen", "nombre_tarea", "mensaje_error"],
        "properties": {
            "timestamp": {"bsonType": "date"},
            "nivel": {"enum": ["INFO", "WARNING", "ERROR"]},
            "origen": _ORIGEN_SCHEMA,
            "nombre_tarea": {"bsonType": "string"},
            "mensaje_error": {"bsonType": "string"},
        },
    }
}

VALIDADOR_WARNINGS = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["timestamp", "nivel", "origen", "mensaje"],
        "properties": {
            "timestamp": {"bsonType": "date"},
            "nivel": {"enum": ["INFO", "WARNING", "ERROR"]},
            "origen": _ORIGEN_SCHEMA,
            "mensaje": {"bsonType": "string"},
        },
    }
}

VALIDADOR_RESUMEN_EJECUCIONES = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "run_id", "timestamp_inicio", "timestamp_fin",
            "n_procesos", "total_tareas", "exitosas", "fallidas",
        ],
        "properties": {
            "run_id": {"bsonType": "string"},
            "timestamp_inicio": {"bsonType": "date"},
            "timestamp_fin": {"bsonType": "date"},
            "n_procesos": {"bsonType": "int"},
            "total_tareas": {"bsonType": "int"},
            "exitosas": {"bsonType": "int"},
            "fallidas": {"bsonType": "int"},
        },
    }
}


def _crear_coleccion_con_validador(bd, nombre: str, validador: dict) -> None:
    if nombre in bd.list_collection_names():
        print(f"  - '{nombre}' ya existe, se omite creacion.")
        return
    bd.create_collection(nombre, validator=validador, validationLevel="moderate")
    print(f"  - '{nombre}' creada con validacion $jsonSchema.")


def _asegurar_indice_ttl(bd, nombre: str, campo: str = "timestamp") -> None:
    coleccion = bd[nombre]
    indices_existentes = coleccion.index_information()
    for info in indices_existentes.values():
        if info.get("key") == [(campo, 1)] and "expireAfterSeconds" in info:
            print(f"  - Indice TTL sobre '{nombre}.{campo}' ya existe, se omite.")
            return
    coleccion.create_index(
        [(campo, ASCENDING)], expireAfterSeconds=SEGUNDOS_RETENCION_LOGS
    )
    print(f"  - Indice TTL creado en '{nombre}.{campo}' ({DIAS_RETENCION_LOGS} dias).")


def provisionar() -> None:
    con = ConexionMongo()
    if not con.verificar_conexion():
        raise SystemExit(
            "No se pudo conectar a MongoDB. Verifica que el contenedor este "
            "levantado (`docker compose up -d`) y que MONGO_URI sea correcto."
        )

    bd = con.bd
    print(f"Conectado a la base de datos '{bd.name}'.\n")

    print("Creando colecciones de logs (con validacion $jsonSchema)...")
    _crear_coleccion_con_validador(bd, COLECCION_GENERACION_EXITOSA, VALIDADOR_GENERACION_EXITOSA)
    _crear_coleccion_con_validador(bd, COLECCION_ERRORES, VALIDADOR_ERRORES)
    _crear_coleccion_con_validador(bd, COLECCION_WARNINGS, VALIDADOR_WARNINGS)

    print("\nCreando coleccion de resumen de ejecuciones...")
    _crear_coleccion_con_validador(bd, COLECCION_RESUMEN_EJECUCIONES, VALIDADOR_RESUMEN_EJECUCIONES)

    print("\nCreando indices TTL (retencion de logs)...")
    _asegurar_indice_ttl(bd, COLECCION_GENERACION_EXITOSA)
    _asegurar_indice_ttl(bd, COLECCION_ERRORES)
    _asegurar_indice_ttl(bd, COLECCION_WARNINGS)

    print("\nCreando indices de consulta (filtrado por origen)...")
    for nombre in (COLECCION_GENERACION_EXITOSA, COLECCION_ERRORES, COLECCION_WARNINGS):
        bd[nombre].create_index([("origen.modulo", ASCENDING)])
        bd[nombre].create_index([("origen.proyecto", ASCENDING)])

    try:
        bd[COLECCION_RESUMEN_EJECUCIONES].create_index([("run_id", ASCENDING)], unique=True)
    except OperationFailure as e:
        print(f"  - Aviso al indexar 'run_id': {e}")
    bd[COLECCION_RESUMEN_EJECUCIONES].create_index([("timestamp_inicio", ASCENDING)])

    print("\nColecciones disponibles en la base de datos:")
    for nombre in sorted(bd.list_collection_names()):
        print(f"  - {nombre}")

    con.cerrar()


if __name__ == "__main__":
    provisionar()