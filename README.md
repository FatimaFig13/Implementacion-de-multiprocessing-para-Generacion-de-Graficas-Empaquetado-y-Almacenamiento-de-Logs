# Implementación de multiprocessing para Generación de Gráficas, Empaquetado y almacenamiento de Logs

Pipeline de visualización que consume datos tipo API (`PrepararDatos`),
genera gráficas dinámicamente (`Vizualizador`), y produce ese trabajo en
**paralelo** usando la librería nativa `multiprocessing`, empaquetando el
resultado de cada gráfica en 4 archivos: imagen, datos, estadísticos y
metadatos.

Cada ejecución queda además **auditada en MongoDB**: por cada gráfica se
registra si se generó con éxito o falló, y por cada corrida completa se
guarda un resumen (tareas totales, exitosas, fallidas, duración).

Todo el pipeline —incluyendo la aplicación y MongoDB— puede levantarse
**contenerizado con Docker**, sin instalar Python ni dependencias en tu
máquina, o bien correr solo Mongo en Docker y el pipeline localmente.

## 1. Descargar el repositorio

Si el proyecto está en un repositorio Git:

```bash
git clone https://github.com/FatimaFig13/Implementacion-de-multiprocessing-para-Generacion-de-Graficas-y-Empaquetado.git
cd API_Multi
```

## 2. Requisitos

- Docker y Docker Compose
- Python 3.9 o superior y pip — **solo** si vas a correr el pipeline de forma local (Opción B)

## 3. Crear el archivo `.env`

Antes de levantar nada, crea un archivo `.env` en la raíz del proyecto:

```env
MONGO_ROOT_USERNAME=stori_admin
MONGO_ROOT_PASSWORD=changeme_dev
MONGO_APP_USERNAME=stori_app
MONGO_APP_PASSWORD=changeme_app
```

`stori_admin` es la cuenta administradora de Mongo. `stori_app` es la
cuenta con permisos `readWrite` limitados a la base `stori_logs`, que el
pipeline usa para no depender nunca de la cuenta root; el script
`mongo-init/init-app-user.sh` la crea automáticamente la primera vez que
se levanta el volumen de Mongo.

## 4. Opción A — Todo en Docker (recomendado)

No necesitas instalar Python ni ninguna dependencia en tu máquina.

### 4.1 Construir la imagen de la aplicación

```bash
docker compose build
```

### 4.2 Levantar Mongo y esperar a que esté sano

```bash
docker compose up -d mongo_stori
docker compose ps
```

`mongo_stori` debe quedar con estado `healthy` (si dice `starting`, espera
unos segundos y vuelve a correr `docker compose ps`).

### 4.3 Provisionar las colecciones

```bash
docker compose run --rm -e MONGO_URI="mongodb://stori_admin:changeme_dev@mongo_stori:27017/?authSource=admin" stori_app python provisionar_bd.py
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

### 4.4 Ejecutar el pipeline

```bash
docker compose run --rm stori_app
```

Los paquetes generados quedan tanto dentro del contenedor como en
`./paquetes` de tu máquina, gracias al volumen configurado en
`docker-compose.yml`.

### 4.5 Apagar todo

```bash
docker compose down        # detiene los contenedores, conserva los datos de Mongo
docker compose down -v     # además borra el volumen de Mongo (reinicia desde cero)
```

## 6. Verificar que todo funciona

### 6.1 Salida esperada de la ejecución

```
[ventas_por_region] pid=XXXX (0.4XXs) -> OK
[distribucion_ventas] pid=YYYY (0.3XXs) -> OK
Paquete comprimido: paquetes/ventas_por_region.zip
Paquete comprimido: paquetes/distribucion_ventas.zip
```

Los dos `pid` deben ser **distintos** entre sí — es la evidencia de que las
gráficas se generaron en procesos separados (paralelismo real).

> Si el contenedor de Mongo no está levantado o el usuario de la aplicación
> aún no existe, verás además mensajes como
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

### 6.2 Pruebas automatizadas del paralelismo y empaquetado

Local:

```bash
python3 -m pytest test_productor_paquetes.py -v
```

Dentro de Docker:

```bash
docker compose run --rm stori_app pytest test_productor_paquetes.py -v
```

Deben pasar 8 pruebas (`PASSED`), incluyendo una que confirma que dos
tareas distintas corren en PIDs distintos, y otra que confirma que si una
tarea falla, las demás se completan y el `Pool` se cierra correctamente.

### 6.3 Revisar los logs guardados en Mongo

```bash
docker exec -it mongo_stori mongosh -u stori_admin -p changeme_dev \
  --authenticationDatabase admin stori_logs \
  --eval "db.logs_generacion_exitosa.find().pretty()"
```

Cambia la colección (`logs_errores`, `resumen_ejecuciones`, etc.) según lo
que quieras revisar.

### 6.4 Pruebas automatizadas de la capa de logging

Local:

```bash
python3 -m pytest test_conexion_mongo.py -v
```

Dentro de Docker:

```bash
docker compose run --rm stori_app pytest test_conexion_mongo.py -v
```

Estas corren contra `mongomock` (no requieren el contenedor levantado).
Si además quieres correr la prueba de integración contra el Mongo real:

```bash
python3 -m pytest test_conexion_mongo.py -v -m integracion
```

## 7. Notas sobre el usuario de aplicación en Mongo

El usuario `stori_app` (usado por el pipeline para escribir logs) **no**
se crea con `MONGO_INITDB_ROOT_USERNAME`/`PASSWORD` — esas variables solo
crean la cuenta root. Se crea automáticamente mediante
`mongo-init/init-app-user.sh`, que la imagen oficial de Mongo ejecuta
**solo la primera vez** que el volumen de datos está vacío. Si en algún
momento ves errores de `AuthenticationFailed` para `stori_app`, casi
siempre significa que el volumen de Mongo ya existía de una ejecución
anterior sin ese usuario; la solución es:

```bash
docker compose down -v
docker compose up -d mongo_stori
```

para que el volumen se recree desde cero y el script de inicialización
vuelva a correr.
