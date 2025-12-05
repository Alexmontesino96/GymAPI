"""
AsyncAttendanceService - Servicio async para gestión de asistencia con QR.

Este módulo maneja check-ins de usuarios mediante códigos QR y registro de
asistencia a clases dentro de ventanas de tiempo.

Migrado en FASE 3 de la conversión sync → async.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import random
import string
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis
import logging

from app.models.user_gym import UserGym
from app.models.schedule import ClassParticipationStatus
from app.services.schedule import class_session_service
from app.repositories.async_schedule import async_class_participation_repository

logger = logging.getLogger("async_attendance_service")


class AsyncAttendanceService:
    """
    Servicio async para gestión de asistencia con códigos QR.

    Todos los métodos son async y utilizan AsyncSession.

    Funcionalidades:
    - Generación de códigos QR únicos por usuario
    - Procesamiento de check-ins con ventana de tiempo (±30 min)
    - Registro automático de asistencia
    - Invalidación de caché de dashboard
    - Búsqueda de sesiones próximas

    Métodos principales:
    - generate_qr_code() - Genera QR único (formato U{user_id}_{hash})
    - process_check_in() - Procesa check-in con QR
    """

    async def generate_qr_code(self, user_id: int) -> str:
        """
        Genera un código QR único para un usuario.

        Args:
            user_id: ID del usuario

        Returns:
            str: Código QR único en formato U{user_id}_{hash}

        Note:
            - Hash de 8 caracteres generado con SHA256
            - Incluye string aleatorio de 6 chars para unicidad
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

        Busca una clase próxima y registra la asistencia si corresponde.

        Args:
            db: Sesión async de base de datos
            qr_code: Código QR del usuario (formato U{user_id}_{hash})
            gym_id: ID del gimnasio actual
            redis_client: Cliente de Redis opcional para caché
            session_id: ID de sesión específica (opcional)

        Returns:
            Dict con el resultado del check-in:
            - success: bool
            - message: str
            - session: Optional[Dict] con id, start_time, end_time

        Note:
            - Ventana de check-in: ±30 minutos desde ahora
            - Si session_id se proporciona, valida que esté en la ventana
            - Invalida caché de last_attendance y dashboard_summary
            - Si ya existe participación, actualiza a ATTENDED
            - Si no existe, crea nueva con ATTENDED
        """
        # Extraer user_id del código QR
        try:
            # El formato es U{user_id}_{hash}
            parts = qr_code.split('_')[0]  # Tomar la parte antes del _
            user_id = int(parts.replace('U', ''))

            # Verificar que el usuario pertenece al gimnasio actual (async)
            result = await db.execute(
                select(UserGym).where(
                    UserGym.user_id == user_id,
                    UserGym.gym_id == gym_id
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

        # Obtener sesiones próximas (async)
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

        # Si se especifica session_id, buscar esa sesión específica
        if session_id:
            target_session = await class_session_service.get_session(
                db, session_id=session_id, gym_id=gym_id, redis_client=redis_client
            )
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

        # Verificar si el usuario ya tiene participación en esta sesión (async)
        existing_participation = await async_class_participation_repository.get_by_session_and_member(
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
            # Actualizar estado a ATTENDED (async)
            updated_participation = await async_class_participation_repository.update(
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
            # Crear nueva participación con estado ATTENDED (async)
            participation_data = {
                "session_id": closest_session.id,
                "member_id": user_id,
                "status": ClassParticipationStatus.ATTENDED,
                "gym_id": gym_id,
                "attendance_time": now
            }

            new_participation = await async_class_participation_repository.create(
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
