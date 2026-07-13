from __future__ import annotations

import json
import multiprocessing as mp
import os
import shutil
import time
import traceback
import uuid
from datetime import datetime, timezone
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

# Timeout corto para las conexiones "best-effort" de logging: si Mongo no
# esta disponible, no queremos que cada worker se quede colgado esperando.
_TIMEOUT_LOGGING_MS = 800


@dataclass
class TareaGrafica:
    nombre: str
    payload: dict
    directorio_salida: str = "paquetes"
    formato_imagen: str = "png"

def _generar_producto_worker_interno(tarea: TareaGrafica) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    from fuente_datos import PrepararDatos
    from visualizador import Vizualizador

    inicio = time.time()
    pid = os.getpid()

    resultado = {
        "nombre": tarea.nombre,
        "pid": pid,
        "ok": False, 
        "error": None, 
        "archivos": {},
        "duracion_seg": None,
    }

    fig=None

    try:
        fuente= PrepararDatos()
        cargando= fuente.cargar_desde_payload(tarea.payload)

        if not cargando:
            resultado["error"] = f"Fallo al acargar datos: {fuente.error}."
            return resultado
        
        viz = Vizualizador(fuente)
        fig = viz.graficar(mostrar=False, guardar=False)

        if fig is None:
            resultado["error"] = "El visualizador no genero ninguna figura (revisar tipo_grafico/columnas)."
            return resultado
        
        directorio_paquete = os.path.join(tarea.directorio_salida, tarea.nombre)
        os.makedirs(directorio_paquete, exist_ok=True)

        ruta_imagen = os.path.join(directorio_paquete, f"{tarea.nombre}.{tarea.formato_imagen}")
        fig.savefig(ruta_imagen, dpi=150, bbox_inches="tight")

        ruta_csv = os.path.join(directorio_paquete, f"{tarea.nombre}_datos.csv")
        fuente.df.to_csv(ruta_csv, index=False)

        estadisticos = _calcular_estadisticos(fuente.df)
        ruta_estadisticos = os.path.join(directorio_paquete, f"{tarea.nombre}_estadisticos.json")
        with open(ruta_estadisticos, "w", encoding="utf-8") as f:
            json.dump(estadisticos, f, ensure_ascii=False, indent=2, default=str)
        
        metadatos_out = {
            "config_original": fuente.metadatos,
            "columnas": list(fuente.df.columns),
            "n_filas": len(fuente.df),
            "tipo_grafico": fuente.metadatos.get("tipo_grafico"),
            "generado_por_pid": pid,
        }

        ruta_metadatos = os.path.join(directorio_paquete, f"{tarea.nombre}_metadatos.json")
        with open(ruta_metadatos, "w", encoding="utf-8") as f:
            json.dump(metadatos_out, f, ensure_ascii=False, indent=2, default=str)
        
        resultado["ok"] = True
        resultado["archivos"] = {
            "imagen": ruta_imagen,
            "datos": ruta_csv,
            "estadisticos": ruta_estadisticos,
            "metadatos": ruta_metadatos,
        }
        resultado["metadatos"] = metadatos_out

    except Exception as e:
        resultado["error"] = f"{type(e).__name__}: {e}"
        resultado["traceback"] = traceback.format_exc()
    

    finally: 
        if fig is not None:
            plt.close(fig)
        plt.close("all")
        resultado["duracion_seg"] = round(time.time() - inicio, 3)
 
    return resultado



_conexion_mongo_worker = None
_registrador_worker = None


def _obtener_registrador_worker():
   
    global _conexion_mongo_worker, _registrador_worker

    if _registrador_worker is not None:
        return _registrador_worker

    try:
        from conexion_mongo import ConexionMongo, RegistradorEventos

        con = ConexionMongo(timeout_ms=_TIMEOUT_LOGGING_MS)
        if not con.verificar_conexion():
            print("[auditoria] Mongo no disponible, se omite el logging de este proceso.")
            return None

        _conexion_mongo_worker = con
        _registrador_worker = RegistradorEventos(con)
        return _registrador_worker
    except Exception as e:
        print(f"[auditoria] No se pudo inicializar la conexion a MongoDB: {e}")
        return None


def _extraer_tipo_excepcion(mensaje_error: Optional[str]) -> Optional[str]:
    if not mensaje_error or ":" not in mensaje_error:
        return None
    posible_tipo = mensaje_error.split(":", 1)[0].strip()
    return posible_tipo if posible_tipo.isidentifier() else None


def _registrar_resultado_en_mongo(tarea: TareaGrafica, resultado: dict) -> None:
    registrador = _obtener_registrador_worker()
    if registrador is None:
        return

    origen = {
        "modulo": "GeneradorParalelo",
        "proceso_id": str(resultado.get("pid", os.getpid())),
        "proyecto": "STORI",
    }
    duracion_ms = (resultado.get("duracion_seg") or 0.0) * 1000

    try:
        if resultado.get("ok"):
            metadatos = resultado.get("metadatos") or {}
            registrador.registrar_generacion_exitosa(
                origen=origen,
                nombre_tarea=tarea.nombre,
                tipo_grafico=metadatos.get("tipo_grafico"),
                n_filas=metadatos.get("n_filas"),
                columnas=metadatos.get("columnas", []),
                archivos=resultado.get("archivos", {}),
                duracion_ms=duracion_ms,
            )
        else:
            mensaje_error = resultado.get("error") or "Error desconocido"
            registrador.registrar_error(
                origen=origen,
                nombre_tarea=tarea.nombre,
                tipo_excepcion=_extraer_tipo_excepcion(mensaje_error),
                mensaje_error=mensaje_error,
                duracion_ms=duracion_ms,
            )
    except Exception as e:
        # El logging jamas debe tumbar la generacion de graficas.
        print(f"[auditoria] No se pudo registrar el evento en MongoDB: {e}")


