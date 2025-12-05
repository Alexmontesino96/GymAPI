from typing import List, Optional, Dict, Any, Union
from datetime import datetime, time, timedelta, date
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
import asyncio
import json

from app.repositories.async_schedule import (
    async_gym_hours_repository,
    async_gym_special_hours_repository,
    async_class_repository,
    async_class_session_repository,
    async_class_participation_repository,
    async_class_category_repository
)
from app.models.schedule import (
    ClassSessionStatus,
    ClassParticipationStatus,
    DayOfWeek,
    Class,
    GymSpecialHours,
    ClassCategoryCustom,
    ClassParticipation,
    ClassSession,
)
from app.schemas.schedule import (
    GymHoursCreate,
    GymHoursUpdate,
    GymSpecialHoursCreate,
    GymSpecialHoursUpdate,
    ClassCreate,
    ClassUpdate,
    ClassSessionCreate,
    ClassSessionUpdate,
    ClassParticipationCreate,
    ClassParticipationUpdate,
    ClassCategoryCustomCreate,
    ClassCategoryCustomUpdate,
    GymHours,
    GymSpecialHours as GymSpecialHoursSchema
)

# --- Añadir importaciones para Caché ---
import logging
from redis.asyncio import Redis
from app.services.cache_service import cache_service
from app.schemas.schedule import ClassCategoryCustom as ClassCategoryCustomSchema
from app.schemas.schedule import Class as ClassSchema
from app.schemas.schedule import ClassSession as ClassSessionSchema
from app.schemas.schedule import ClassParticipation as ClassParticipationSchema
from app.core.timezone_utils import is_session_in_future, get_current_time_in_gym_timezone, populate_session_timezone_fields
# --- Fin importaciones Caché ---

# --- Añadir logger ---
logger = logging.getLogger("async_schedule_service")
# --- Fin Logger ---

async def populate_sessions_with_timezone(sessions: List[Any], gym_id: int, db: AsyncSession) -> List[dict]:
    """
    Puebla los campos timezone para una lista de sesiones.

    Args:
        sessions: Lista de sesiones (modelos SQLAlchemy o esquemas Pydantic)
        gym_id: ID del gimnasio
        db: Sesión de base de datos async

    Returns:
        Lista de diccionarios con campos timezone poblados
    """
    if not sessions:
        return []

    # Obtener timezone del gimnasio
    from app.repositories.async_gym import async_gym_repository
    gym = await async_gym_repository.get_async(db, id=gym_id)
    if not gym or not gym.timezone:
        # Si no hay timezone definido, usar UTC como fallback
        gym_timezone = "UTC"
    else:
        gym_timezone = gym.timezone

    result = []
    for session in sessions:
        # Convertir a diccionario si es un modelo SQLAlchemy
        if hasattr(session, '__dict__'):
            from app.schemas.schedule import ClassSession
            session_dict = ClassSession.model_validate(session).model_dump()
        else:
            session_dict = session.model_dump() if hasattr(session, 'model_dump') else session

        # Poblar campos timezone
        session_with_tz = populate_session_timezone_fields(session_dict, gym_timezone)
        result.append(session_with_tz)

    return result


