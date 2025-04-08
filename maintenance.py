"""
Script de mantenimiento para la API de gimnasios

Este script realiza tareas periódicas de mantenimiento:
1. Limpieza de caches
2. Verificación de conexiones a servicios externos
3. Optimización de base de datos
4. Monitoreo de rendimiento
"""

import time
import logging
import argparse
import sys
import psutil
import psycopg2
import requests
from datetime import datetime, timedelta
import schedule
import threading
import signal

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("maintenance.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("maintenance")

# Importar servicios de la aplicación
try:
    from app.db.session import get_db, engine
    from app.core.stream_client import stream_client
    from app.services.chat import chat_service
    
    # Bandera para indicar que podemos acceder a los módulos internos
    internal_modules_available = True
    logger.info("Módulos internos de la aplicación cargados correctamente")
except ImportError as e:
    logger.warning(f"No se pudieron cargar módulos internos de la aplicación: {e}")
    internal_modules_available = False
    
# URL de conexión de base de datos para mantenimiento directo
DB_URL = "postgresql://postgres:Jazdi0-cyhvan-pofduz@db.ueijlkythlkqadxymzqd.supabase.co:5432/postgres"

def check_services_health():
    """Verificar el estado de los servicios externos"""
    logger.info("Verificando salud de servicios externos...")
    
    # Verificar base de datos
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        if cursor.fetchone():
            logger.info("✅ Base de datos: Conexión exitosa")
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"❌ Base de datos: Error de conexión - {str(e)}")
    
    # Verificar Stream Chat si está disponible
    if internal_modules_available:
        try:
            # Intentar una operación básica con Stream
            response = stream_client.get_app_settings()
            if response:
                logger.info(f"✅ Stream Chat: Conexión exitosa - Configuración obtenida")
            else:
                logger.warning("⚠️ Stream Chat: Conexión exitosa pero sin datos")
        except Exception as e:
            logger.error(f"❌ Stream Chat: Error de conexión - {str(e)}")

def cleanup_caches():
    """Limpiar las caches de la aplicación"""
    logger.info("Limpiando caches...")
    
    if internal_modules_available:
        try:
            # Limpiar cache de chat usando el método interno
            chat_service.cleanup_caches()
            logger.info("✅ Limpieza de caches de chat completada")
        except Exception as e:
            logger.error(f"❌ Error limpiando caches de chat: {str(e)}")
    else:
        logger.warning("⚠️ No se pueden limpiar caches (módulos internos no disponibles)")

def optimize_database():
    """Realizar tareas de optimización en la base de datos"""
    logger.info("Optimizando base de datos...")
    
    try:
        # Crear conexión directa para mantenimiento
        engine = create_engine(DB_URL)
        conn = engine.connect()
        
        # Lista de consultas de mantenimiento
        maintenance_queries = [
            # Vacuum para recuperar espacio y actualizar estadísticas
            "VACUUM ANALYZE",
            
            # Reindexar tablas principales para mejorar rendimiento
            "REINDEX TABLE events",
            "REINDEX TABLE event_participations",
            "REINDEX TABLE chat_rooms",
            "REINDEX TABLE user"
        ]
        
        # Ejecutar cada consulta
        for query in maintenance_queries:
            try:
                logger.info(f"Ejecutando: {query}")
                conn.execute(text(query))
                logger.info(f"✅ Consulta completada correctamente: {query}")
            except Exception as e:
                logger.error(f"❌ Error ejecutando {query}: {str(e)}")
        
        conn.close()
        logger.info("Optimización de base de datos completada")
    except Exception as e:
        logger.error(f"❌ Error conectando a la base de datos para optimización: {str(e)}")

def monitor_system_resources():
    """Monitorear recursos del sistema"""
    logger.info("Monitoreando recursos del sistema...")
    
    # Obtener uso de CPU y memoria
    cpu_percent = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    
    # Registrar información
    logger.info(f"Uso de CPU: {cpu_percent}%")
    logger.info(f"Uso de memoria: {memory_info.percent}% ({memory_info.used / 1024 / 1024:.2f} MB)")
    
    # Alertar si el uso es muy alto
    if cpu_percent > 90:
        logger.warning(f"⚠️ ALERTA: Uso de CPU muy alto ({cpu_percent}%)")
    
    if memory_info.percent > 90:
        logger.warning(f"⚠️ ALERTA: Uso de memoria muy alto ({memory_info.percent}%)")

def run_scheduled_tasks():
    """Ejecutar todas las tareas de mantenimiento"""
    logger.info("Ejecutando tareas de mantenimiento programadas...")
    
    try:
        # Registrar inicio
        start_time = time.time()
        
        # Ejecutar tareas
        check_services_health()
        cleanup_caches()
        optimize_database()
        monitor_system_resources()
        
        # Registrar tiempo total
        execution_time = time.time() - start_time
        logger.info(f"Tareas de mantenimiento completadas en {execution_time:.2f} segundos")
    except Exception as e:
        logger.error(f"Error durante las tareas de mantenimiento: {str(e)}", exc_info=True)

def schedule_manager():
    """Gestionar la programación de tareas"""
    # Programar tareas
    schedule.every(15).minutes.do(check_services_health)
    schedule.every(30).minutes.do(cleanup_caches)
    schedule.every(1).day.at("03:00").do(optimize_database)
    schedule.every(5).minutes.do(monitor_system_resources)
    schedule.every(1).hour.do(run_scheduled_tasks)
    
    logger.info("Tareas programadas configuradas. Iniciando ciclo de ejecución...")
    
    # Ejecutar en bucle
    while True:
        schedule.run_pending()
        time.sleep(1)

def run_once():
    """Ejecutar todas las tareas una vez"""
    logger.info("Ejecutando tareas de mantenimiento una sola vez...")
    run_scheduled_tasks()

def signal_handler(sig, frame):
    """Manejador para señales de terminación"""
    logger.info("Señal de terminación recibida. Finalizando script de mantenimiento...")
    sys.exit(0)

if __name__ == "__main__":
    # Configurar el manejador de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Configurar argumentos
    parser = argparse.ArgumentParser(description="Script de mantenimiento para la API de gimnasios")
    parser.add_argument("--once", action="store_true", help="Ejecutar tareas una sola vez")
    parser.add_argument("--schedule", action="store_true", help="Ejecutar tareas según programación")
    
    args = parser.parse_args()
    
    if args.once:
        run_once()
    elif args.schedule:
        # Iniciar el gestor de programación en un hilo
        scheduler_thread = threading.Thread(target=schedule_manager)
        scheduler_thread.daemon = True
        scheduler_thread.start()
        
        logger.info("Scheduler iniciado. Presiona Ctrl+C para salir.")
        
        try:
            # Mantener el programa principal vivo
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrumpido por el usuario. Saliendo...")
    else:
        parser.print_help() 