# Implementación de multiprocessing para Generación de Gráficas, Empaquetado y almacenamiento de Logs

Pipeline de visualización que consume datos tipo API (`PrepararDatos`),
genera gráficas dinámicamente (`Vizualizador`), y produce ese trabajo en
**paralelo** usando la librería nativa `multiprocessing`, empaquetando el
resultado de cada gráfica en 4 archivos: imagen, datos, estadísticos y
metadatos.
 
Cada ejecución queda además **auditada en MongoDB**: por cada gráfica se
registra si se generó con éxito o falló, y por cada corrida completa se
guarda un resumen (tareas totales, exitosas, fallidas, duración).
## Contenido del repositorio

Estos archivos deben estar en la **misma carpeta**:

```
API/
├── fuente_datos.py             # PrepararDatos: carga y transforma el payload de la API
├── visualizador.py             # Vizualizador: genera las gráficas a partir de los metadatos
├── productor_paquetes.py       # GeneradorParalelo: orquesta la generación en paralelo, el empaquetado y la auditoría
├── test_productor_paquetes.py  # Pruebas del paralelismo y del empaquetado
│
├── docker-compose.yml          # Instancia de MongoDB en contenedor
├── esquemas_log.py             # Esquemas Pydantic de los documentos de log (fuente de verdad)
├── conexion_mongo.py           # ConexionMongo y RegistradorEventos: conexión y escritura de logs
├── provisionar_bd.py           # Script idempotente: crea colecciones, validadores e índices
├── test_conexion_mongo.py      # Pruebas unitarias de escritura de logs (con mongomock)
```

## 1. Descargar el repositorio
 
Si el proyecto está en un repositorio Git:
 
```bash
git clone https://github.com/FatimaFig13/Implementacion-de-multiprocessing-para-Generacion-de-Graficas-y-Empaquetado.git
cd API_Multi
```
 
 
## 2. Requisitos
 
- Python 3.9 o superior
- pip
- Docker y Docker Compose (para la instancia de MongoDB de auditoría)
## 3. Instalar dependencias
 
Desde la carpeta del proyecto:
 
```bash
pip install pandas matplotlib seaborn requests pytest pymongo pydantic mongomock
```
 
(Opcional pero recomendado) usa un entorno virtual antes de instalar:
 
```bash
python3 -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate
pip install pandas matplotlib seaborn requests pytest pymongo pydantic mongomock
```
 
## 4. Levantar la base de datos de auditoría (MongoDB)
 
### 4.1 Levantar el contenedor
 
```bash
cp .env.example .env
docker compose up -d
docker compose ps
```
 
`mongo_stori` debe quedar con estado `healthy` (si dice `starting`, espera
unos segundos y vuelve a correr `docker compose ps`).
 
### 4.2 Crear las colecciones
 
```bash
python3 provisionar_bd.py
```
 
Este script es **idempotente** (se puede correr varias veces sin duplicar
nada) y crea, dentro de la base `stori_logs`:
 
| Colección | Contenido |
|---|---|
| `logs_generacion_exitosa` | Un documento por cada gráfica generada con éxito |
| `logs_errores` | Un documento por cada gráfica que falló, con el mensaje de error |
| `logs_warnings` | Advertencias no fatales del pipeline |
| `resumen_ejecuciones` | Un documento por cada corrida completa de `GeneradorParalelo.generar()` |
 
Todas con validación `$jsonSchema` (rechazan documentos mal formados) y con
retención automática a 90 días (índice TTL sobre `timestamp`).
 
## 5. Verificar que todo funciona
 
### 5.1 Ejecución manual del módulo de paralelismo
 
```bash
python3 productor_paquetes.py
```
 
Salida esperada:
 
```
[ventas_por_region] pid=XXXX (0.4XXs) -> OK
[distribucion_ventas] pid=YYYY (0.3XXs) -> OK
Paquete comprimido: paquetes/ventas_por_region.zip
Paquete comprimido: paquetes/distribucion_ventas.zip
```
 
Los dos `pid` deben ser **distintos** entre sí — es la evidencia de que las
gráficas se generaron en procesos separados (paralelismo real).
 
> Si el contenedor de Mongo no está levantado, verás además mensajes como
> `[auditoria] Mongo no disponible, se omite el logging de este proceso.`
> El pipeline sigue funcionando normalmente: el logging es "best-effort" y
> nunca detiene la generación de gráficas.
 
Revisa que los archivos se hayan creado:
 
```bash
find paquetes -type f
```
 
Deberías ver, por cada gráfica, su propia carpeta con 4 archivos:
 
```
paquetes/ventas_por_region/ventas_por_region.png
paquetes/ventas_por_region/ventas_por_region_datos.csv
paquetes/ventas_por_region/ventas_por_region_estadisticos.json
paquetes/ventas_por_region/ventas_por_region_metadatos.json
paquetes/ventas_por_region.zip
```
 
### 5.2 Pruebas automatizadas del paralelismo y empaquetado
 
```bash
python3 -m pytest test_productor_paquetes.py -v
```
 
Deben pasar 8 pruebas (`PASSED`), incluyendo una que confirma que dos
tareas distintas corren en PIDs distintos, y otra que confirma que si una
tarea falla, las demás se completan y el `Pool` se cierra correctamente.
 
### 5.3 Revisar los logs guardados en Mongo
 
```bash
docker exec -it mongo_stori mongosh -u stori_admin -p changeme_dev \
  --authenticationDatabase admin stori_logs \
  --eval "db.logs_generacion_exitosa.find().pretty()"
```
 
Cambia la colección (`logs_errores`, `resumen_ejecuciones`, etc.) según lo
que quieras revisar.
 
### 5.4 Pruebas automatizadas de la capa de logging
 
```bash
python3 -m pytest test_conexion_mongo.py -v
```
 
Estas corren contra `mongomock` (no requieren el contenedor levantado).
Si además quieres correr la prueba de integración contra el Mongo real:
 
```bash
python3 -m pytest test_conexion_mongo.py -v -m integracion
```
