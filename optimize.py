#!/usr/bin/env python3
"""
Script para aplicar todas las optimizaciones de rendimiento a la API de gimnasios

Este script ejecuta todas las optimizaciones implementadas:
1. Creación de índices para tablas principales
2. Optimización de consultas SQL
3. Limpieza de caché
4. Optimización de base de datos
"""

import os
import sys
import time
import subprocess
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("optimization.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("optimize")

def run_script(script_name, description):
    """Ejecutar un script Python"""
    logger.info(f"Ejecutando {description}...")
    
    try:
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, script_name],
            check=True,
            capture_output=True,
            text=True
        )
        execution_time = time.time() - start_time
        
        logger.info(f"✅ {description} completado en {execution_time:.2f} segundos")
        logger.info(f"Salida: {result.stdout}")
        
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error ejecutando {description}")
        logger.error(f"Código de salida: {e.returncode}")
        logger.error(f"Salida de error: {e.stderr}")
        return False

def create_all_indexes():
    """Crear todos los índices de optimización"""
    success = True
    success &= run_script("create_indexes.py", "Creación de índices para eventos")
    success &= run_script("create_chat_indexes.py", "Creación de índices para chat")
    
    if success:
        logger.info("✅ Todos los índices creados correctamente")
    else:
        logger.warning("⚠️ Algunos índices no pudieron ser creados")
    
    return success

def run_database_maintenance():
    """Ejecutar mantenimiento de base de datos"""
    logger.info("Ejecutando mantenimiento de base de datos...")
    
    try:
        # Ejecutar el script de mantenimiento con la opción --once
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, "maintenance.py", "--once"],
            check=True,
            capture_output=True,
            text=True
        )
        execution_time = time.time() - start_time
        
        logger.info(f"✅ Mantenimiento de base de datos completado en {execution_time:.2f} segundos")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error ejecutando mantenimiento de base de datos")
        logger.error(f"Código de salida: {e.returncode}")
        logger.error(f"Salida de error: {e.stderr}")
        return False

def main():
    """Función principal que ejecuta todas las optimizaciones"""
    logger.info("=== INICIO DE OPTIMIZACIÓN COMPLETA ===")
    start_time = time.time()
    
    # Crear todos los índices
    indexes_success = create_all_indexes()
    
    # Ejecutar mantenimiento de base de datos
    maintenance_success = run_database_maintenance()
    
    # Resumen final
    total_time = time.time() - start_time
    logger.info(f"=== FINALIZACIÓN DE OPTIMIZACIÓN COMPLETA ===")
    logger.info(f"Tiempo total de ejecución: {total_time:.2f} segundos")
    
    if indexes_success and maintenance_success:
        logger.info("✅ Todas las optimizaciones aplicadas correctamente")
        return 0
    else:
        logger.warning("⚠️ Algunas optimizaciones no se aplicaron correctamente")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 