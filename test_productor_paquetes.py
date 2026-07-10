import json
import os
import tempfile

from productor_paquetes import (
    TareaGrafica,
    GeneradorParalelo,
    _generar_producto_worker,
    _calcular_estadisticos,
    empaquetar_zip,
)


PAYLOAD_BARRAS = {
    "data": [
        {"region": "Norte", "producto": "A", "ventas": "120"},
        {"region": "Norte", "producto": "B", "ventas": "80"},
        {"region": "Sur", "producto": "A", "ventas": "200"},
        {"region": "Sur", "producto": "B", "ventas": "150"},
    ],
    "config": {
        "tipo_grafico": "barras_agrupadas",
        "columna_x": "region",
        "columna_y": "ventas",
        "columna_grupo": "producto",
        "columnas_numericas": ["ventas"],
        "titulo": "Ventas por región",
    },
}

PAYLOAD_PASTEL = {
    "data": [
        {"categoria": "Electrónica", "monto": "500"},
        {"categoria": "Ropa", "monto": "300"},
        {"categoria": "Hogar", "monto": "200"},
    ],
    "config": {
        "tipo_grafico": "pastel",
        "columna_categoria": "categoria",
        "columna_valor": "monto",
        "columnas_numericas": ["monto"],
        "titulo": "Distribución de ventas",
    },
}

PAYLOAD_SIN_DATA = {"config": {"tipo_grafico": "lineas"}}


def test_worker_genera_los_4_archivos_del_paquete():
    with tempfile.TemporaryDirectory() as tmp:
        tarea = TareaGrafica(nombre="prueba_barras", payload=PAYLOAD_BARRAS, directorio_salida=tmp)
        resultado = _generar_producto_worker(tarea)

        assert resultado["ok"] is True
        assert resultado["error"] is None
        archivos = resultado["archivos"]
        assert set(archivos.keys()) == {"imagen", "datos", "estadisticos", "metadatos"}
        for ruta in archivos.values():
            assert os.path.isfile(ruta)


def test_worker_falla_limpiamente_si_no_hay_data():
    with tempfile.TemporaryDirectory() as tmp:
        tarea = TareaGrafica(nombre="prueba_sin_data", payload=PAYLOAD_SIN_DATA, directorio_salida=tmp)
        resultado = _generar_producto_worker(tarea)

        assert resultado["ok"] is False
        assert resultado["error"] is not None
        assert resultado["archivos"] == {}


def test_estadisticos_incluyen_columnas_numericas_y_categoricas():
    import pandas as pd

    df = pd.DataFrame({"region": ["Norte", "Sur"], "ventas": [10, 20]})
    stats = _calcular_estadisticos(df)

    assert stats["n_filas"] == 2
    assert "mean" in stats["columnas"]["ventas"]
    assert "mas_frecuente" in stats["columnas"]["region"]
    # debe ser serializable a JSON sin problemas (tipos nativos, no numpy)
    json.dumps(stats)


def test_generador_paralelo_procesa_todas_las_tareas():
    with tempfile.TemporaryDirectory() as tmp:
        tareas = [
            TareaGrafica(nombre="barras", payload=PAYLOAD_BARRAS),
            TareaGrafica(nombre="pastel", payload=PAYLOAD_PASTEL),
        ]
        generador = GeneradorParalelo(n_procesos=2, directorio_salida=tmp)
        resultados = generador.generar(tareas)

        assert len(resultados) == 2
        assert all(r["ok"] for r in resultados)
        # se ejecutaron en procesos hijos (nunca en el proceso de pytest)
        assert all(r["pid"] != os.getpid() for r in resultados)


def test_generador_paralelo_usa_procesos_distintos_para_tareas_distintas():
    with tempfile.TemporaryDirectory() as tmp:
        tareas = [
            TareaGrafica(nombre="barras", payload=PAYLOAD_BARRAS),
            TareaGrafica(nombre="pastel", payload=PAYLOAD_PASTEL),
        ]
        generador = GeneradorParalelo(n_procesos=2, directorio_salida=tmp)
        resultados = generador.generar(tareas)

        pids = {r["pid"] for r in resultados}
        assert len(pids) == 2  # cada tarea corrió en su propio proceso


def test_generador_paralelo_con_lista_vacia_no_falla():
    generador = GeneradorParalelo(n_procesos=2, directorio_salida="paquetes_vacio")
    assert generador.generar([]) == []


def test_generador_paralelo_continua_aunque_una_tarea_falle():
    with tempfile.TemporaryDirectory() as tmp:
        tareas = [
            TareaGrafica(nombre="valida", payload=PAYLOAD_BARRAS),
            TareaGrafica(nombre="invalida", payload=PAYLOAD_SIN_DATA),
        ]
        generador = GeneradorParalelo(n_procesos=2, directorio_salida=tmp)
        resultados = generador.generar(tareas)

        por_nombre = {r["nombre"]: r for r in resultados}
        assert por_nombre["valida"]["ok"] is True
        assert por_nombre["invalida"]["ok"] is False

def test_empaquetar_zip_contiene_los_4_archivos():
    with tempfile.TemporaryDirectory() as tmp:
        tarea = TareaGrafica(nombre="paquete_zip", payload=PAYLOAD_BARRAS, directorio_salida=tmp)
        resultado = _generar_producto_worker(tarea)
        carpeta = os.path.dirname(resultado["archivos"]["imagen"])

        ruta_zip = empaquetar_zip(carpeta)

        assert os.path.isfile(ruta_zip)
        import zipfile
        with zipfile.ZipFile(ruta_zip) as z:
            nombres = z.namelist()
            assert len(nombres) == 4


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))