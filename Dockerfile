FROM python:3.11-slim

WORKDIR /app

# Establecer variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Actualizar pip e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    # Instalar Redis explícitamente
    pip install --no-cache-dir redis==5.0.1 hiredis==2.2.3 && \
    # Verificar que Redis se instaló correctamente
    python -c "import redis; from redis.asyncio import Redis; print(f'Redis {redis.__version__} instalado correctamente')"

# Copiar el código de la aplicación
COPY . .

# Verificar que Redis se puede importar desde el código
RUN python -c "import sys; sys.path.insert(0, '/app'); from app.services.user import user_service; print('Módulo user_service importado correctamente')"

# Puerto en el que se ejecuta la aplicación
EXPOSE 8000

# Comando para iniciar la aplicación usando el wrapper
# El puerto será manejado por Render a través de la variable PORT inyectada
CMD ["python", "app_wrapper.py"] 