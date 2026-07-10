from enum import Enum

import pandas as pd
import requests

class EstadoCarga(Enum):
    INACTIVO = "inactivo"
    CARGANDO = "cargando"
    EXITO = "exito"
    ERROR = "error"

class PrepararDatos:
    
    def __init__(self, timeout=10):
        self.timeout = timeout
        self.estado = EstadoCarga.INACTIVO
        self.error = None
        self.df = None
        self.metadatos = {}
        self.payload_crudo = None
    
    # ---- Carga desde un endpoint real -------------------------------------
    
    def cargar_desde_endpoints(self, url, params=None, headers=None):
        self.estado = EstadoCarga.CARGANDO
        self.error = None

        try:
            resp = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            payload = resp.json()
        except requests.exceptions.RequestException as e:
            self.estado = EstadoCarga.ERROR
            self.error = f"Error de conexion con la API: {e}"
            return False
        except ValueError as e:
            self.estado = EstadoCarga.ERROR
            self.error = f"La API no delvovio un JSON valido: {e}"
            return False
        return self._procesar_payload(payload)
    
    # ---- Carga desde un payload ya obtenido (mocks, tests, cache) ---------
    
    def cargar_desde_payload(self, payload):
        self.estado = EstadoCarga.CARGANDO
        self.error = None
        return self._procesar_payload(payload)
    
    # ---- Logica interna de mapeo/transformacion ----------------------------
    
    def _procesar_payload(self, payload):
        self.payload_crudo = payload

        if not isinstance(payload, dict):
            self.estado = EstadoCarga.ERROR
            self.error = "El payload de la API debe ser un objeto JSON (dict)."
            return False
        
        datos = payload.get("data")
        metadatos = payload.get("config", payload.get("metadata", {})) or {}

        if datos is None:
            self.estado = EstadoCarga.ERROR
            self.error = "El payload no contiene la clave 'data' con los registros."
            return False
        
        if not isinstance(datos, list) or len(datos) == 0:
            self.estado = EstadoCarga.ERROR
            self.error = "El payload no contiene filas de datos (lista 'data' vacia)."
            return False
        
        try:
            df = pd.DataFrame(datos)
        except Exception as e:
            self.estado = EstadoCarga.ERROR
            self.error = f"No se pudo convertir 'data' en un DataFrame: {e}"
            return False
 
        if df.empty:
            self.estado = EstadoCarga.ERROR
            self.error = "El DataFrame resultante esta vacio."
            return False
 
        for col in metadatos.get("columnas_numericas", []):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
 
        self.df = df
        self.metadatos = metadatos
        self.estado = EstadoCarga.EXITO
        self.error = None
        return True
    
    # ---- Utilidades de consulta de estado ----------------------------------

    def esta_en_exito(self):
        return self.estado == EstadoCarga.EXITO
 
    def esta_en_error(self):
        return self.estado == EstadoCarga.ERROR
 
    def esta_cargando(self):
        return self.estado == EstadoCarga.CARGANDO