def _generar_producto_worker(tarea: TareaGrafica) -> dict:
    
    resultado = _generar_producto_worker_interno(tarea)
    _registrar_resultado_en_mongo(tarea, resultado)
    return resultado


def _calcular_estadisticos(df: pd.DataFrame)-> dict:
    numericas = df.select_dtypes(include="number")
    describe_num = numericas.describe().to_dict() if not numericas.empty else {}

    salida = {"n_filas": int(len(df)), "n_columnas": int(df.shape[1]), "columnas":{}}

    for col in df.columns:
        info_col = {"dtype": str(df[col].dtype), "nulos": int(df[col].isna().sum())}

        if col in describe_num:
            info_col.update(
                {k: (None if pd.isna(v) else float(v)) for k, v in describe_num[col].items()})
        else:
            info_col["valores_unicos"] = int(df[col].nunique())
            conteo = df[col].value_counts()
            if not conteo.empty:
                info_col["mas_frecuente"] = str(conteo.index[0])
                info_col["frecuencia_mas_frecuente"] = int(conteo.iloc[0])
        salida["columnas"][col] = info_col

    return salida

class GeneradorParalelo:

    def __init__(self, n_procesos: Optional[int] = None, directorio_salida: str = "paquetes"):

        cpus_disponibles = os.cpu_count() or 1
        self.n_procesos = n_procesos or max(1, cpus_disponibles -1)
        self.directorio_salida = directorio_salida

    def generar(self, tareas: list[TareaGrafica])->list[dict]:
        if not tareas: 
            return []
        
        for t in tareas:
            t.directorio_salida = self.directorio_salida
        
        os.makedirs(self.directorio_salida, exist_ok=True)

        n_procesos = min(self.n_procesos, len(tareas))
        ctx = mp.get_context("spawn")
        pool = ctx.Pool(processes=n_procesos)

        inicio = datetime.now(timezone.utc)
        try:
            resultados = pool.map(_generar_producto_worker, tareas)
        finally:
            pool.close()
            pool.join()
        fin = datetime.now(timezone.utc)

        self._registrar_resumen_ejecucion(tareas, resultados, n_procesos, inicio, fin)
        return resultados

    def _registrar_resumen_ejecucion(self, tareas, resultados, n_procesos, inicio, fin) -> None:
        try:
            from conexion_mongo import ConexionMongo, RegistradorEventos

            con = ConexionMongo(timeout_ms=_TIMEOUT_LOGGING_MS)
            if not con.verificar_conexion():
                print("[auditoria] Mongo no disponible, se omite el resumen de la ejecucion.")
                return

            registrador = RegistradorEventos(con)
            exitosas = sum(1 for r in resultados if r.get("ok"))
            registrador.registrar_resumen_ejecucion(
                run_id=str(uuid.uuid4()),
                timestamp_inicio=inicio,
                timestamp_fin=fin,
                n_procesos=n_procesos,
                total_tareas=len(tareas),
                exitosas=exitosas,
                fallidas=len(tareas) - exitosas,
                duracion_total_seg=(fin - inicio).total_seconds(),
            )
            con.cerrar()
        except Exception as e:
            print(f"[auditoria] No se pudo registrar el resumen de la ejecucion: {e}")
    
def empaquetar_zip(directorio_paquete: str, ruta_zip: Optional[str] = None)->str:
    
    if not os.path.isdir(directorio_paquete):
        raise FileNotFoundError(f"No existe el directorio del paquete: {directorio_paquete}")
 
    base_zip = ruta_zip[:-4] if ruta_zip and ruta_zip.endswith(".zip") else (ruta_zip or directorio_paquete)
    
    return shutil.make_archive(base_zip, "zip", directorio_paquete)

def resumen_ejecucion(resultados: list[dict]) -> str:
    lineas = []
   
    for r in resultados:
        estado = "OK" if r["ok"] else f"ERROR: {r['error']}"
        lineas.append(f"[{r['nombre']}] pid={r['pid']} ({r['duracion_seg']}s) -> {estado}")
    return "\n".join(lineas)

if __name__=="__main__":

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

    tareas = [
        TareaGrafica(nombre="ventas_por_region", payload=PAYLOAD_BARRAS),
        TareaGrafica(nombre="distribucion_ventas", payload=PAYLOAD_PASTEL),
    ]

    generador = GeneradorParalelo(n_procesos=2, directorio_salida="paquetes")
    resultados = generador.generar(tareas)
 
    print(resumen_ejecucion(resultados))
 
    for r in resultados:
        if r["ok"]:
            carpeta = os.path.dirname(r["archivos"]["imagen"])
            ruta_zip = empaquetar_zip(carpeta)
            print(f"Paquete comprimido: {ruta_zip}")
