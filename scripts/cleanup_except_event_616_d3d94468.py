#!/usr/bin/env python3
"""
Script para eliminar todos los canales de Stream Chat excepto event_616_d3d94468.

Este script elimina todos los canales de Stream Chat excepto el canal específico
'event_616_d3d94468' que debe ser preservado.

Uso:
    # Modo simulación (recomendado primero)
    python scripts/cleanup_except_event_616_d3d94468.py --dry-run
    
    # Eliminar canales reales (con confirmación)
    python scripts/cleanup_except_event_616_d3d94468.py
    
    # Eliminar sin confirmación (usar con precaución)
    python scripts/cleanup_except_event_616_d3d94468.py --force
"""

import sys
import os
import time
import argparse
import logging
from typing import List, Dict, Any

# Añadir el directorio raíz al path para poder importar módulos de la aplicación
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar configuración y cliente de Stream
from app.core.config import get_settings
from app.core.stream_client import stream_client

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def should_preserve_channel(channel_id: str, channel_name: str = "") -> bool:
    """
    Determina si un canal debe ser preservado.
    
    Args:
        channel_id: ID del canal en Stream
        channel_name: Nombre del canal (opcional)
        
    Returns:
        True si el canal debe preservarse, False si debe eliminarse
    """
    # Patrón específico a preservar
    preserve_pattern = "event_616_d3d94468"
    
    # Verificar en el ID del canal
    if preserve_pattern.lower() in channel_id.lower():
        return True
    
    # Verificar en el nombre del canal si está disponible
    if channel_name and preserve_pattern.lower() in channel_name.lower():
        return True
    
    return False

