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

class AttendanceService:
    async def generate_qr_code(self, user_id: int, gym_id: int) -> str:
        """
        Genera un código QR único para un usuario.
        El formato es: GYM{gym_id}U{user_id}_{hash}
        
        Args:
            user_id: ID del usuario
            gym_id: ID del gimnasio
            
        Returns:
            str: Código QR único
        """
        # Generar un string aleatorio para hacer el código más único
        random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        
        # Crear un hash usando user_id, gym_id y el string aleatorio
        hash_input = f"{user_id}_{gym_id}_{random_str}"
        hash_obj = hashlib.sha256(hash_input.encode())
        hash_short = hash_obj.hexdigest()[:8]
        
        # Formato final: GYM{gym_id}U{user_id}_{hash}
        return f"GYM{gym_id}U{user_id}_{hash_short}"

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
        # Extraer user_id y gym_id del código QR
        try:
            # El formato es GYM{gym_id}U{user_id}_{hash}
            parts = qr_code.split('_')[0]  # Tomar la parte antes del _
            gym_part = parts.split('U')[0]  # Separar la parte del gym
            user_part = parts.split('U')[1]  # Separar la parte del usuario
            
            qr_gym_id = int(gym_part.replace('GYM', ''))
            user_id = int(user_part)
            
            # Verificar que el código corresponde al gimnasio actual
            if qr_gym_id != gym_id:
                return {
                    "success": False,
                    "message": "Código QR no válido para este gimnasio"
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
        existing_participation = await class_participation_service.get_participation(
            db,
            session_id=closest_session.id,
            user_id=user_id
        )
        
        if existing_participation:
            if existing_participation.status == ClassParticipationStatus.CHECKED_IN:
                return {
                    "success": False,
                    "message": "Ya has hecho check-in en esta clase"
                }
            # Actualizar estado a CHECKED_IN
            existing_participation.status = ClassParticipationStatus.CHECKED_IN
            db.add(existing_participation)
            db.commit()
            db.refresh(existing_participation)
            
            return {
                "success": True,
                "message": "Check-in realizado correctamente",
                "session": {
                    "id": closest_session.id,
                    "name": closest_session.class_info.name,
                    "start_time": closest_session.start_time,
                    "end_time": closest_session.end_time
                }
            }
        else:
            # Crear nueva participación con estado CHECKED_IN
            participation = await class_participation_service.create_participation(
                db,
                session_id=closest_session.id,
                user_id=user_id,
                status=ClassParticipationStatus.CHECKED_IN,
                gym_id=gym_id
            )
            
            return {
                "success": True,
                "message": "Check-in realizado correctamente",
                "session": {
                    "id": closest_session.id,
                    "name": closest_session.class_info.name,
                    "start_time": closest_session.start_time,
                    "end_time": closest_session.end_time
                }
            }

# Instancia global del servicio
attendance_service = AttendanceService() 