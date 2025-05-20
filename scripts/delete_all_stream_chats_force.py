#!/usr/bin/env python3
"""
Script para eliminar todos los canales de chat en Stream.io SIN SOLICITAR CONFIRMACIÓN

Este script se conecta a Stream.io usando las credenciales de la aplicación
y elimina todos los canales de chat existentes.

ADVERTENCIA: Este script eliminará PERMANENTEMENTE todos los canales de chat
y sus mensajes sin solicitar confirmación. Solo debe usarse en entornos de prueba
o para ejecuciones automatizadas donde se tenga absoluta certeza de la operación.
Esta acción NO se puede deshacer.
"""

import sys
import os
import time
import argparse
import logging
import json
from typing import List, Dict, Any, Optional

# Añadir el directorio raíz al path para poder importar módulos de la aplicación
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar configuración y cliente de Stream
from app.core.config import get_settings
from app.core.stream_client import stream_client

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_all_channels(limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    """
    Obtiene todos los canales de Stream usando la API de consulta.
    
    Args:
        limit: Número máximo de canales a obtener por solicitud
        offset: Índice desde donde comenzar la consulta
        
    Returns:
        Respuesta de la API con la lista de canales
    """
    try:
        # Usar la API de Stream para obtener todos los canales
        response = stream_client.query_channels(
            filter_conditions={},
            sort=[{"field": "created_at", "direction": -1}],
            offset=offset,
            limit=limit
        )
        
        return response
    except Exception as e:
        logger.error(f"Error al obtener canales: {str(e)}")
        raise

def delete_multiple_channels(channel_cids: List[str], hard_delete: bool = False) -> Dict[str, Any]:
    """
    Elimina múltiples canales en una sola operación.
    
    Args:
        channel_cids: Lista de CIDs de canales (formato: 'tipo:id')
        hard_delete: Si es True, elimina permanentemente; si es False, hace un soft delete
        
    Returns:
        Respuesta de la API con el ID de la tarea asíncrona
    """
    try:
        # Usar la API de Stream para eliminar múltiples canales
        response = stream_client.delete_channels(channel_cids, hard_delete=hard_delete)
        
        logger.info(f"Solicitud de eliminación enviada para {len(channel_cids)} canales. ID de tarea: {response.get('task_id')}")
        return response
    except Exception as e:
        logger.error(f"Error al eliminar múltiples canales: {str(e)}")
        raise

def check_task_status(task_id: str) -> Dict[str, Any]:
    """
    Verifica el estado de una tarea asíncrona.
    
    Args:
        task_id: ID de la tarea a verificar
        
    Returns:
        Información sobre el estado de la tarea
    """
    try:
        # Obtener el estado actual de la tarea
        response = stream_client.get_task(task_id)
        
        logger.info(f"Estado de la tarea {task_id}: {response.get('status')}")
        return response
    except Exception as e:
        logger.error(f"Error al verificar estado de tarea {task_id}: {str(e)}")
        raise

def delete_all_channels(batch_size: int = 25, hard_delete: bool = False, dry_run: bool = True, quiet: bool = False) -> None:
    """
    Elimina todos los canales de Stream en lotes.
    
    Args:
        batch_size: Número de canales a eliminar por lote
        hard_delete: Si es True, elimina permanentemente; si es False, hace un soft delete
        dry_run: Si es True, solo muestra los canales que se eliminarían sin hacerlo realmente
        quiet: Si es True, reduce la cantidad de mensajes de logging
    """
    offset = 0
    total_deleted = 0
    deletion_mode = "HARD DELETE" if hard_delete else "SOFT DELETE"
    
    if not quiet:
        logger.info(f"Iniciando eliminación de canales en modo {'SIMULACIÓN' if dry_run else deletion_mode}")
    
    while True:
        # Obtener un lote de canales
        try:
            response = get_all_channels(limit=batch_size, offset=offset)
            channels = response.get("channels", [])
            
            # Si no hay más canales, terminar
            if not channels:
                if not quiet:
                    logger.info(f"No se encontraron más canales. Total eliminados: {total_deleted}")
                break
            
            # Crear lista de CIDs para eliminación en lote
            channel_cids = []
            for channel in channels:
                cid = channel.get("id") if "id" in channel else f"{channel.get('type')}:{channel.get('id')}"
                channel_type = channel.get("type")
                channel_id = channel.get("id").split(":")[-1] if ":" in channel.get("id", "") else channel.get("id")
                
                if ":" not in cid:
                    cid = f"{channel_type}:{channel_id}"
                
                channel_cids.append(cid)
                if not quiet:
                    logger.info(f"Canal encontrado: {cid}")
            
            if not quiet:
                logger.info(f"Lote de {len(channel_cids)} canales listos para eliminar (offset: {offset})")
            
            # Si no es dry_run, proceder con la eliminación
            if not dry_run:
                # Eliminar canales en lote
                if channel_cids:
                    response = delete_multiple_channels(channel_cids, hard_delete=hard_delete)
                    task_id = response.get("task_id")
                    
                    # Esperar a que la tarea termine (con timeout)
                    max_retries = 10
                    retry_count = 0
                    
                    while retry_count < max_retries:
                        task_status = check_task_status(task_id)
                        status = task_status.get("status")
                        
                        if status == "completed":
                            if not quiet:
                                logger.info(f"Tarea {task_id} completada exitosamente")
                            break
                        elif status == "failed":
                            logger.error(f"Tarea {task_id} falló: {task_status.get('error')}")
                            break
                        
                        retry_count += 1
                        if not quiet:
                            logger.info(f"Esperando finalización de tarea {task_id} ({retry_count}/{max_retries})...")
                        time.sleep(3)  # Esperar 3 segundos entre verificaciones
                    
                    total_deleted += len(channel_cids)
            else:
                if not quiet:
                    logger.info(f"[SIMULACIÓN] Se eliminarían {len(channel_cids)} canales")
                total_deleted += len(channel_cids)
            
            # Avanzar al siguiente lote
            offset += batch_size
            
        except Exception as e:
            logger.error(f"Error durante la eliminación de canales: {str(e)}")
            break
    
    logger.info(f"Proceso completado. Total de canales {'que se eliminarían' if dry_run else 'eliminados'}: {total_deleted}")

def main():
    """Función principal del script"""
    parser = argparse.ArgumentParser(description='Eliminar todos los canales de chat en Stream.io SIN SOLICITAR CONFIRMACIÓN')
    parser.add_argument('--batch-size', type=int, default=25, help='Número de canales a eliminar por lote')
    parser.add_argument('--hard-delete', action='store_true', help='Eliminar permanentemente los canales y sus mensajes')
    parser.add_argument('--dry-run', action='store_true', help='Simular la eliminación sin realizarla realmente')
    parser.add_argument('--quiet', action='store_true', help='Reducir la cantidad de mensajes de logging')
    args = parser.parse_args()
    
    # Ajustar nivel de logging si se solicita modo silencioso
    if args.quiet:
        logger.setLevel(logging.WARNING)
    
    try:
        # Verificar credenciales
        settings = get_settings()
        if not args.quiet:
            logger.info(f"Conectando a Stream.io con API key: {settings.STREAM_API_KEY[:4]}***")
        
        # Advertencia final en modo no simulado
        if not args.dry_run:
            logger.warning("ADVERTENCIA: Ejecutando eliminación SIN CONFIRMACIÓN")
            logger.warning(f"Modo de eliminación: {'PERMANENTE (Hard Delete)' if args.hard_delete else 'TEMPORAL (Soft Delete)'}")
        
        # Proceder con la eliminación
        delete_all_channels(
            batch_size=args.batch_size,
            hard_delete=args.hard_delete,
            dry_run=args.dry_run,
            quiet=args.quiet
        )
        
    except Exception as e:
        logger.error(f"Error durante la ejecución: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 