def get_all_channels(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Obtiene todos los canales de Stream.io
    
    Args:
        limit: Número máximo de canales a obtener por consulta
        offset: Índice desde donde comenzar la consulta
        
    Returns:
        Lista de canales encontrados
    """
    try:
        # Usar la API de Stream para obtener todos los canales
        response = stream_client.query_channels(
            filter_conditions={},
            sort=[{"field": "created_at", "direction": -1}],
            offset=offset,
            limit=limit
        )
        
        # Extraer información de canales de la respuesta
        result = []
        channels_data = response.get("channels", [])
        
        for channel_data in channels_data:
            # Extraer información del canal
            channel_info = channel_data.get("channel", {})
            
            # Obtener tipo, ID, CID y nombre del canal
            channel_type = channel_info.get("type")
            channel_id = channel_info.get("id")
            cid = channel_info.get("cid")
            name = channel_info.get("name", "")
            
            if channel_type and channel_id:
                result.append({
                    "type": channel_type,
                    "id": channel_id,
                    "cid": cid,
                    "name": name
                })
        
        return result
    except Exception as e:
        logger.error(f"Error al obtener canales: {e}")
        return []

def delete_channel(channel_type: str, channel_id: str) -> bool:
    """
    Elimina un canal específico completamente (mensajes + canal).
    
    Args:
        channel_type: Tipo del canal
        channel_id: ID del canal
        
    Returns:
        True si se eliminó correctamente, False en caso contrario
    """
    try:
        # Obtener referencia al canal
        channel = stream_client.channel(channel_type, channel_id)
        
        # Paso 1: Truncar el canal para eliminar todos los mensajes
        try:
            truncate_response = channel.truncate()
            logger.info(f"🧹 Canal {channel_type}:{channel_id} truncado (mensajes eliminados)")
        except Exception as truncate_error:
            # Si truncate falla, continuar con delete (podría ser un canal vacío)
            logger.warning(f"⚠️ No se pudo truncar {channel_type}:{channel_id}: {truncate_error}")
        
        # Paso 2: Eliminar el canal
        response = channel.delete()
        
        logger.info(f"✅ Canal {channel_type}:{channel_id} eliminado completamente")
        return True
    except Exception as e:
        logger.error(f"❌ Error al eliminar canal {channel_type}:{channel_id}: {e}")
        return False

def analyze_channels() -> Dict[str, Any]:
    """
    Analiza todos los canales para determinar cuáles preservar vs eliminar.
    
    Returns:
        Dict con información del análisis
    """
    logger.info("🔍 Consultando canales en Stream Chat...")
    
    offset = 0
    batch_size = 100
    all_channels = []
    
    # Obtener todos los canales
    while True:
        channels = get_all_channels(limit=batch_size, offset=offset)
        if not channels:
            break
        all_channels.extend(channels)
        offset += batch_size
        
        # Evitar bucle infinito
        if len(channels) < batch_size:
            break
    
    # Clasificar canales
    preserved_channels = []
    channels_to_delete = []
    
    for channel in all_channels:
        if should_preserve_channel(channel["id"], channel.get("name", "")):
            preserved_channels.append(channel)
        else:
            channels_to_delete.append(channel)
    
    return {
        "total_channels": len(all_channels),
        "preserved_channels": preserved_channels,
        "channels_to_delete": channels_to_delete
    }

def cleanup_channels(dry_run: bool = True, force: bool = False, quiet: bool = False) -> None:
    """
    Elimina canales excepto los preservados.
    
    Args:
        dry_run: Si es True, solo muestra los canales sin eliminarlos
        force: Si es True, elimina sin solicitar confirmación
        quiet: Si es True, reduce la cantidad de mensajes de log
    """
    analysis = analyze_channels()
    
    total_channels = analysis["total_channels"]
    preserved_channels = analysis["preserved_channels"]
    channels_to_delete = analysis["channels_to_delete"]
    
    if not quiet:
        logger.info(f"📊 Total de canales encontrados: {total_channels}")
        
        if preserved_channels:
            logger.info(f"\n🛡️ Canales a PRESERVAR: {len(preserved_channels)}")
            for channel in preserved_channels:
                logger.info(f"  ✅ {channel['cid']} ({channel.get('name', 'Sin nombre')})")
        
        logger.info(f"\n💥 Canales a ELIMINAR: {len(channels_to_delete)}")
        
        if not quiet and len(channels_to_delete) > 0:
            # Mostrar algunos ejemplos
            for i, channel in enumerate(channels_to_delete[:5]):
                logger.info(f"  ❌ {channel['cid']} ({channel.get('name', 'Sin nombre')})")
            
            if len(channels_to_delete) > 5:
                logger.info(f"  ... y {len(channels_to_delete) - 5} canales más")
    
    if len(channels_to_delete) == 0:
        logger.info("✨ No hay canales para eliminar.")
        return
    
    if dry_run:
        logger.info(f"\n🔍 MODO SIMULACIÓN: Se eliminarían {len(channels_to_delete)} canales")
        logger.info("Ejecuta sin --dry-run para eliminar realmente")
        return
    
    # Solicitar confirmación si no es force
    if not force:
        logger.warning(f"\n⚠️  ¡ADVERTENCIA! Se eliminarán {len(channels_to_delete)} canales PERMANENTEMENTE.")
        logger.warning("Esta acción NO se puede deshacer.")
        
        if preserved_channels:
            logger.info(f"Se preservarán {len(preserved_channels)} canales específicos.")
        
        confirmation = input(f"\n¿Continuar con la eliminación de {len(channels_to_delete)} canales? Escriba 'CONFIRMAR': ")
        
        if confirmation != "CONFIRMAR":
            logger.info("❌ Operación cancelada.")
            return
    
    # Proceder con la eliminación
    logger.info(f"\n🗑️ Iniciando eliminación de {len(channels_to_delete)} canales...")
    
    deleted_count = 0
    failed_count = 0
    
    for i, channel in enumerate(channels_to_delete):
        try:
            if not quiet:
                logger.info(f"Eliminando {i+1}/{len(channels_to_delete)}: {channel['cid']}")
            
            success = delete_channel(channel["type"], channel["id"])
            
            if success:
                deleted_count += 1
            else:
                failed_count += 1
            
            # Pequeña pausa para no sobrecargar la API
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error procesando canal {channel['cid']}: {e}")
            failed_count += 1
    
    # Resumen final
    logger.info(f"\n📊 RESUMEN FINAL:")
    logger.info(f"  ✅ Canales eliminados: {deleted_count}")
    logger.info(f"  ❌ Fallos: {failed_count}")
    logger.info(f"  🛡️ Canales preservados: {len(preserved_channels)}")
    
    if preserved_channels:
        logger.info(f"\n🔒 Canales preservados:")
        for channel in preserved_channels:
            logger.info(f"  ✅ {channel['cid']}")

def main():
    """Función principal del script"""
    parser = argparse.ArgumentParser(
        description='Eliminar todos los canales de Stream Chat excepto event_616_d3d94468'
    )
    parser.add_argument(
        '--dry-run', 
        action='store_true', 
        help='Simular la eliminación sin realizarla (recomendado primero)'
    )
    parser.add_argument(
        '--force', 
        action='store_true', 
        help='Eliminar sin solicitar confirmación'
    )
    parser.add_argument(
        '--quiet', 
        action='store_true', 
        help='Reducir la cantidad de mensajes de log'
    )
    
    args = parser.parse_args()
    
    # Verificar credenciales
    settings = get_settings()
    if not args.quiet:
        logger.info(f"🔗 Conectando a Stream.io con API key: {settings.STREAM_API_KEY[:4]}***")
    
    try:
        cleanup_channels(
            dry_run=args.dry_run,
            force=args.force,
            quiet=args.quiet
        )
    except KeyboardInterrupt:
        logger.info("\n❌ Operación interrumpida por el usuario")
    except Exception as e:
        logger.error(f"❌ Error durante la operación: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()