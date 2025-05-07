v#!/usr/bin/env python3
"""
Script para eliminar un canal específico de Stream.io
"""

import sys
import os
import argparse
import logging
from typing import Dict, Any

# Añadir el directorio raíz al path para poder importar módulos de la aplicación
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar configuración y cliente de Stream
from app.core.config import get_settings
from app.core.stream_client import stream_client

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def delete_channel(channel_type: str, channel_id: str, hard_delete: bool = False) -> bool:
    """
    Elimina un canal específico de Stream.io
    
    Args:
        channel_type: Tipo del canal (ej: 'messaging')
        channel_id: ID del canal
        hard_delete: Si es True, elimina permanentemente los mensajes (actualmente no soportado)
        
    Returns:
        True si se eliminó correctamente, False en caso contrario
    """
    try:
        logger.info(f"Eliminando canal: {channel_type}:{channel_id}")
        
        # Obtener el canal
        channel = stream_client.channel(channel_type, channel_id)
        
        # Eliminar el canal
        # Nota: No estamos usando hard_delete porque la API no lo soporta
        if hard_delete:
            logger.info("Hard delete no soportado por la API, usando delete normal")
        
        response = channel.delete()
        
        logger.info(f"Canal eliminado exitosamente: {response}")
        return True
    except Exception as e:
        logger.error(f"Error al eliminar canal: {e}")
        return False

def delete_channel_by_cid(cid: str, hard_delete: bool = False) -> bool:
    """
    Elimina un canal utilizando su CID completo
    
    Args:
        cid: CID completo en formato 'tipo:id'
        hard_delete: Si es True, elimina permanentemente los mensajes
        
    Returns:
        True si se eliminó correctamente, False en caso contrario
    """
    try:
        # Separar el tipo y el ID del canal
        parts = cid.split(':')
        if len(parts) != 2:
            logger.error(f"Formato de CID inválido: {cid}. Debe ser 'tipo:id'")
            return False
        
        channel_type, channel_id = parts
        
        # Eliminar el canal
        return delete_channel(channel_type, channel_id, hard_delete)
    except Exception as e:
        logger.error(f"Error al eliminar canal por CID: {e}")
        return False

def main():
    """Función principal del script"""
    parser = argparse.ArgumentParser(description='Eliminar un canal específico de Stream.io')
    
    # Opciones para especificar el canal
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--channel-type', type=str, help='Tipo del canal (ej: messaging)')
    group.add_argument('--cid', type=str, help='CID completo del canal en formato tipo:id')
    
    # Si se especifica channel-type, también es necesario channel-id
    parser.add_argument('--channel-id', type=str, help='ID del canal (requerido con --channel-type)')
    
    # Opción hard-delete
    parser.add_argument('--hard-delete', action='store_true', help='Actualmente no soportado en la API')
    
    args = parser.parse_args()
    
    # Validar argumentos
    if args.channel_type and not args.channel_id:
        parser.error("Si se especifica --channel-type, también es necesario --channel-id")
    
    # Verificar credenciales
    settings = get_settings()
    logger.info(f"Conectando a Stream.io con API key: {settings.STREAM_API_KEY[:4]}***")
    
    # Ejecutar la eliminación
    success = False
    if args.cid:
        success = delete_channel_by_cid(args.cid, args.hard_delete)
    else:
        success = delete_channel(args.channel_type, args.channel_id, args.hard_delete)
    
    if success:
        print("Canal eliminado exitosamente")
    else:
        print("Error al eliminar el canal")
        sys.exit(1)

if __name__ == "__main__":
    main() 