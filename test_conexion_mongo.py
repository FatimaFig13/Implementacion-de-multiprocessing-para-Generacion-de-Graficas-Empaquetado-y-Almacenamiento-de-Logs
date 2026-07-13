import mongomock
import pytest
from pydantic import ValidationError

from conexion_mongo import (
    COLECCION_ERRORES,
    COLECCION_GENERACION_EXITOSA,
    COLECCION_RESUMEN_EJECUCIONES,
    COLECCION_WARNINGS,
    ConexionMongo,
    RegistradorEventos,
)


@pytest.fixture
def conexion(monkeypatch):
    """ConexionMongo respaldada por mongomock en vez de un servidor real."""
    monkeypatch.setattr("conexion_mongo.MongoClient", mongomock.MongoClient)
    con = ConexionMongo(uri="mongodb://localhost:27017", nombre_bd="stori_logs_test")
    yield con
    con.cerrar()


@pytest.fixture
def registrador(conexion):
    return RegistradorEventos(conexion)


ORIGEN_PRUEBA = {"modulo": "GeneradorParalelo", "proceso_id": "12345", "proyecto": "STORI"}


def test_registrar_generacion_exitosa_escribe_documento(registrador, conexion):
    id_insertado = registrador.registrar_generacion_exitosa(
        origen=ORIGEN_PRUEBA,
        nombre_tarea="ventas_por_region",
        tipo_grafico="barras_agrupadas",
        n_filas=4,
        columnas=["region", "producto", "ventas"],
        archivos={"imagen": "paquetes/ventas_por_region/ventas_por_region.png"},
        duracion_ms=842.5,
    )

    assert id_insertado is not None
    coleccion = conexion.coleccion(COLECCION_GENERACION_EXITOSA)
    assert coleccion.count_documents({}) == 1

    doc = coleccion.find_one({})
    assert doc["nombre_tarea"] == "ventas_por_region"
    assert doc["nivel"] == "INFO"
    assert doc["origen"]["modulo"] == "GeneradorParalelo"


def test_registrar_error_escribe_documento(registrador, conexion):
    registrador.registrar_error(
        origen=ORIGEN_PRUEBA,
        nombre_tarea="distribucion_ventas",
        tipo_excepcion="KeyError",
        mensaje_error="Columnas no encontradas en los datos de la API: ['monto']",
        duracion_ms=120.0,
    )

    coleccion = conexion.coleccion(COLECCION_ERRORES)
    assert coleccion.count_documents({}) == 1
    doc = coleccion.find_one({})
    assert doc["nivel"] == "ERROR"
    assert doc["tipo_excepcion"] == "KeyError"


def test_registrar_warning_escribe_documento(registrador, conexion):
    registrador.registrar_warning(
        origen=ORIGEN_PRUEBA,
        nombre_tarea="ventas_por_region",
        mensaje="La columna 'paleta' no fue especificada, se usa la paleta por defecto.",
        contexto={"columna": "paleta"},
    )

    coleccion = conexion.coleccion(COLECCION_WARNINGS)
    assert coleccion.count_documents({}) == 1
    assert coleccion.find_one({})["nivel"] == "WARNING"


def test_registrar_resumen_ejecucion_escribe_documento(registrador, conexion):
    from datetime import datetime, timezone

    registrador.registrar_resumen_ejecucion(
        run_id="run-2026-07-12-001",
        timestamp_inicio=datetime(2026, 7, 12, 10, 0, tzinfo=timezone.utc),
        timestamp_fin=datetime(2026, 7, 12, 10, 0, 5, tzinfo=timezone.utc),
        n_procesos=2,
        total_tareas=2,
        exitosas=2,
        fallidas=0,
        duracion_total_seg=5.2,
    )

    coleccion = conexion.coleccion(COLECCION_RESUMEN_EJECUCIONES)
    assert coleccion.count_documents({}) == 1
    doc = coleccion.find_one({"run_id": "run-2026-07-12-001"})
    assert doc["exitosas"] == 2
    assert doc["fallidas"] == 0


def test_multiples_eventos_se_acumulan_en_la_coleccion(registrador, conexion):
    for i in range(5):
        registrador.registrar_generacion_exitosa(
            origen=ORIGEN_PRUEBA,
            nombre_tarea=f"tarea_{i}",
            duracion_ms=100.0 + i,
        )

    coleccion = conexion.coleccion(COLECCION_GENERACION_EXITOSA)
    assert coleccion.count_documents({}) == 5


def test_registrar_evento_con_datos_invalidos_no_se_escribe(registrador, conexion):
    """La validacion Pydantic debe rechazar el documento ANTES de llegar a Mongo
    (aqui: falta el campo obligatorio 'duracion_ms')."""
    with pytest.raises(ValidationError):
        registrador.registrar_generacion_exitosa(
            origen=ORIGEN_PRUEBA,
            nombre_tarea="tarea_incompleta",
        )

    coleccion = conexion.coleccion(COLECCION_GENERACION_EXITOSA)
    assert coleccion.count_documents({}) == 0


def test_verificar_conexion_responde_true_con_mongomock(conexion):
    assert conexion.verificar_conexion() is True


# ---------------------------------------------------------------------------
# Prueba de integracion opcional contra el contenedor real (docker compose)
# ---------------------------------------------------------------------------

@pytest.mark.integracion
def test_integracion_mongo_real():
    con = ConexionMongo()
    if not con.verificar_conexion():
        pytest.skip("No hay conexion a un MongoDB real (levanta `docker compose up -d`).")

    registrador = RegistradorEventos(con)
    id_insertado = registrador.registrar_generacion_exitosa(
        origen=ORIGEN_PRUEBA,
        nombre_tarea="prueba_integracion",
        duracion_ms=10.0,
    )
    assert id_insertado is not None

    coleccion = con.coleccion(COLECCION_GENERACION_EXITOSA)
    coleccion.delete_many({"nombre_tarea": "prueba_integracion"})
    con.cerrar()


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "-m", "not integracion"]))