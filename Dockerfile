FROM python:3.11-slim

WORKDIR /app

# Establecer variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Actualizar pip e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    # Instalar directamente desde requirements.txt ahora que las versiones son compatibles
    pip install --no-cache-dir -r requirements.txt && \
    # Verificar que Redis, Supabase, Stream Chat y APScheduler se instalaron correctamente
    python -c "import redis; from redis.asyncio import Redis; import supabase; import stream_chat; import apscheduler; print(f'Redis {redis.__version__}, Supabase {supabase.__version__}, Stream Chat importado, APScheduler {apscheduler.__version__} instalados correctamente')"

# Copiar el código de la aplicación
COPY . .

# Puerto en el que se ejecuta la aplicación
EXPOSE 8000

# Comando para iniciar la aplicación usando el wrapper
# El puerto será manejado por Render a través de la variable PORT inyectada
CMD ["python", "app_wrapper.py"] 