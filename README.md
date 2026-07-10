# Implementación de multiprocessing para Generación de Gráficas y Empaquetado

Pipeline de visualización que consume datos tipo API (`PrepararDatos`),
genera gráficas dinámicamente (`Vizualizador`), y produce ese trabajo en
**paralelo** usando la librería nativa `multiprocessing`, empaquetando el
resultado de cada gráfica en 4 archivos: imagen, datos, estadísticos y
metadatos.

## Contenido del repositorio

Estos 5 archivos deben estar en la **misma carpeta**:

```
API_Multi/
├── fuente_datos.py             # PrepararDatos: carga y transforma el payload de la API
├── visualizador.py             # Vizualizador: genera las gráficas a partir de los metadatos
├── productor_paquetes.py       # GeneradorParalelo: orquesta la generación en paralelo y el empaquetado
└── test_productor_paquetes.py  # Pruebas del paralelismo y del empaquetado
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

## 3. Instalar dependencias

Desde la carpeta del proyecto:

```bash
pip install pandas matplotlib seaborn requests pytest
```

(Opcional pero recomendado) usa un entorno virtual antes de instalar:

```bash
python3 -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate
pip install pandas matplotlib seaborn requests pytest
```

## 4. Verificar que todo funciona

### 4.1 Ejecución manual del módulo de paralelismo

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

### 4.2 Pruebas automatizadas del paralelismo y empaquetado

```bash
python3 -m pytest test_productor_paquetes.py -v
```

Deben pasar 8 pruebas (`PASSED`), incluyendo una que confirma que dos
tareas distintas corren en PIDs distintos, y otra que confirma que si una
tarea falla, las demás se completan y el `Pool` se cierra correctamente.
---
