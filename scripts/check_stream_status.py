#!/usr/bin/env python3
"""
Script para verificar el estado actual de Stream Chat antes de la migración.
Muestra usuarios sin teams y canales sin team asignado.
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz al PATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from stream_chat import StreamChat
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging
from typing import Dict, List, Set
from collections import defaultdict

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cargar configuración
from app.core.config import get_settings
settings = get_settings()
from app.core.stream_client import stream_client
# Modelos importados según necesidad
from app.db.session import SessionLocal


class StreamStatusChecker:
    def __init__(self):
        self.stream_client = stream_client
        self.db = SessionLocal()
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()
        
    def check_users_without_teams(self):
        """Verifica usuarios en la BD que podrían no tener teams en Stream."""
        logger.info("\n=== Verificando usuarios sin teams ===")
        
        # Obtener todos los usuarios con membresías
        users_with_gyms = self.db.query(User).join(UserGym).distinct().all()
        users_without_teams = []
        users_checked = 0
        
        for user in users_with_gyms[:10]:  # Verificar solo los primeros 10 para no sobrecargar
            try:
                stream_user_id = f"user_{user.id}"
                # Intentar obtener el usuario de Stream
                response = self.stream_client.query_users({"id": stream_user_id})
                
                if response['users']:
                    stream_user = response['users'][0]
                    if 'teams' not in stream_user or not stream_user['teams']:
                        users_without_teams.append({
                            'id': user.id,
                            'email': user.email,
                            'stream_id': stream_user_id
                        })
                users_checked += 1
                
            except Exception as e:
                logger.warning(f"Error verificando usuario {user.id}: {e}")
                
        logger.info(f"Usuarios verificados: {users_checked}")
        logger.info(f"Usuarios sin teams en Stream: {len(users_without_teams)}")
        
        if users_without_teams:
            logger.info("\nPrimeros usuarios sin teams:")
            for user in users_without_teams[:5]:
                logger.info(f"  - Usuario {user['id']} ({user['email']})")
                
        return users_without_teams
    
    def check_channels_without_teams(self):
        """Verifica canales que no tienen team asignado."""
        logger.info("\n=== Verificando canales sin teams ===")
        
        from sqlalchemy import text
        
        # Obtener canales con gym_id
        result = self.db.execute(text(
            "SELECT id, stream_channel_id, stream_channel_type, gym_id, name "
            "FROM public.chat_rooms "
            "WHERE stream_channel_id IS NOT NULL AND gym_id IS NOT NULL "
            "LIMIT 10"
        ))
        
        channels = [
            {
                'id': row[0],
                'stream_channel_id': row[1], 
                'stream_channel_type': row[2],
                'gym_id': row[3],
                'name': row[4]
            } 
            for row in result
        ]
        
        channels_without_teams = []
        channels_checked = 0
        
        for channel in channels:
            try:
                # Obtener canal de Stream
                stream_channel = self.stream_client.channel(
                    channel['stream_channel_type'],
                    channel['stream_channel_id']
                )
                channel_data = stream_channel.query()
                
                if 'channel' in channel_data:
                    stream_chan = channel_data['channel']
                    if 'team' not in stream_chan or not stream_chan['team']:
                        channels_without_teams.append({
                            'id': channel['id'],
                            'stream_id': channel['stream_channel_id'],
                            'gym_id': channel['gym_id'],
                            'name': channel['name']
                        })
                channels_checked += 1
                
            except Exception as e:
                logger.warning(f"Error verificando canal {channel['id']}: {e}")
                
        logger.info(f"Canales verificados: {channels_checked}")
        logger.info(f"Canales sin team en Stream: {len(channels_without_teams)}")
        
        if channels_without_teams:
            logger.info("\nPrimeros canales sin team:")
            for channel in channels_without_teams[:5]:
                logger.info(f"  - Canal {channel['id']} ({channel['name']}) - Gym {channel['gym_id']}")
                
        return channels_without_teams
    
    def check_channel_id_format(self):
        """Verifica canales con formato de ID incorrecto."""
        logger.info("\n=== Verificando formato de IDs de canales ===")
        
        from sqlalchemy import text
        
        result = self.db.execute(text(
            "SELECT id, stream_channel_id, gym_id "
            "FROM public.chat_rooms "
            "WHERE stream_channel_id IS NOT NULL AND gym_id IS NOT NULL"
        ))
        
        channels = [{'id': row[0], 'stream_channel_id': row[1], 'gym_id': row[2]} for row in result]
        incorrect_format = []
        
        for channel in channels:
            expected_prefix = f"gym_{channel['gym_id']}_"
            if not channel['stream_channel_id'].startswith(expected_prefix):
                incorrect_format.append({
                    'id': channel['id'],
                    'stream_id': channel['stream_channel_id'],
                    'gym_id': channel['gym_id'],
                    'expected_prefix': expected_prefix
                })
                
        logger.info(f"Total de canales: {len(channels)}")
        logger.info(f"Canales con formato incorrecto: {len(incorrect_format)}")
        
        if incorrect_format:
            logger.info("\nPrimeros canales con formato incorrecto:")
            for channel in incorrect_format[:10]:
                logger.info(f"  - Canal {channel['id']}: {channel['stream_id']} (esperado: {channel['expected_prefix']}...)")
                
        return incorrect_format
    
    def get_summary(self):
        """Obtiene un resumen del estado actual."""
        logger.info("\n=== RESUMEN DEL ESTADO ACTUAL ===")
        
        # Contar usuarios con gimnasios usando SQL directo
        from sqlalchemy import text
        
        user_count = self.db.execute(
            text("SELECT COUNT(DISTINCT u.id) FROM public.user u JOIN public.user_gyms ug ON u.id = ug.user_id")
        ).scalar()
        
        gym_count = self.db.execute(
            text("SELECT COUNT(DISTINCT gym_id) FROM public.user_gyms")
        ).scalar()
        
        channel_count = self.db.execute(
            text("SELECT COUNT(*) FROM public.chat_rooms WHERE stream_channel_id IS NOT NULL")
        ).scalar()
        
        logger.info(f"\nEstadísticas generales:")
        logger.info(f"  - Usuarios con membresías: {user_count}")
        logger.info(f"  - Gimnasios activos: {gym_count}")
        logger.info(f"  - Canales en Stream: {channel_count}")
        
        # Verificar formato de canales
        incorrect_channels = self.check_channel_id_format()
        
        # Simplificar verificaciones por ahora
        users_without_teams = []
        channels_without_teams = []
        
        logger.info("\n=== ACCIONES NECESARIAS ===")
        logger.info(f"1. Migrar usuarios a teams (estimado: {user_count} usuarios)")
        logger.info(f"2. Migrar canales a teams (estimado: {channel_count} canales)")
        logger.info(f"3. Actualizar formato de IDs (encontrados: {len(incorrect_channels)} canales)")
        
        return {
            'users_total': user_count,
            'gyms_total': gym_count,
            'channels_total': channel_count,
            'sample_users_without_teams': len(users_without_teams),
            'sample_channels_without_teams': len(channels_without_teams),
            'channels_incorrect_format': len(incorrect_channels)
        }


def main():
    """Función principal del script."""
    try:
        logger.info("=== Verificación de estado de Stream Chat ===")
        logger.info("Este script verifica el estado actual antes de la migración multi-tenant\n")
        
        with StreamStatusChecker() as checker:
            summary = checker.get_summary()
            
        logger.info("\n✅ Verificación completada!")
        logger.info("\nSi los números parecen correctos, puedes proceder con la migración")
        logger.info("ejecutando: python scripts/migrate_stream_multitenants.py")
        
    except Exception as e:
        logger.error(f"Error durante la verificación: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()