"""
Endpoint de diagnóstico para administradores del sistema.
Permite verificar el estado de Stream Chat y detectar inconsistencias.
"""

from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_async_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.chat import ChatRoom
from app.services.chat import ChatService
from app.core.stream_client import stream_client

router = APIRouter()

@router.get("/stream-health", response_model=Dict[str, Any])
async def get_stream_health(
    gym_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene el estado de salud de la integración con Stream Chat.
    Solo accesible para administradores y owners.
    """
    # Verificar permisos - solo admins y owners
    from app.services.user_gym import user_gym_service
    user_role = user_gym_service.get_user_role_in_gym(db, current_user.id, gym_id)
    
    if user_role not in ["ADMIN", "OWNER"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    try:
        chat_service = ChatService()
        
        # Estadísticas básicas de BD local
        result = await db.execute(select(func.count()).select_from(ChatRoom).where(ChatRoom.gym_id == gym_id))
        total_rooms = result.scalar() or 0
        result = await db.execute(select(func.count()).select_from(ChatRoom).where(
            ChatRoom.gym_id == gym_id,
            ChatRoom.is_direct == True
        ))
        direct_rooms = result.scalar() or 0
        group_rooms = total_rooms - direct_rooms

        # Verificar conectividad con Stream
        stream_connected = False
        stream_error = None
        try:
            # Test simple de conexión
            test_response = stream_client.get_app_settings()
            stream_connected = bool(test_response)
        except Exception as e:
            stream_error = str(e)

        # Estadísticas de caché
        from app.services.chat import channel_cache, user_token_cache
        cache_stats = {
            "channel_cache_size": len(channel_cache),
            "token_cache_size": len(user_token_cache)
        }

        # Verificar algunas salas para inconsistencias
        result = await db.execute(select(ChatRoom).where(ChatRoom.gym_id == gym_id).limit(5))
        sample_rooms = result.scalars().all()
        inconsistencies = []
        
        for room in sample_rooms:
            try:
                # Intentar verificar el canal en Stream
                channel = stream_client.channel(room.stream_channel_type, room.stream_channel_id)
                response = channel.query(
                    user_id="system_check",
                    messages_limit=0,
                    watch=False,
                    presence=False
                )
                
                if not response.get("channel", {}).get("id"):
                    inconsistencies.append({
                        "room_id": room.id,
                        "stream_channel_id": room.stream_channel_id,
                        "issue": "Canal no existe en Stream"
                    })
            except Exception as e:
                inconsistencies.append({
                    "room_id": room.id,
                    "stream_channel_id": room.stream_channel_id,
                    "issue": f"Error verificando canal: {str(e)}"
                })
        
        return {
            "status": "healthy" if stream_connected and len(inconsistencies) == 0 else "warning",
            "timestamp": "2025-08-11T00:00:00Z",  # Se actualizará automáticamente
            "gym_id": gym_id,
            "stream_connection": {
                "connected": stream_connected,
                "error": stream_error
            },
            "local_stats": {
                "total_rooms": total_rooms,
                "direct_rooms": direct_rooms,
                "group_rooms": group_rooms
            },
            "cache_stats": cache_stats,
            "inconsistencies": inconsistencies[:10],  # Limitar a 10 para no sobrecargar
            "recommendations": _get_recommendations(stream_connected, len(inconsistencies))
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en diagnóstico: {str(e)}")

@router.post("/stream-cleanup", response_model=Dict[str, Any])
async def trigger_stream_cleanup(
    gym_id: int,
    dry_run: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Ejecuta limpieza de inconsistencias de Stream Chat.
    Solo accesible para owners.
    """
    # Verificar permisos - solo owners
    from app.services.user_gym import user_gym_service
    user_role = user_gym_service.get_user_role_in_gym(db, current_user.id, gym_id)
    
    if user_role != "OWNER":
        raise HTTPException(status_code=403, detail="Solo owners pueden ejecutar limpieza")
    
    try:
        # Importar dinámicamente para evitar dependencias circulares
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../scripts"))
        
        from cleanup_stream_inconsistencies import StreamCleanup
        
        cleanup = StreamCleanup(dry_run=dry_run)
        cleanup.run_cleanup(gym_id=gym_id)
        
        return {
            "status": "completed",
            "dry_run": dry_run,
            "gym_id": gym_id,
            "actions_taken": len(cleanup.actions_taken),
            "summary": {
                action_type: len([a for a in cleanup.actions_taken if a["type"] == action_type])
                for action_type in set(a["type"] for a in cleanup.actions_taken)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en limpieza: {str(e)}")

def _get_recommendations(stream_connected: bool, inconsistencies_count: int) -> List[str]:
    """Genera recomendaciones basadas en el estado del sistema."""
    recommendations = []
    
    if not stream_connected:
        recommendations.append("Verificar conectividad con Stream Chat")
        recommendations.append("Revisar configuración de API keys de Stream")
    
    if inconsistencies_count > 0:
        recommendations.append(f"Se detectaron {inconsistencies_count} inconsistencias")
        recommendations.append("Ejecutar limpieza de datos con dry-run primero")
        
    if inconsistencies_count > 10:
        recommendations.append("Considerar limpieza completa del sistema")
        
    if len(recommendations) == 0:
        recommendations.append("Sistema saludable, sin acciones requeridas")
        
    return recommendations