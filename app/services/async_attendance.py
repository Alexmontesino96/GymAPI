"""
AsyncAttendanceService - Servicio async para gestión de asistencia a clases.

Este módulo proporciona un servicio totalmente async para procesar check-in de usuarios
mediante códigos QR y registro de asistencia a clases.

Migrado en FASE 3 de la conversión sync → async.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import random
import string
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from redis.asyncio import Redis
import logging

from app.models.user import User
from app.models.schedule import ClassSession, ClassParticipation, ClassParticipationStatus
from app.models.user_gym import UserGym

logger = logging.getLogger(__name__)


class AsyncAttendanceService:
    """
    Servicio async para gestión de asistencia a clases mediante códigos QR.

    Todos los métodos son async y utilizan AsyncSession.

    Sistema de Check-in:
    - Códigos QR únicos por usuario (formato: U{user_id}_{hash})
    - Ventana de check-in: ±30 minutos de la hora de la clase
    - Auto-detección de clase más cercana o selección manual
    - Prevención de check-ins duplicados
    - Invalidación automática de cache después de check-in

    Métodos principales:
    - generate_qr_code() - Generar código QR único para usuario
    - process_check_in() - Procesar check-in con QR code
    """

    async def generate_qr_code(self, user_id: int) -> str:
        """
        Genera un código QR único para un usuario.

        Args:
            user_id: ID del usuario

        Returns:
            Código QR en formato: U{user_id}_{hash}

        Note:
            El hash es SHA256 de user_id + random_string (primeros 8 chars).
            Cada generación produce un código diferente.
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
        db: AsyncSession,
        qr_code: str,
        gym_id: int,
        redis_client: Optional[Redis] = None,
        session_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Procesa el check-in de un usuario usando su código QR.

        Args:
            db: Sesión async de base de datos
            qr_code: Código QR del usuario (formato U{user_id}_{hash})
            gym_id: ID del gimnasio actual
            redis_client: Cliente Redis opcional para cache
            session_id: ID de sesión específica (opcional)

        Returns:
            Dict con resultado del check-in:
            - success: bool
            - message: str
            - session: Dict con info de la clase (si success=True)

        Note:
            Ventana de check-in: ±30 minutos de la hora de inicio de la clase.
            Si no se especifica session_id, busca la clase más cercana.
            Previene check-ins duplicados automáticamente.
        """
        # Extraer user_id del código QR
        try:
            # El formato es U{user_id}_{hash}
            parts = qr_code.split('_')[0]  # Tomar la parte antes del _
            user_id = int(parts.replace('U', ''))

            # Verificar que el usuario pertenece al gimnasio actual
            result = await db.execute(
                select(UserGym).where(
                    and_(
                        UserGym.user_id == user_id,
                        UserGym.gym_id == gym_id,
                        UserGym.is_active == True
                    )
                )
            )
            membership = result.scalar_one_or_none()

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
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=30)
        window_end = now + timedelta(minutes=30)

        # Obtener sesiones próximas en el rango de fechas
        result = await db.execute(
            select(ClassSession).where(
                and_(
                    ClassSession.gym_id == gym_id,
                    ClassSession.start_time >= window_start,
                    ClassSession.start_time <= window_end,
                    ClassSession.is_cancelled == False
                )
            )
        )
        valid_sessions = result.scalars().all()

        # Si se especifica session_id, buscar esa sesión específica
        if session_id:
            result = await db.execute(
                select(ClassSession).where(
                    and_(
                        ClassSession.id == session_id,
                        ClassSession.gym_id == gym_id
                    )
                )
            )
            target_session = result.scalar_one_or_none()

            if not target_session:
                return {
                    "success": False,
                    "message": "Sesión no encontrada o no pertenece a este gimnasio"
                }

            # Validar que la sesión está dentro de la ventana de tiempo
            if not (window_start <= target_session.start_time <= window_end):
                return {
                    "success": False,
                    "message": "La sesión está fuera del horario de check-in (±30 minutos)"
                }
            closest_session = target_session
        else:
            # Comportamiento original: buscar sesión más cercana
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
        result = await db.execute(
            select(ClassParticipation).where(
                and_(
                    ClassParticipation.session_id == closest_session.id,
                    ClassParticipation.member_id == user_id,
                    ClassParticipation.gym_id == gym_id
                )
            )
        )
        existing_participation = result.scalar_one_or_none()

        if existing_participation:
            if existing_participation.status == ClassParticipationStatus.ATTENDED:
                return {
                    "success": False,
                    "message": "Ya has hecho check-in en esta clase"
                }
            # Actualizar estado a ATTENDED
            existing_participation.status = ClassParticipationStatus.ATTENDED
            existing_participation.attendance_time = now

            await db.commit()
            await db.refresh(existing_participation)

            # Invalidar caché después de actualizar asistencia
            if redis_client:
                try:
                    cache_key = f"last_attendance:{user_id}:{gym_id}"
                    await redis_client.delete(cache_key)
                    # También invalidar caché del dashboard summary
                    dashboard_cache_key = f"dashboard_summary:{user_id}:{gym_id}"
                    await redis_client.delete(dashboard_cache_key)
                except Exception as e:
                    # No fallar el check-in si la invalidación de caché falla
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
            new_participation = ClassParticipation(
                session_id=closest_session.id,
                member_id=user_id,
                status=ClassParticipationStatus.ATTENDED,
                gym_id=gym_id,
                attendance_time=now
            )

            db.add(new_participation)
            await db.commit()
            await db.refresh(new_participation)

            # Invalidar caché después de crear nueva asistencia
            if redis_client:
                try:
                    cache_key = f"last_attendance:{user_id}:{gym_id}"
                    await redis_client.delete(cache_key)
                    # También invalidar caché del dashboard summary
                    dashboard_cache_key = f"dashboard_summary:{user_id}:{gym_id}"
                    await redis_client.delete(dashboard_cache_key)
                except Exception as e:
                    # No fallar el check-in si la invalidación de caché falla
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


# Instancia singleton del servicio async
async_attendance_service = AsyncAttendanceService()
