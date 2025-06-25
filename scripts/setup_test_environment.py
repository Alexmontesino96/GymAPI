#!/usr/bin/env python3
"""
Script para configurar el entorno de prueba del sistema de chat.
Crea salas de chat y eventos necesarios para las pruebas.
"""

import sys
import os
from datetime import datetime, timedelta

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.user import User
from app.models.gym import Gym
from app.models.event import Event
from app.models.chat import ChatRoom, ChatMember
from app.services.chat import chat_service

def setup_test_environment():
    """Configura el entorno de prueba con datos reales."""
    db = SessionLocal()
    
    try:
        print("🚀 Configurando entorno de prueba...")
        
        # Datos reales del gimnasio
        gym_id = 1
        user_ids = [2, 4, 5, 6, 8]  # IDs reales de usuarios
        
        # Verificar que el gimnasio y usuarios existen
        gym = db.query(Gym).filter(Gym.id == gym_id).first()
        if not gym:
            print(f"❌ Gimnasio con ID {gym_id} no encontrado")
            return False
        
        existing_users = db.query(User).filter(User.id.in_(user_ids)).all()
        existing_user_ids = [user.id for user in existing_users]
        print(f"✅ Encontrados {len(existing_users)} usuarios: {existing_user_ids}")
        
        # 1. Crear evento de prueba si no existe
        test_event = db.query(Event).filter(
            Event.gym_id == gym_id,
            Event.title == "Evento de Prueba Chat"
        ).first()
        
        if not test_event:
            test_event = Event(
                title="Evento de Prueba Chat",
                description="Evento para probar el sistema de chat",
                gym_id=gym_id,
                start_time=datetime.utcnow() + timedelta(days=1),
                end_time=datetime.utcnow() + timedelta(days=1, hours=2),
                max_participants=20,
                creator_id=existing_user_ids[0] if existing_user_ids else 2
            )
            db.add(test_event)
            db.commit()
            db.refresh(test_event)
            print(f"✅ Evento de prueba creado: ID {test_event.id}")
        else:
            print(f"✅ Evento de prueba ya existe: ID {test_event.id}")
        
        # 2. Crear salas de chat de prueba
        test_channels = [
            "test_basic_123",
            "test_mentions_123", 
            "test_welcome_123",
            "test_commands_123",
            "test_stats_123",
            "test_system_123",
            "test_multi_users_123"
        ]
        
        created_rooms = 0
        for channel_id in test_channels:
            # Verificar si ya existe
            existing_room = db.query(ChatRoom).filter(
                ChatRoom.stream_channel_id == channel_id
            ).first()
            
            if not existing_room:
                # Crear sala de chat
                chat_room = ChatRoom(
                    stream_channel_id=channel_id,
                    stream_channel_type="messaging",
                    name=f"Sala {channel_id.replace('_', ' ').title()}",
                    event_id=test_event.id,
                    is_direct=False
                )
                db.add(chat_room)
                db.flush()  # Para obtener el ID
                
                # Agregar algunos miembros
                members_to_add = existing_user_ids[:3]  # Primeros 3 usuarios
                for user_id in members_to_add:
                    member = ChatMember(
                        room_id=chat_room.id,
                        user_id=user_id
                    )
                    db.add(member)
                
                created_rooms += 1
                print(f"✅ Sala creada: {channel_id} con {len(members_to_add)} miembros")
            else:
                print(f"⏭️  Sala ya existe: {channel_id}")
        
        # 3. Crear salas para pruebas de rendimiento
        for i in range(10):
            channel_id = f"perf_test_{i}"
            existing_room = db.query(ChatRoom).filter(
                ChatRoom.stream_channel_id == channel_id
            ).first()
            
            if not existing_room:
                chat_room = ChatRoom(
                    stream_channel_id=channel_id,
                    stream_channel_type="messaging", 
                    name=f"Sala Rendimiento {i}",
                    event_id=test_event.id,
                    is_direct=False
                )
                db.add(chat_room)
                db.flush()
                
                # Agregar un miembro aleatorio
                user_id = existing_user_ids[i % len(existing_user_ids)]
                member = ChatMember(
                    room_id=chat_room.id,
                    user_id=user_id
                )
                db.add(member)
                created_rooms += 1
        
        db.commit()
        
        print(f"\n🎉 Entorno configurado exitosamente!")
        print(f"   • Gimnasio: {gym.name} (ID: {gym_id})")
        print(f"   • Usuarios disponibles: {len(existing_users)}")
        print(f"   • Evento de prueba: {test_event.title} (ID: {test_event.id})")
        print(f"   • Salas de chat creadas: {created_rooms}")
        
        # 4. Mostrar estadísticas actuales
        total_rooms = db.query(ChatRoom).count()
        total_members = db.query(ChatMember).count()
        print(f"   • Total salas en BD: {total_rooms}")
        print(f"   • Total membresías: {total_members}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error configurando entorno: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()

def clean_test_environment():
    """Limpia el entorno de prueba (opcional)."""
    db = SessionLocal()
    
    try:
        print("🧹 Limpiando entorno de prueba...")
        
        # Eliminar salas de prueba
        test_patterns = ["test_", "perf_test_"]
        deleted_count = 0
        
        for pattern in test_patterns:
            rooms = db.query(ChatRoom).filter(
                ChatRoom.stream_channel_id.like(f"{pattern}%")
            ).all()
            
            for room in rooms:
                # Eliminar miembros primero
                db.query(ChatMember).filter(ChatMember.room_id == room.id).delete()
                # Eliminar sala
                db.delete(room)
                deleted_count += 1
        
        # Eliminar evento de prueba
        test_event = db.query(Event).filter(
            Event.title == "Evento de Prueba Chat"
        ).first()
        if test_event:
            db.delete(test_event)
            print("✅ Evento de prueba eliminado")
        
        db.commit()
        print(f"✅ {deleted_count} salas de prueba eliminadas")
        
        return True
        
    except Exception as e:
        print(f"❌ Error limpiando entorno: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Configurar entorno de prueba")
    parser.add_argument("--clean", action="store_true", help="Limpiar entorno de prueba")
    args = parser.parse_args()
    
    if args.clean:
        success = clean_test_environment()
    else:
        success = setup_test_environment()
    
    sys.exit(0 if success else 1) 