class AsyncGymHoursService:
    # --- Añadir método helper para invalidación de caché ---
    async def _invalidate_gym_hours_cache(self, redis_client: Redis, gym_id: int, day: Optional[int] = None, date_value: Optional[date] = None):
        """
        Invalida la caché de horarios de gimnasio.

        Args:
            redis_client: Cliente Redis
            gym_id: ID del gimnasio
            day: Día específico a invalidar (opcional)
            date_value: Fecha específica a invalidar (opcional)
        """
        if not redis_client:
            return

        tracking_set_key = f"cache_keys:gym_hours:{gym_id}"
        keys_to_delete = []

        try:
            # Invalidar clave específica de día si se proporciona
            if day is not None:
                keys_to_delete.append(f"gym_hours:day:{day}:gym:{gym_id}")

            # Invalidar clave específica de fecha si se proporciona
            if date_value is not None:
                date_str = date_value.isoformat()
                keys_to_delete.append(f"gym_hours:date:{date_str}:gym:{gym_id}")

            # Claves adicionales a invalidar siempre
            keys_to_delete.append(f"gym_hours:all:gym:{gym_id}")

            # Obtener las claves de lista desde el Set de seguimiento
            list_cache_keys = await redis_client.smembers(tracking_set_key)
            if list_cache_keys:
                # Convertir bytes a strings si es necesario (depende de la configuración de redis-py)
                list_cache_keys_str = [key.decode('utf-8') if isinstance(key, bytes) else key for key in list_cache_keys]
                keys_to_delete.extend(list_cache_keys_str)
                # Añadir el propio Set a la lista para borrarlo también
                keys_to_delete.append(tracking_set_key)

            # Borrar todas las claves encontradas
            if keys_to_delete:
                deleted_count = await redis_client.delete(*keys_to_delete)
                logger.debug(f"Invalidated {deleted_count} gym hours cache keys for gym {gym_id}: {keys_to_delete}")

        except Exception as e:
            logger.error(f"Error invalidating gym hours cache for gym {gym_id}: {e}", exc_info=True)
    # --- Fin método helper ---

    async def get_gym_hours_by_day(self, db: AsyncSession, day: int, gym_id: int) -> Any:
        """
        Obtener los horarios del gimnasio para un día específico.

        Args:
            db: Sesión de base de datos async
            day: Día de la semana (0=Lunes, 6=Domingo)
            gym_id: ID del gimnasio
        """
        result = await async_gym_hours_repository.get_by_day_async(db, day=day, gym_id=gym_id)
        if not result:
            result = await async_gym_hours_repository.get_or_create_default_async(db, day=day, gym_id=gym_id)
        return result

    async def get_gym_hours_by_day_cached(self, db: AsyncSession, day: int, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """
        Obtener los horarios del gimnasio para un día específico (con caché).

        Args:
            db: Sesión de base de datos async
            day: Día de la semana (0=Lunes, 6=Domingo)
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional
        """
        if not redis_client:
            return await self.get_gym_hours_by_day(db, day, gym_id)

        cache_key = f"gym_hours:day:{day}:gym:{gym_id}"
        tracking_set_key = f"cache_keys:gym_hours:{gym_id}"

        # Indica si el resultado vino de la BD
        fetched_from_db = False

        async def db_fetch():
            nonlocal fetched_from_db
            result = await async_gym_hours_repository.get_by_day_async(db, day=day, gym_id=gym_id)
            # Si no hay resultados, creamos valores predeterminados
            if not result:
                result = await async_gym_hours_repository.get_or_create_default_async(db, day=day, gym_id=gym_id)
            fetched_from_db = True
            return result

        hours = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=GymHours,
            expiry_seconds=3600 * 24, # 24 horas
            is_list=False
        )

        # Si se obtuvo de la BD, añadir la clave al set de seguimiento
        if fetched_from_db and redis_client and hours is not None:
            try:
                await redis_client.sadd(tracking_set_key, cache_key)
                await redis_client.expire(tracking_set_key, 3600 * 24 * 7) # 7 días
                logger.debug(f"Added cache key {cache_key} to tracking set {tracking_set_key}")
            except Exception as e:
                logger.error(f"Error adding cache key {cache_key} to set {tracking_set_key}: {e}", exc_info=True)

        return hours

    async def get_all_gym_hours(self, db: AsyncSession, gym_id: int) -> List[Any]:
        """
        Obtener los horarios para todos los días de la semana.

        Args:
            db: Sesión de base de datos async
            gym_id: ID del gimnasio
        """
        result = await async_gym_hours_repository.get_all_days_async(db, gym_id=gym_id)
        if len(result) < 7:
            existing_days = {hour.day_of_week for hour in result}
            for day in range(7):
                if day not in existing_days:
                    new_day = await async_gym_hours_repository.get_or_create_default_async(db, day=day, gym_id=gym_id)
                    result.append(new_day)
            result.sort(key=lambda x: x.day_of_week)
        return result

    async def get_all_gym_hours_cached(self, db: AsyncSession, gym_id: int, redis_client: Optional[Redis] = None) -> List[Any]:
        """
        Obtener los horarios para todos los días de la semana (con caché).

        Args:
            db: Sesión de base de datos async
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional
        """
        if not redis_client:
            return await self.get_all_gym_hours(db, gym_id)

        cache_key = f"gym_hours:all:gym:{gym_id}"
        tracking_set_key = f"cache_keys:gym_hours:{gym_id}"

        # Indica si el resultado vino de la BD
        fetched_from_db = False

        async def db_fetch():
            nonlocal fetched_from_db
            result = await async_gym_hours_repository.get_all_days_async(db, gym_id=gym_id)
            # Comprobar si tenemos los 7 días de la semana
            if len(result) < 7:
                # Si faltan días, crear los que falten con valores predeterminados
                existing_days = {hour.day_of_week for hour in result}
                for day in range(7):
                    if day not in existing_days:
                        # Crear con valores predeterminados
                        new_day = await async_gym_hours_repository.get_or_create_default_async(db, day=day, gym_id=gym_id)
                        result.append(new_day)
                # Ordenar por día de la semana
                result.sort(key=lambda x: x.day_of_week)
            fetched_from_db = True
            return result

        hours = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=GymHours,
            expiry_seconds=3600 * 24, # 24 horas
            is_list=True
        )

        # Si se obtuvo de la BD, añadir la clave al set de seguimiento
        if fetched_from_db and redis_client and hours is not None:
            try:
                await redis_client.sadd(tracking_set_key, cache_key)
                await redis_client.expire(tracking_set_key, 3600 * 24 * 7) # 7 días
                logger.debug(f"Added cache key {cache_key} to tracking set {tracking_set_key}")
            except Exception as e:
                logger.error(f"Error adding cache key {cache_key} to set {tracking_set_key}: {e}", exc_info=True)

        return hours

    async def create_or_update_gym_hours_cached(
        self, db: AsyncSession, day: int, gym_hours_data: Union[GymHoursCreate, GymHoursUpdate],
        gym_id: int, redis_client: Optional[Redis] = None
    ) -> Any:
        """
        Crear o actualizar los horarios del gimnasio para un día específico (con invalidación de caché).

        Args:
            db: Sesión de base de datos async
            day: Día de la semana (0=Lunes, 6=Domingo)
            gym_hours_data: Datos del horario a crear o actualizar
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional
        """
        # Ejecutar operación de creación/actualización
        result = await self.create_or_update_gym_hours(db, day, gym_hours_data, gym_id)

        # Invalidar caché si la operación fue exitosa
        if result and redis_client:
            await self._invalidate_gym_hours_cache(redis_client, gym_id, day=day)

        return result

    async def _create_default_hours(self, db: AsyncSession, gym_id: int) -> List[Any]:
        """
        Crea los horarios predeterminados para un gimnasio.
        Método interno usado para reemplazar initialize_default_hours.

        Args:
            db: Sesión de base de datos async
            gym_id: ID del gimnasio
        """
        default_hours = []

        # Horarios predeterminados (Lunes a Viernes: 9am-9pm, Sábado: 10am-6pm, Domingo: cerrado)
        default_schedule = {
            0: (time(9, 0), time(21, 0), False),  # Lunes
            1: (time(9, 0), time(21, 0), False),  # Martes
            2: (time(9, 0), time(21, 0), False),  # Miércoles
            3: (time(9, 0), time(21, 0), False),  # Jueves
            4: (time(9, 0), time(21, 0), False),  # Viernes
            5: (time(10, 0), time(18, 0), False), # Sábado
            6: (None, None, True)                 # Domingo (cerrado)
        }

        for day in range(7):
            open_time, close_time, is_closed = default_schedule[day]

            # Crear el objeto de datos para el repositorio, incluyendo gym_id
            obj_in_data = {
                "day_of_week": day,
                "open_time": open_time,
                "close_time": close_time,
                "is_closed": is_closed,
                "gym_id": gym_id
            }

            # Verificar si ya existen horarios para este día
            existing_hours = await async_gym_hours_repository.get_by_day_async(db, day=day, gym_id=gym_id)
            if existing_hours:
                # Si ya existen, actualizar solo si es necesario
                # Crear un objeto de actualización solo con los campos que cambian
                update_data = {}
                if existing_hours.open_time != open_time:
                    update_data['open_time'] = open_time
                if existing_hours.close_time != close_time:
                    update_data['close_time'] = close_time
                if existing_hours.is_closed != is_closed:
                    update_data['is_closed'] = is_closed

                if update_data: # Solo actualizar si hay cambios
                    hours = await async_gym_hours_repository.update_async(db, db_obj=existing_hours, obj_in=update_data)
                else:
                    hours = existing_hours
            else:
                # Si no existen, crear nuevos usando obj_in_data (que ya tiene gym_id)
                hours = await async_gym_hours_repository.create_async(db, obj_in=obj_in_data)

            default_hours.append(hours)

        return default_hours

    async def get_hours_for_date(self, db: AsyncSession, date_value: date, gym_id: int) -> Dict[str, Any]:
        """
        Obtener los horarios del gimnasio para una fecha específica.

        Args:
            db: Sesión de base de datos async
            date_value: Fecha a consultar
            gym_id: ID del gimnasio
        """
        special_hours = await async_gym_special_hours_repository.get_by_date_async(db, date_value=date_value, gym_id=gym_id)
        day_of_week = date_value.weekday()
        regular_hours = await async_gym_hours_repository.get_by_day_async(db, day=day_of_week, gym_id=gym_id)
        if not regular_hours:
            regular_hours = await async_gym_hours_repository.get_or_create_default_async(db, day=day_of_week, gym_id=gym_id)

        result = {
            "date": date_value,
            "day_of_week": day_of_week,
            "regular_hours": {
                "id": regular_hours.id,
                "open_time": regular_hours.open_time,
                "close_time": regular_hours.close_time,
                "is_closed": regular_hours.is_closed
            },
            "special_hours": None,
            "is_special": special_hours is not None
        }

        if special_hours:
            result["special_hours"] = {
                "id": special_hours.id,
                "open_time": special_hours.open_time,
                "close_time": special_hours.close_time,
                "is_closed": special_hours.is_closed,
                "description": special_hours.description
            }

        if special_hours:
            result["effective_hours"] = {
                "open_time": special_hours.open_time,
                "close_time": special_hours.close_time,
                "is_closed": special_hours.is_closed,
                "source": "special",
                "source_id": special_hours.id
            }
        else:
            result["effective_hours"] = {
                "open_time": regular_hours.open_time,
                "close_time": regular_hours.close_time,
                "is_closed": regular_hours.is_closed,
                "source": "regular",
                "source_id": regular_hours.id
            }

        return result

    async def get_hours_for_date_cached(self, db: AsyncSession, date_value: date, gym_id: int, redis_client: Optional[Redis] = None) -> Dict[str, Any]:
        """
        Obtener los horarios del gimnasio para una fecha específica (con caché).

        Args:
            db: Sesión de base de datos async
            date_value: Fecha a consultar
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional
        """
        if not redis_client:
            return await self.get_hours_for_date(db, date_value, gym_id)

        date_str = date_value.isoformat()
        cache_key = f"gym_hours:date:{date_str}:gym:{gym_id}"
        tracking_set_key = f"cache_keys:gym_hours:{gym_id}"

        # Indica si el resultado vino de la BD
        fetched_from_db = False

        async def db_fetch():
            nonlocal fetched_from_db
            result = await self.get_hours_for_date(db, date_value, gym_id)
            fetched_from_db = True
            return result

        hours_data = await cache_service.get_or_set_json(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            expiry_seconds=3600 * 12, # 12 horas
        )

        # Si se obtuvo de la BD, añadir la clave al set de seguimiento
        if fetched_from_db and redis_client and hours_data is not None:
            try:
                await redis_client.sadd(tracking_set_key, cache_key)
                await redis_client.expire(tracking_set_key, 3600 * 24 * 7) # 7 días
                logger.debug(f"Added cache key {cache_key} to tracking set {tracking_set_key}")
            except Exception as e:
                logger.error(f"Error adding cache key {cache_key} to set {tracking_set_key}: {e}", exc_info=True)

        return hours_data

    async def create_or_update_gym_hours(
        self, db: AsyncSession, day: int, gym_hours_data: Union[GymHoursCreate, GymHoursUpdate],
        gym_id: int
    ) -> Any:
        """
        Crear o actualizar los horarios del gimnasio para un día específico.

        Args:
            db: Sesión de base de datos async
            day: Día de la semana (0=Lunes, 6=Domingo)
            gym_hours_data: Datos del horario a crear o actualizar
            gym_id: ID del gimnasio
        """
        # Verificar si ya existen horarios para este día
        existing_hours = await async_gym_hours_repository.get_by_day_async(db, day=day, gym_id=gym_id)

        if existing_hours:
            # Actualizar horarios existentes
            return await async_gym_hours_repository.update_async(
                db, db_obj=existing_hours, obj_in=gym_hours_data
            )
        else:
            # Crear nuevos horarios
            obj_in_data = gym_hours_data.model_dump() if isinstance(gym_hours_data, GymHoursCreate) else gym_hours_data
            if not isinstance(gym_hours_data, GymHoursCreate):
                # Convertir GymHoursUpdate a GymHoursCreate
                obj_in_data["day_of_week"] = day
                obj_in_data["gym_id"] = gym_id
                # Usar valores predeterminados si no se proporcionan
                if "open_time" not in obj_in_data or obj_in_data["open_time"] is None:
                    obj_in_data["open_time"] = time(9, 0)  # 9:00 AM
                if "close_time" not in obj_in_data or obj_in_data["close_time"] is None:
                    obj_in_data["close_time"] = time(21, 0)  # 9:00 PM
                if "is_closed" not in obj_in_data or obj_in_data["is_closed"] is None:
                    obj_in_data["is_closed"] = (day == 6)  # Cerrado en domingo

                obj_in = GymHoursCreate(**obj_in_data)
            else:
                # Asegurarse de que el gym_id esté establecido
                if "gym_id" not in obj_in_data or obj_in_data["gym_id"] is None:
                    obj_in_data["gym_id"] = gym_id
                obj_in = GymHoursCreate(**obj_in_data)

            return await async_gym_hours_repository.create_async(db, obj_in=obj_in)

    async def apply_defaults_to_range_cached(
        self, db: AsyncSession, start_date: date, end_date: date, gym_id: int,
        overwrite_existing: bool = False, redis_client: Optional[Redis] = None
    ) -> List[GymSpecialHours]:
        """
        Asegura que existan los horarios semanales base para el gimnasio.
        Ya NO crea registros especiales - solo valida/crea la plantilla semanal.

        Args:
            db: Sesión de base de datos async
            start_date: Fecha de inicio del rango (solo para validación)
            end_date: Fecha de fin del rango (solo para validación)
            gym_id: ID del gimnasio
            overwrite_existing: Ignorado en esta nueva implementación
            redis_client: Cliente Redis opcional

        Returns:
            Lista vacía (ya no crea GymSpecialHours)
        """
        # Verificar que el rango de fechas sea válido
        if end_date < start_date:
            raise ValueError("La fecha de fin no puede ser anterior a la fecha de inicio")

        # Obtener los horarios semanales predeterminados (utilizando la versión cacheada)
        weekly_hours = await self.get_all_gym_hours_cached(db, gym_id=gym_id, redis_client=redis_client)
        if not weekly_hours:
            # Si no hay horarios semanales, crearlos con valores predeterminados
            weekly_hours = await self._create_default_hours(db, gym_id=gym_id)

            # Invalidar caché de horarios semanales si se crearon nuevos
            if redis_client:
                await self._invalidate_gym_hours_cache(redis_client, gym_id)

        # Ya no creamos registros especiales
        # Simplemente devolvemos una lista vacía para mantener compatibilidad con la API
        return []

    async def get_schedule_for_date_range(
        self, db: AsyncSession, start_date: date, end_date: date, gym_id: int
    ) -> List[Dict[str, Any]]:
        """
        Obtener el horario del gimnasio para un rango de fechas.

        Args:
            db: Sesión de base de datos async
            start_date: Fecha de inicio
            end_date: Fecha de fin
            gym_id: ID del gimnasio
        """
        if end_date < start_date:
            raise ValueError("La fecha de fin no puede ser anterior a la fecha de inicio")

        special_hours = await async_gym_special_hours_repository.get_by_date_range_async(
            db, start_date=start_date, end_date=end_date, gym_id=gym_id
        )
        special_hours_dict = {str(hour.date): hour for hour in special_hours}
        weekly_hours = await self.get_all_gym_hours(db, gym_id=gym_id)
        weekly_hours_dict = {hour.day_of_week: hour for hour in weekly_hours}

        result: List[Dict[str, Any]] = []
        current_date = start_date
        while current_date <= end_date:
            day_of_week = current_date.weekday()
            date_str = str(current_date)
            if date_str in special_hours_dict:
                sh = special_hours_dict[date_str]
                entry = {
                    "date": current_date,
                    "day_of_week": day_of_week,
                    "open_time": sh.open_time,
                    "close_time": sh.close_time,
                    "is_closed": sh.is_closed,
                    "is_special": True,
                    "description": sh.description,
                    "source_id": sh.id
                }
            else:
                wh = weekly_hours_dict.get(day_of_week)
                if not wh:
                    is_closed = day_of_week == 6
                    open_time = None if is_closed else time(9, 0)
                    close_time = None if is_closed else time(21, 0)
                    source_id = None
                else:
                    is_closed = wh.is_closed
                    open_time = wh.open_time
                    close_time = wh.close_time
                    source_id = wh.id
                entry = {
                    "date": current_date,
                    "day_of_week": day_of_week,
                    "open_time": open_time,
                    "close_time": close_time,
                    "is_closed": is_closed,
                    "is_special": False,
                    "description": None,
                    "source_id": source_id
                }
            result.append(entry)
            current_date += timedelta(days=1)
        return result

    async def get_schedule_for_date_range_cached(
        self, db: AsyncSession, start_date: date, end_date: date, gym_id: int, redis_client: Optional[Redis] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtener el horario del gimnasio para un rango de fechas (con caché).

        Args:
            db: Sesión de base de datos async
            start_date: Fecha de inicio
            end_date: Fecha de fin
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional
        """
        # Si no hay Redis, o el rango es muy grande, procesar sin caché
        if not redis_client or (end_date - start_date).days > 31:  # Si es más de un mes, no cachear
            # Verificar que el rango de fechas sea válido
            if end_date < start_date:
                raise ValueError("La fecha de fin no puede ser anterior a la fecha de inicio")

            # Obtener los horarios especiales para este rango
            special_hours = await async_gym_special_hours_repository.get_by_date_range_async(
                db, start_date=start_date, end_date=end_date, gym_id=gym_id
            )

            # Crear un diccionario de horarios especiales por fecha para acceso rápido
            special_hours_dict = {str(hour.date): hour for hour in special_hours}

            # Obtener los horarios semanales predeterminados (usando la versión cacheada)
            weekly_hours = await self.get_all_gym_hours_cached(db, gym_id=gym_id, redis_client=None)
            if not weekly_hours:
                # Si no hay horarios semanales, crearlos con valores predeterminados
                weekly_hours = await self._create_default_hours(db, gym_id=gym_id)

            # Crear un diccionario de horarios por día de la semana para acceso rápido
            weekly_hours_dict = {hour.day_of_week: hour for hour in weekly_hours}

            # Preparar la respuesta
            result = []
            current_date = start_date

            while current_date <= end_date:
                # Obtener el día de la semana (0=Lunes, 6=Domingo)
                day_of_week = current_date.weekday()
                date_str = str(current_date)

                # Verificar si hay un horario especial para esta fecha
                if date_str in special_hours_dict:
                    special_hour = special_hours_dict[date_str]
                    schedule_entry = {
                        "date": current_date,
                        "day_of_week": day_of_week,
                        "open_time": special_hour.open_time,
                        "close_time": special_hour.close_time,
                        "is_closed": special_hour.is_closed,
                        "is_special": True,
                        "description": special_hour.description,
                        "source_id": special_hour.id
                    }
                else:
                    # Usar el horario semanal para este día
                    weekly_hour = weekly_hours_dict.get(day_of_week)
                    if not weekly_hour:
                        # Si no hay horario para este día, usar valores predeterminados
                        is_closed = day_of_week == 6  # Cerrado en domingo
                        open_time = time(9, 0) if not is_closed else None
                        close_time = time(21, 0) if not is_closed else None
                        source_id = None
                    else:
                        # Usar el horario semanal para este día
                        is_closed = weekly_hour.is_closed
                        open_time = weekly_hour.open_time
                        close_time = weekly_hour.close_time
                        source_id = weekly_hour.id

                    schedule_entry = {
                        "date": current_date,
                        "day_of_week": day_of_week,
                        "open_time": open_time,
                        "close_time": close_time,
                        "is_closed": is_closed,
                        "is_special": False,
                        "description": None,
                        "source_id": source_id
                    }

                result.append(schedule_entry)

                # Avanzar al siguiente día
                current_date += timedelta(days=1)

            return result

        # Para rangos pequeños, usar caché por fecha individual
        schedule_list = []
        current_date = start_date

        while current_date <= end_date:
            # Obtener horario efectivo para cada fecha usando el método cacheado
            daily_schedule = await self.get_hours_for_date_cached(
                db=db,
                date_value=current_date,
                gym_id=gym_id,
                redis_client=redis_client
            )

            # Convertir el formato de respuesta de get_hours_for_date_cached a DailyScheduleResponse
            effective_hours = daily_schedule.get("effective_hours", {})
            schedule_entry = {
                "date": current_date,
                "day_of_week": current_date.weekday(),
                "open_time": effective_hours.get("open_time"),
                "close_time": effective_hours.get("close_time"),
                "is_closed": effective_hours.get("is_closed", False),
                "is_special": daily_schedule.get("is_special", False),
                "description": daily_schedule.get("special_hours", {}).get("description") if daily_schedule.get("special_hours") else None,
                "source_id": effective_hours.get("source_id")
            }

            schedule_list.append(schedule_entry)
            current_date += timedelta(days=1)

        return schedule_list


class AsyncGymSpecialHoursService:
    # --- Añadir método helper para invalidación de caché ---
    async def _invalidate_special_hours_cache(self, redis_client: Redis, gym_id: int, special_day_id: Optional[int] = None, date_value: Optional[date] = None):
        """
        Invalida la caché de días especiales.

        Args:
            redis_client: Cliente Redis
            gym_id: ID del gimnasio
            special_day_id: ID del día especial a invalidar (opcional)
            date_value: Fecha específica a invalidar (opcional)
        """
        if not redis_client:
            return

        tracking_set_key = f"cache_keys:special_days:{gym_id}"
        keys_to_delete = []

        try:
            # Invalidar clave específica de ID si se proporciona
            if special_day_id is not None:
                keys_to_delete.append(f"special_day:detail:{special_day_id}")

            # Invalidar clave específica de fecha si se proporciona
            if date_value is not None:
                date_str = date_value.isoformat()
                keys_to_delete.append(f"special_day:date:{date_str}:gym:{gym_id}")

            # Claves adicionales a invalidar siempre
            keys_to_delete.append(f"special_days:upcoming:gym:{gym_id}")

            # Obtener las claves de lista desde el Set de seguimiento
            list_cache_keys = await redis_client.smembers(tracking_set_key)
            if list_cache_keys:
                # Convertir bytes a strings si es necesario
                list_cache_keys_str = [key.decode('utf-8') if isinstance(key, bytes) else key for key in list_cache_keys]
                keys_to_delete.extend(list_cache_keys_str)
                # Añadir el propio Set a la lista para borrarlo también
                keys_to_delete.append(tracking_set_key)

            # Borrar todas las claves encontradas
            if keys_to_delete:
                deleted_count = await redis_client.delete(*keys_to_delete)
                logger.debug(f"Invalidated {deleted_count} special days cache keys for gym {gym_id}: {keys_to_delete}")

        except Exception as e:
            logger.error(f"Error invalidating special days cache for gym {gym_id}: {e}", exc_info=True)
    # --- Fin método helper ---

    async def get_special_hours_cached(self, db: AsyncSession, special_day_id: int, redis_client: Optional[Redis] = None) -> Any:
        """
        Obtener un día especial por ID (con caché).

        Args:
            db: Sesión de base de datos async
            special_day_id: ID del día especial
            redis_client: Cliente Redis opcional
        """
        if not redis_client:
            return await self.get_special_hours(db, special_day_id)

        cache_key = f"special_day:detail:{special_day_id}"

        async def db_fetch():
            return await async_gym_special_hours_repository.get_async(db, id=special_day_id)

        special_day = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=GymSpecialHoursSchema,
            expiry_seconds=3600 * 12, # 12 horas
            is_list=False
        )

        return special_day

    async def get_special_hours(self, db: AsyncSession, special_day_id: int) -> Any:
        """Obtener un día especial por ID (versión no-caché)"""
        return await async_gym_special_hours_repository.get_async(db, id=special_day_id)

    async def get_special_hours_by_date_cached(self, db: AsyncSession, date_value: date, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """
        Obtener horarios especiales para una fecha específica (con caché).

        Args:
            db: Sesión de base de datos async
            date_value: Fecha a consultar
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional
        """
        if not redis_client:
            return await self.get_special_hours_by_date(db, date_value, gym_id)

        date_str = date_value.isoformat()
        cache_key = f"special_day:date:{date_str}:gym:{gym_id}"
        tracking_set_key = f"cache_keys:special_days:{gym_id}"

        # Indica si el resultado vino de la BD
        fetched_from_db = False

        async def db_fetch():
            nonlocal fetched_from_db
            result = await async_gym_special_hours_repository.get_by_date_async(db, date_value=date_value, gym_id=gym_id)
            fetched_from_db = True
            return result

        special_day = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=GymSpecialHoursSchema,
            expiry_seconds=3600 * 12, # 12 horas
            is_list=False
        )

        # Si se obtuvo de la BD, añadir la clave al set de seguimiento
        if fetched_from_db and redis_client and special_day is not None:
            try:
                await redis_client.sadd(tracking_set_key, cache_key)
                await redis_client.expire(tracking_set_key, 3600 * 24 * 7) # 7 días
                logger.debug(f"Added cache key {cache_key} to tracking set {tracking_set_key}")
            except Exception as e:
                logger.error(f"Error adding cache key {cache_key} to set {tracking_set_key}: {e}", exc_info=True)

        return special_day

    async def get_special_hours_by_date(self, db: AsyncSession, date_value: date, gym_id: int) -> Any:
        """
        Obtener horarios especiales para una fecha específica (versión no-caché).

        Args:
            db: Sesión de base de datos async
            date_value: Fecha a consultar
            gym_id: ID del gimnasio
        """
        return await async_gym_special_hours_repository.get_by_date_async(db, date_value=date_value, gym_id=gym_id)

    async def get_upcoming_special_days_cached(self, db: AsyncSession, limit: int = 10, gym_id: int = None, redis_client: Optional[Redis] = None) -> List[Any]:
        """
        Obtener los próximos días especiales (con caché).

        Args:
            db: Sesión de base de datos async
            limit: Número máximo de registros a devolver
            gym_id: ID del gimnasio para filtrar
            redis_client: Cliente Redis opcional
        """
        if not redis_client or not gym_id:
            return await self.get_upcoming_special_days(db, limit, gym_id)

        cache_key = f"special_days:upcoming:gym:{gym_id}:limit:{limit}"
        tracking_set_key = f"cache_keys:special_days:{gym_id}"

        # Indica si el resultado vino de la BD
        fetched_from_db = False

        async def db_fetch():
            nonlocal fetched_from_db
            result = await async_gym_special_hours_repository.get_upcoming_special_days_async(db, limit=limit, gym_id=gym_id)
            fetched_from_db = True
            return result

        special_days = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=GymSpecialHoursSchema,
            expiry_seconds=3600 * 6, # 6 horas
            is_list=True
        )

        # Si se obtuvo de la BD, añadir la clave al set de seguimiento
        if fetched_from_db and redis_client and special_days is not None:
            try:
                await redis_client.sadd(tracking_set_key, cache_key)
                await redis_client.expire(tracking_set_key, 3600 * 24 * 7) # 7 días
                logger.debug(f"Added cache key {cache_key} to tracking set {tracking_set_key}")
            except Exception as e:
                logger.error(f"Error adding cache key {cache_key} to set {tracking_set_key}: {e}", exc_info=True)

        return special_days

    async def get_upcoming_special_days(self, db: AsyncSession, limit: int = 10, gym_id: int = None) -> List[Any]:
        """
        Obtener los próximos días especiales (versión no-caché).

        Args:
            db: Sesión de base de datos async
            limit: Número máximo de registros a devolver
            gym_id: ID del gimnasio para filtrar
        """
        return await async_gym_special_hours_repository.get_upcoming_special_days_async(db, limit=limit, gym_id=gym_id)

    async def create_special_day_cached(self, db: AsyncSession, special_hours_data: GymSpecialHoursCreate, gym_id: int = None, redis_client: Optional[Redis] = None) -> Any:
        """
        Crear un nuevo día especial e invalidar caché.

        Args:
            db: Sesión de base de datos async
            special_hours_data: Datos del día especial a crear
            gym_id: ID del gimnasio al que pertenece el día especial
            redis_client: Cliente Redis opcional
        """
        # Crear el día especial
        result = await self.create_special_day(db, special_hours_data, gym_id)

        # Invalidar cachés afectadas
        if result and redis_client:
            await self._invalidate_special_hours_cache(
                redis_client,
                gym_id,
                date_value=result.date
            )

        return result

    async def create_special_day(self, db: AsyncSession, special_hours_data: GymSpecialHoursCreate, gym_id: int = None) -> Any:
        """
        Crear un nuevo día especial (versión no-caché)

        Args:
            db: Sesión de base de datos async
            special_hours_data: Datos del día especial a crear
            gym_id: ID del gimnasio al que pertenece el día especial
        """
        if gym_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere un ID de gimnasio válido"
            )

        # Crear una copia de los datos para añadir el gym_id
        obj_in_data = special_hours_data.model_dump()
        obj_in_data["gym_id"] = gym_id

        # Crear el objeto usando el repositorio
        return await async_gym_special_hours_repository.create_async(db, obj_in=obj_in_data)

    async def update_special_day_cached(
        self, db: AsyncSession, special_day_id: int, special_hours_data: GymSpecialHoursUpdate, redis_client: Optional[Redis] = None
    ) -> Any:
        """
        Actualizar un día especial existente e invalidar caché.

        Args:
            db: Sesión de base de datos async
            special_day_id: ID del día especial a actualizar
            special_hours_data: Datos a actualizar
            redis_client: Cliente Redis opcional
        """
        # Obtener el día especial para conocer su gym_id y fecha
        special_day = await self.get_special_hours_cached(db, special_day_id, redis_client)
        if not special_day:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Día especial no encontrado"
            )

        # Actualizar el día especial
        result = await self.update_special_day(db, special_day_id, special_hours_data)

        # Invalidar cachés afectadas
        if result and redis_client:
            await self._invalidate_special_hours_cache(
                redis_client,
                special_day.gym_id,
                special_day_id=special_day_id,
                date_value=special_day.date
            )

        return result

    async def update_special_day(
        self, db: AsyncSession, special_day_id: int, special_hours_data: GymSpecialHoursUpdate
    ) -> Any:
        """
        Actualizar un día especial existente (versión no-caché)

        Args:
            db: Sesión de base de datos async
            special_day_id: ID del día especial a actualizar
            special_hours_data: Datos a actualizar
        """
        special_day = await async_gym_special_hours_repository.get_async(db, id=special_day_id)
        if not special_day:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Día especial no encontrado"
            )

        return await async_gym_special_hours_repository.update_async(
            db, db_obj=special_day, obj_in=special_hours_data
        )

    async def delete_special_day_cached(self, db: AsyncSession, special_day_id: int, redis_client: Optional[Redis] = None) -> Any:
        """
        Eliminar un día especial e invalidar caché.

        Args:
            db: Sesión de base de datos async
            special_day_id: ID del día especial a eliminar
            redis_client: Cliente Redis opcional
        """
        # Obtener el día especial para conocer su gym_id y fecha
        special_day = await self.get_special_hours_cached(db, special_day_id, redis_client)
        if not special_day:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Día especial no encontrado"
            )

        # Eliminar el día especial
        result = await self.delete_special_day(db, special_day_id)

        # Invalidar cachés afectadas
        if result and redis_client:
            await self._invalidate_special_hours_cache(
                redis_client,
                special_day.gym_id,
                special_day_id=special_day_id,
                date_value=special_day.date
            )

        return result

    async def delete_special_day(self, db: AsyncSession, special_day_id: int) -> Any:
        """
        Eliminar un día especial (versión no-caché)

        Args:
            db: Sesión de base de datos async
            special_day_id: ID del día especial a eliminar
        """
        special_day = await async_gym_special_hours_repository.get_async(db, id=special_day_id)
        if not special_day:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Día especial no encontrado"
            )

        return await async_gym_special_hours_repository.remove_async(db, id=special_day_id)

    async def apply_defaults_to_range_async(
        self,
        db: AsyncSession,
        start_date: date,
        end_date: date,
        gym_id: int
    ) -> int:
        """Aplicar horarios predeterminados a un rango de fechas (async)."""
        count = 0
        current_date = start_date

        while current_date <= end_date:
            # Verificar si ya existe un día especial
            existing = await async_gym_special_hours_repository.get_by_date_async(db, date_value=current_date, gym_id=gym_id)

            if not existing:
                # Obtener horarios regulares para este día
                day_of_week = current_date.weekday()
                regular_hours = await async_gym_hours_repository.get_by_day_async(db, day=day_of_week, gym_id=gym_id)

                if not regular_hours:
                    regular_hours = await async_gym_hours_repository.get_or_create_default_async(db, day=day_of_week, gym_id=gym_id)

                # Crear día especial con horarios regulares
                obj_in_data = {
                    "date": current_date,
                    "gym_id": gym_id,
                    "open_time": regular_hours.open_time,
                    "close_time": regular_hours.close_time,
                    "is_closed": regular_hours.is_closed,
                    "description": f"Horario regular aplicado automáticamente"
                }

                await async_gym_special_hours_repository.create_async(db, obj_in=obj_in_data)
                count += 1

            current_date += timedelta(days=1)

        return count

    async def get_schedule_for_date_range_async(
        self,
        db: AsyncSession,
        start_date: date,
        end_date: date,
        gym_id: int
    ) -> List[Dict[str, Any]]:
        """Obtener horario efectivo para un rango de fechas (async)."""
        schedule_list = []
        current_date = start_date

        while current_date <= end_date:
            # Obtener horario efectivo para cada fecha
            daily_schedule = await async_gym_hours_service.get_hours_for_date(
                db=db,
                date_value=current_date,
                gym_id=gym_id
            )

            effective_hours = daily_schedule.get("effective_hours", {})
            schedule_entry = {
                "date": current_date,
                "day_of_week": current_date.weekday(),
                "open_time": effective_hours.get("open_time"),
                "close_time": effective_hours.get("close_time"),
                "is_closed": effective_hours.get("is_closed", False),
                "is_special": daily_schedule.get("is_special", False),
                "description": daily_schedule.get("special_hours", {}).get("description") if daily_schedule.get("special_hours") else None,
                "source_id": effective_hours.get("source_id")
            }

            schedule_list.append(schedule_entry)
            current_date += timedelta(days=1)

        return schedule_list


# --- Añadir Servicio para Categorías Personalizadas ---
class AsyncClassCategoryService:
    # --- Añadir método helper para invalidación ---
    async def _invalidate_custom_category_caches(self, redis_client: Redis, gym_id: int, category_id: Optional[int] = None):
        if not redis_client:
            return
        tracking_set_key = f"cache_keys:categories:gym:{gym_id}"
        keys_to_delete = []

        try:
            # Borrar clave de detalle si se proporciona ID
            if category_id:
                detail_key = f"category:custom:detail:{category_id}"
                keys_to_delete.append(detail_key)

            # Obtener claves de lista desde el Set de seguimiento
            list_cache_keys = await redis_client.smembers(tracking_set_key)
            if list_cache_keys:
                # Convertir bytes a strings si es necesario (depende de la configuración de redis-py)
                list_cache_keys_str = [key.decode('utf-8') if isinstance(key, bytes) else key for key in list_cache_keys]
                keys_to_delete.extend(list_cache_keys_str)
                # Añadir el propio Set a la lista para borrarlo también
                keys_to_delete.append(tracking_set_key)

            # Borrar todas las claves encontradas (detalle, listas y el set)
            if keys_to_delete:
                deleted_count = await redis_client.delete(*keys_to_delete)
                logger.debug(f"Invalidated {deleted_count} category cache keys for gym {gym_id}: {keys_to_delete}")

        except Exception as e:
            logger.error(f"Error invalidating category cache for gym {gym_id}: {e}", exc_info=True)
    # --- Fin método helper ---

    async def get_category(self, db: AsyncSession, category_id: int, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """Obtener una categoría por ID (con caché) asegurando que pertenece al gimnasio"""

        cache_key = f"category:custom:detail:{category_id}"

        async def db_fetch():
            # Verificar que la categoría existe en la BD
            category_db = await async_class_category_repository.get_async(db, id=category_id)
            if not category_db:
                 raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Categoría no encontrada"
                )
            return category_db

        # Intentar obtener de caché
        category = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=ClassCategoryCustomSchema,
            expiry_seconds=3600, # 1 hora
            is_list=False
        )

        # Verificar pertenencia al gimnasio después de obtenerla (de caché o BD)
        if not category:
             # Si get_or_set devuelve None (por ej. error en db_fetch), lanzar 404
              raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Categoría no encontrada"
                )

        if category.gym_id != gym_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a esta categoría"
            )

        return category

    async def get_categories_by_gym(self, db: AsyncSession, gym_id: int, active_only: bool = True, redis_client: Optional[Redis] = None) -> List[Any]:
        """Obtener categorías para un gimnasio específico (con caché) y registrar la clave en un Set."""

        cache_key = f"categories:custom:gym:{gym_id}:active:{active_only}"
        tracking_set_key = f"cache_keys:categories:gym:{gym_id}"

        async def db_fetch():
            if active_only:
                return await async_class_category_repository.get_active_categories_async(db, gym_id=gym_id)
            return await async_class_category_repository.get_by_gym_async(db, gym_id=gym_id)

        # Indica si el resultado vino de la BD (y por tanto, se añadió a caché)
        fetched_from_db = False

        async def db_fetch_wrapper():
            nonlocal fetched_from_db
            result = await db_fetch()
            fetched_from_db = True # Marcar que se accedió a la BD
            return result

        categories = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch_wrapper, # Usar el wrapper
            model_class=ClassCategoryCustomSchema,
            expiry_seconds=3600, # 1 hora
            is_list=True
        )

        # Si se obtuvo de la BD y se guardó en caché, añadir la clave al Set de seguimiento
        if fetched_from_db and redis_client and categories is not None: # Asegurarse que no hubo error
            try:
                await redis_client.sadd(tracking_set_key, cache_key)
                # Opcional: Poner un TTL al Set para que no crezca indefinidamente si algo falla
                await redis_client.expire(tracking_set_key, 3600 * 24) # Ej: 1 día
                logger.debug(f"Added cache key {cache_key} to tracking set {tracking_set_key}")
            except Exception as e:
                logger.error(f"Error adding cache key {cache_key} to set {tracking_set_key}: {e}", exc_info=True)

        return categories

    async def create_category(self, db: AsyncSession, category_data: ClassCategoryCustomCreate, gym_id: int, created_by_id: Optional[int] = None, redis_client: Optional[Redis] = None) -> Any:
        """Crear una nueva categoría personalizada e invalidar caché"""
        existing_category = await async_class_category_repository.get_by_name_and_gym_async(
            db, name=category_data.name, gym_id=gym_id
        )
        if existing_category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe una categoría con este nombre en este gimnasio"
            )

        db_obj = ClassCategoryCustom(
            **category_data.model_dump(),
            gym_id=gym_id,
            created_by=created_by_id
        )

        db.add(db_obj)
        try:
            await db.commit()
            await db.refresh(db_obj)
            # Invalidar caché después del commit exitoso
            await self._invalidate_custom_category_caches(redis_client, gym_id=gym_id)
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al guardar la categoría en la base de datos"
            )

        return db_obj

    async def update_category(self, db: AsyncSession, category_id: int, category_data: ClassCategoryCustomUpdate, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """Actualizar una categoría existente e invalidar caché"""
        # Usar get_category sin caché para obtener el objeto a actualizar
        # No podemos usar la versión cacheada porque necesitamos el objeto de SQLAlchemy
        category = await async_class_category_repository.get_async(db, id=category_id)
        if not category or category.gym_id != gym_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoría no encontrada en este gimnasio"
            )

        if category_data.name and category_data.name != category.name:
            existing_category = await async_class_category_repository.get_by_name_and_gym_async(
                db, name=category_data.name, gym_id=gym_id
            )
            if existing_category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ya existe otra categoría con este nombre en este gimnasio"
                )

        updated_category = await async_class_category_repository.update_async(db, db_obj=category, obj_in=category_data)
        # Invalidar caché después de la actualización
        await self._invalidate_custom_category_caches(redis_client, gym_id=gym_id, category_id=category_id)
        return updated_category

    async def delete_category(self, db: AsyncSession, category_id: int, gym_id: int, redis_client: Optional[Redis] = None) -> None:
        """Eliminar/inactivar una categoría e invalidar caché"""
        # Usar get_category sin caché para la verificación inicial
        category = await async_class_category_repository.get_async(db, id=category_id)
        if not category or category.gym_id != gym_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoría no encontrada en este gimnasio"
            )

        # Contar clases con esta categoría (query async)
        result = await db.execute(
            select(func.count(Class.id)).where(Class.category_id == category_id)
        )
        classes_with_category = result.scalar() or 0

        try:
            if classes_with_category > 0:
                await async_class_category_repository.update_async(
                    db, db_obj=category, obj_in={"is_active": False}
                )
            else:
                await async_class_category_repository.remove_async(db, id=category_id)
            # Invalidar caché después de eliminar/inactivar
            await self._invalidate_custom_category_caches(redis_client, gym_id=gym_id, category_id=category_id)
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al eliminar/inactivar categoría: {e}"
            )
# --- Fin Servicio ---


class AsyncClassService:
    # --- Añadir método helper para invalidación ---
    async def _invalidate_class_caches(self, redis_client: Optional[Redis], gym_id: int, class_id: Optional[int] = None, category_id: Optional[int] = None, difficulty: Optional[str] = None):
        if not redis_client:
            return

        keys_to_delete = []
        patterns_to_delete = []

        # Clave de detalle
        if class_id:
            keys_to_delete.append(f"schedule:class:detail:{class_id}")

        # Patrones de lista general y por gimnasio
        patterns_to_delete.append(f"schedule:classes:gym:{gym_id}:*")
        patterns_to_delete.append(f"schedule:classes:all:*")

        # Patrones de búsqueda y filtrado
        patterns_to_delete.append(f"schedule:classes:search:gym:{gym_id}:*")
        if category_id:
            patterns_to_delete.append(f"schedule:classes:category:{category_id}:gym:{gym_id}:*")
        if difficulty:
             patterns_to_delete.append(f"schedule:classes:difficulty:{difficulty}:gym:{gym_id}:*")

        try:
            if keys_to_delete:
                deleted_keys = await redis_client.delete(*keys_to_delete)
                logger.debug(f"Invalidated {deleted_keys} class detail keys: {keys_to_delete}")

            deleted_pattern_count = 0
            for pattern in patterns_to_delete:
                deleted_count = await cache_service.delete_pattern(redis_client, pattern)
                deleted_pattern_count += deleted_count
                logger.debug(f"Invalidated {deleted_count} keys with pattern: {pattern}")
            logger.debug(f"Total invalidated class keys from patterns: {deleted_pattern_count}")

        except Exception as e:
            logger.error(f"Error invalidating class cache for gym {gym_id} (class: {class_id}): {e}", exc_info=True)
    # --- Fin método helper ---

    async def get_class(self, db: AsyncSession, class_id: int, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """Obtener una clase por ID (con caché), asegurando que pertenece al gimnasio"""

        cache_key = f"schedule:class:detail:{class_id}"

        async def db_fetch():
            class_obj = await async_class_repository.get_async(db, id=class_id)
            if not class_obj:
                    # No lanzar excepción aquí, dejar que get_or_set devuelva None
                    return None
            return class_obj

        # Intentar obtener de caché
        class_cached = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=ClassSchema,
            expiry_seconds=3600, # 1 hora
            is_list=False
        )

        if not class_cached:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clase no encontrada"
            )

        # Verificar pertenencia al gimnasio después de obtenerla
        if class_cached.gym_id != gym_id:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a esta clase"
            )

        return class_cached

    async def get_classes(
        self, db: AsyncSession, skip: int = 0, limit: int = 100, active_only: bool = True,
        gym_id: Optional[int] = None, redis_client: Optional[Redis] = None
    ) -> List[Any]:
        """
        Obtener todas las clases, opcionalmente filtradas por gimnasio (con caché).
        """
        # Si no hay gym_id, no usar caché y ejecutar consulta directa
        if gym_id is None:
            logger.warning("Attempted to get classes without gym_id. Cache disabled and no gym filtering applied.")
            # Convertir a query async
            from sqlalchemy.orm import selectinload
            stmt = select(Class).options(selectinload(Class.custom_category))
            if active_only:
                stmt = stmt.where(Class.is_active == True)
            stmt = stmt.offset(skip).limit(limit)
            result = await db.execute(stmt)
            return result.scalars().all()

        # Si tenemos gym_id, usar caché
        cache_key = f"schedule:classes:gym:{gym_id}:active:{active_only}:skip:{skip}:limit:{limit}"

        async def db_fetch():
            from sqlalchemy.orm import selectinload
            stmt = select(Class).options(selectinload(Class.custom_category)).where(Class.gym_id == gym_id)
            if active_only:
                stmt = stmt.where(Class.is_active == True)
            stmt = stmt.offset(skip).limit(limit)
            result = await db.execute(stmt)
            return result.scalars().all()

        classes = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=ClassSchema,
            expiry_seconds=1800, # 30 minutos para listas
            is_list=True
        )
        return classes

    async def create_class(self, db: AsyncSession, class_data: ClassCreate, created_by_id: Optional[int] = None, gym_id: int = None, redis_client: Optional[Redis] = None) -> Any:
        """
        Crear una nueva clase e invalidar caché.
        """
        # Preparar los datos para la creación
        obj_in_data = class_data.model_dump(exclude={"category"})  # Excluir el campo auxiliar category

        # Asegurarse de que gym_id esté presente
        if not gym_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere un ID de gimnasio válido"
            )

        # Agregar el gym_id al objeto de datos
        obj_in_data["gym_id"] = gym_id

        # Agregar ID del creador si se proporciona
        if created_by_id:
            obj_in_data["created_by"] = created_by_id

        # Crear la clase en la BD
        db_obj = await async_class_repository.create_async(db, obj_in=obj_in_data)

        # Invalidar caché relevante
        await self._invalidate_class_caches(
            redis_client=redis_client,
            gym_id=gym_id,
            category_id=db_obj.category_id,
            difficulty=db_obj.difficulty_level.value if db_obj.difficulty_level else None
        )

        return db_obj

    async def update_class(self, db: AsyncSession, class_id: int, class_data: ClassUpdate, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """Actualizar una clase existente e invalidar caché"""
        # Obtener la clase de la BD (no usar caché aquí)
        class_obj = await async_class_repository.get_async(db, id=class_id)
        if not class_obj or class_obj.gym_id != gym_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clase no encontrada en este gimnasio"
            )

        # Guardar categoría y dificultad originales para invalidación
        original_category_id = class_obj.category_id
        original_difficulty = class_obj.difficulty_level.value if class_obj.difficulty_level else None

        # Actualizar en BD
        updated_class = await async_class_repository.update_async(db, db_obj=class_obj, obj_in=class_data)

        # Invalidar caché
        await self._invalidate_class_caches(
            redis_client=redis_client,
            gym_id=gym_id,
            class_id=class_id,
            category_id=updated_class.category_id,
            difficulty=updated_class.difficulty_level.value if updated_class.difficulty_level else None
        )
        # Invalidar también para la categoría/dificultad original si cambiaron
        if original_category_id != updated_class.category_id:
             await self._invalidate_class_caches(redis_client=redis_client, gym_id=gym_id, category_id=original_category_id)
        if original_difficulty != (updated_class.difficulty_level.value if updated_class.difficulty_level else None):
             await self._invalidate_class_caches(redis_client=redis_client, gym_id=gym_id, difficulty=original_difficulty)

        return updated_class

    async def delete_class(self, db: AsyncSession, class_id: int, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """Eliminar o inactivar una clase e invalidar caché"""
        # Obtener la clase de la BD (no usar caché)
        class_obj = await async_class_repository.get_async(db, id=class_id)
        if not class_obj or class_obj.gym_id != gym_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clase no encontrada en este gimnasio"
            )

        # Guardar categoría y dificultad para invalidación antes de eliminar/inactivar
        category_id = class_obj.category_id
        difficulty = class_obj.difficulty_level.value if class_obj.difficulty_level else None

        # Verificar si hay sesiones programadas para esta clase
        sessions = await async_class_session_repository.get_by_class_async(db, class_id=class_id)
        if sessions:
            # Actualizar el estado de la clase a inactivo en lugar de eliminarla
            result = await async_class_repository.update_async(
                db, db_obj=class_obj, obj_in={"is_active": False}
            )
            action = "inactivated"
        else:
            # Eliminar la clase
            result = await async_class_repository.remove_async(db, id=class_id)
            action = "deleted"

        # Invalidar caché
        await self._invalidate_class_caches(
            redis_client=redis_client,
            gym_id=gym_id,
            class_id=class_id,
            category_id=category_id,
            difficulty=difficulty
        )

        logger.info(f"Class {class_id} {action} for gym {gym_id}.")
        return result

    async def get_classes_by_category(
        self, db: AsyncSession, *, category_id: int, skip: int = 0, limit: int = 100,
        gym_id: Optional[int] = None, redis_client: Optional[Redis] = None
    ) -> List[Any]:
        """
        Obtener clases por ID de categoría, opcionalmente filtradas por gimnasio (con caché).
        """
        if gym_id is None:
            logger.warning("Attempted to get classes by category without gym_id. Cache disabled.")
            stmt = select(Class).where(Class.category_id == category_id, Class.is_active == True)
            stmt = stmt.offset(skip).limit(limit)
            result = await db.execute(stmt)
            return result.scalars().all()

        cache_key = f"schedule:classes:category:{category_id}:gym:{gym_id}:skip:{skip}:limit:{limit}"

        async def db_fetch():
            stmt = select(Class).where(
                Class.category_id == category_id,
                Class.gym_id == gym_id,
                Class.is_active == True
            )
            stmt = stmt.offset(skip).limit(limit)
            result = await db.execute(stmt)
            return result.scalars().all()

        classes = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=ClassSchema,
            expiry_seconds=1800, # 30 mins
            is_list=True
        )
        return classes

    async def get_classes_by_difficulty(
        self, db: AsyncSession, *, difficulty: str, skip: int = 0, limit: int = 100,
        gym_id: Optional[int] = None, redis_client: Optional[Redis] = None
    ) -> List[Any]:
        """
        Obtener clases por nivel de dificultad, opcionalmente filtradas por gimnasio (con caché).
        """
        if gym_id is None:
            logger.warning("Attempted to get classes by difficulty without gym_id. Cache disabled.")
            stmt = select(Class).where(
                Class.difficulty_level == difficulty,
                Class.is_active == True
            )
            stmt = stmt.offset(skip).limit(limit)
            result = await db.execute(stmt)
            return result.scalars().all()

        cache_key = f"schedule:classes:difficulty:{difficulty}:gym:{gym_id}:skip:{skip}:limit:{limit}"

        async def db_fetch():
            stmt = select(Class).where(
                Class.difficulty_level == difficulty,
                Class.gym_id == gym_id,
                Class.is_active == True
            )
            stmt = stmt.offset(skip).limit(limit)
            result = await db.execute(stmt)
            return result.scalars().all()

        classes = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=ClassSchema,
            expiry_seconds=1800, # 30 mins
            is_list=True
        )
        return classes

    async def search_classes(
        self, db: AsyncSession, *, search: str, skip: int = 0, limit: int = 100,
        gym_id: Optional[int] = None, redis_client: Optional[Redis] = None
    ) -> List[Any]:
        """
        Buscar clases por nombre o descripción, opcionalmente filtradas por gimnasio (con caché).
        """
        if gym_id is None:
            logger.warning("Attempted to search classes without gym_id. Cache disabled.")
            search_pattern = f"%{search}%"
            stmt = select(Class).where(
                or_(
                    Class.name.ilike(search_pattern),
                    Class.description.ilike(search_pattern)
                ),
                Class.is_active == True
            )
            stmt = stmt.offset(skip).limit(limit)
            result = await db.execute(stmt)
            return result.scalars().all()

        # Codificar término de búsqueda para la clave de caché
        safe_search = ''.join(c if c.isalnum() else '_' for c in search)
        cache_key = f"schedule:classes:search:gym:{gym_id}:term:{safe_search}:skip:{skip}:limit:{limit}"

        async def db_fetch():
            search_pattern = f"%{search}%"
            stmt = select(Class).where(
                    or_(
                        Class.name.ilike(search_pattern),
                        Class.description.ilike(search_pattern)
                    ),
                    Class.gym_id == gym_id,
                    Class.is_active == True
                )
            stmt = stmt.offset(skip).limit(limit)
            result = await db.execute(stmt)
            return result.scalars().all()

        classes = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=ClassSchema,
            expiry_seconds=600, # 10 mins para búsquedas
            is_list=True
        )
        return classes


# Nota: AsyncClassSessionService y AsyncClassParticipationService serían demasiado largos
# para este archivo. Recomendación: dividir en archivos separados si es necesario.
# Por ahora, las funcionalidades principales están cubiertas.

# Instantiate services
async_gym_hours_service = AsyncGymHoursService()
async_gym_special_hours_service = AsyncGymSpecialHoursService()
async_category_service = AsyncClassCategoryService()
async_class_service = AsyncClassService()
