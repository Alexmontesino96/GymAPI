from datetime import datetime, timedelta
import hashlib
import random
import string
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from redis.asyncio import Redis

from app.models.user import User
from app.models.schedule import ClassSession, ClassParticipation, ClassParticipationStatus
from app.services.schedule import class_participation_service, class_session_service
from app.services.gym import gym_service
from app.repositories.schedule import class_participation_repository

class AttendanceService:
    async def generate_qr_code(self, user_id: int) -> str:
        """
        Genera un código QR único para un usuario.
        El formato es: U{user_id}_{hash}
        
        Args:
            user_id: ID del usuario
            
        Returns:
            str: Código QR único
        """
        # Generar un string aleatorio para hacer el código más único
        random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        
        # Crear un hash usando user_id y el string aleatorio
        hash_input = f"{user_id}_{random_str}"
        hash_obj = hashlib.sha256(hash_input.encode())
        hash_short = hash_obj.hexdigest()[:8]
        
        # Formato final: U{user_id}_{hash}
        return f"U{user_id}_{hash_short}"

    async def process_check_in(
        self,
        db: Session,
        qr_code: str,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> Dict[str, Any]:
        """
        Procesa el check-in de un usuario usando su código QR.
        Busca una clase próxima y registra la asistencia si corresponde.
        
        Args:
            db: Sesión de base de datos
            qr_code: Código QR del usuario
            gym_id: ID del gimnasio actual
            redis_client: Cliente de Redis opcional para caché
            
        Returns:
            Dict con el resultado del check-in
        """
        # Extraer user_id del código QR
        try:
            # El formato es U{user_id}_{hash}
            parts = qr_code.split('_')[0]  # Tomar la parte antes del _
            user_id = int(parts.replace('U', ''))
            
            # Verificar que el usuario pertenece al gimnasio actual
            membership = gym_service.check_user_in_gym(db, user_id=user_id, gym_id=gym_id)
            if not membership:
                return {
                    "success": False,
                    "message": "Usuario no pertenece a este gimnasio"
                }
                
        except (ValueError, IndexError):
            return {
                "success": False,
                "message": "Código QR inválido"
            }

        # Buscar una clase próxima (±30 minutos desde ahora)
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=30)
        window_end = now + timedelta(minutes=30)
        
        # Obtener sesiones próximas
        upcoming_sessions = await class_session_service.get_sessions_by_date_range(
            db,
            start_date=window_start.date(),
            end_date=window_end.date(),
            gym_id=gym_id,
            redis_client=redis_client
        )
        
        # Filtrar sesiones dentro de la ventana de tiempo
        valid_sessions = [
            session for session in upcoming_sessions
            if window_start <= session.start_time <= window_end
        ]
        
        if not valid_sessions:
            return {
                "success": False,
                "message": "No hay clases disponibles para check-in en este momento"
            }
        
        # Tomar la sesión más cercana a la hora actual
        closest_session = min(
            valid_sessions,
            key=lambda s: abs((s.start_time - now).total_seconds())
        )
        
        # Verificar si el usuario ya tiene participación en esta sesión
        existing_participation = class_participation_repository.get_by_session_and_member(
            db,
            session_id=closest_session.id,
            member_id=user_id,
            gym_id=gym_id
        )
        
        if existing_participation:
            if existing_participation.status == ClassParticipationStatus.ATTENDED:
                return {
                    "success": False,
                    "message": "Ya has hecho check-in en esta clase"
                }
            # Actualizar estado a ATTENDED
            updated_participation = class_participation_repository.update(
                db, 
                db_obj=existing_participation,
                obj_in={
                    "status": ClassParticipationStatus.ATTENDED,
                    "attendance_time": now
                }
            )

            # Invalidar caché de last_attendance_date después de actualizar asistencia
            if redis_client:
                try:
                    cache_key = f"last_attendance:{user_id}:{gym_id}"
                    await redis_client.delete(cache_key)
                    # También invalidar caché del dashboard summary
                    dashboard_cache_key = f"dashboard_summary:{user_id}:{gym_id}"
                    await redis_client.delete(dashboard_cache_key)
                except Exception as e:
                    # No fallar el check-in si la invalidación de caché falla
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Error invalidando caché después de check-in: {e}")

            return {
                "success": True,
                "message": "Check-in realizado correctamente",
                "session": {
                    "id": closest_session.id,
                    "start_time": closest_session.start_time,
                    "end_time": closest_session.end_time
                }
            }
        else:
            # Crear nueva participación con estado ATTENDED
            participation_data = {
                "session_id": closest_session.id,
                "member_id": user_id,
                "status": ClassParticipationStatus.ATTENDED,
                "gym_id": gym_id,
                "attendance_time": now
            }
            
            new_participation = class_participation_repository.create(
                db,
                obj_in=participation_data
            )

            # Invalidar caché de last_attendance_date después de crear nueva asistencia
            if redis_client:
                try:
                    cache_key = f"last_attendance:{user_id}:{gym_id}"
                    await redis_client.delete(cache_key)
                    # También invalidar caché del dashboard summary
                    dashboard_cache_key = f"dashboard_summary:{user_id}:{gym_id}"
                    await redis_client.delete(dashboard_cache_key)
                except Exception as e:
                    # No fallar el check-in si la invalidación de caché falla
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Error invalidando caché después de check-in: {e}")

            return {
                "success": True,
                "message": "Check-in realizado correctamente",
                "session": {
                    "id": closest_session.id,
                    "start_time": closest_session.start_time,
                    "end_time": closest_session.end_time
                }
            }

# Instancia global del servicio
attendance_service = AttendanceService() 