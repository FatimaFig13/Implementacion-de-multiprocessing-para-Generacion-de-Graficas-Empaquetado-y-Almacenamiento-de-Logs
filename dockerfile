FROM python:3.11-slim
 
# Evita .pyc y fuerza salida de logs sin buffer (util para ver logs con docker compose logs -f)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
 
WORKDIR /app
 
# Dependencias del sistema necesarias para compilar/soportar matplotlib y pandas
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
 
# Se copian primero los requirements para aprovechar el cache de capas de Docker:
# si el codigo cambia pero no las dependencias, este paso no se vuelve a ejecutar.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
# Codigo del pipeline
COPY conexion_mongo.py esquemas_log.py fuente_datos.py \
     productor_paquetes.py provisionar_bd.py visualizador.py \
     pytest.ini ./
COPY test_conexion_mongo.py test_productor_paquetes.py ./
 
# Directorio donde GeneradorParalelo escribe los paquetes de salida
RUN mkdir -p /app/paquetes
 
CMD ["python", "productor_paquetes.py"]
 