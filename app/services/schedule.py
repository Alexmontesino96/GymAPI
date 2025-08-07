from typing import List, Optional, Dict, Any, Union
from datetime import datetime, time, timedelta, date
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
import asyncio
import json

from app.repositories.schedule import (
    gym_hours_repository,
    gym_special_hours_repository,
    class_repository,
    class_session_repository,
    class_participation_repository,
    class_category_repository
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
    # GymClass,
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
    GymSpecialHours
)

# --- Añadir importaciones para Caché --- 
import logging
from redis.asyncio import Redis
from app.services.cache_service import cache_service
from app.schemas.schedule import ClassCategoryCustom as ClassCategoryCustomSchema
from app.schemas.schedule import Class as ClassSchema # Añadir importación para Class
from app.schemas.schedule import ClassSession as ClassSessionSchema # Añadir importación para ClassSession
from app.schemas.schedule import ClassParticipation as ClassParticipationSchema # Añadir importación para ClassParticipation
from app.core.timezone_utils import is_session_in_future, get_current_time_in_gym_timezone
# --- Fin importaciones Caché --- 

# --- Añadir logger ---
logger = logging.getLogger(__name__)
# --- Fin Logger ---

class GymHoursService:
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
    
    def get_gym_hours_by_day(self, db: Session, day: int, gym_id: int) -> Any:
        """
        Obtener los horarios del gimnasio para un día específico.
        
        Args:
            db: Sesión de base de datos
            day: Día de la semana (0=Lunes, 6=Domingo)
            gym_id: ID del gimnasio
        """
        # Wrapper que llama a la versión cacheada con redis_client=None
        # Esto evita duplicar código y mantiene compatibilidad con código existente
        return asyncio.run(self.get_gym_hours_by_day_cached(db, day, gym_id, redis_client=None))
    
    async def get_gym_hours_by_day_cached(self, db: Session, day: int, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """
        Obtener los horarios del gimnasio para un día específico (con caché).
        
        Args:
            db: Sesión de base de datos
            day: Día de la semana (0=Lunes, 6=Domingo)
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional
        """
        if not redis_client:
            return self.get_gym_hours_by_day(db, day, gym_id)
            
        cache_key = f"gym_hours:day:{day}:gym:{gym_id}"
        tracking_set_key = f"cache_keys:gym_hours:{gym_id}"
        
        # Indica si el resultado vino de la BD
        fetched_from_db = False
        
        async def db_fetch():
            nonlocal fetched_from_db
            result = gym_hours_repository.get_by_day(db, day=day, gym_id=gym_id)
            # Si no hay resultados, creamos valores predeterminados
            if not result:
                result = gym_hours_repository.get_or_create_default(db, day=day, gym_id=gym_id)
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
    
    def get_all_gym_hours(self, db: Session, gym_id: int) -> List[Any]:
        """
        Obtener los horarios para todos los días de la semana.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
        """
        # Wrapper que llama a la versión cacheada con redis_client=None
        return asyncio.run(self.get_all_gym_hours_cached(db, gym_id, redis_client=None))
    
    async def get_all_gym_hours_cached(self, db: Session, gym_id: int, redis_client: Optional[Redis] = None) -> List[Any]:
        """
        Obtener los horarios para todos los días de la semana (con caché).
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional
        """
        if not redis_client:
            return self.get_all_gym_hours(db, gym_id)
            
        cache_key = f"gym_hours:all:gym:{gym_id}"
        tracking_set_key = f"cache_keys:gym_hours:{gym_id}"
        
        # Indica si el resultado vino de la BD
        fetched_from_db = False
        
        async def db_fetch():
            nonlocal fetched_from_db
            result = gym_hours_repository.get_all_days(db, gym_id=gym_id)
            # Comprobar si tenemos los 7 días de la semana
            if len(result) < 7:
                # Si faltan días, crear los que falten con valores predeterminados
                existing_days = {hour.day_of_week for hour in result}
                for day in range(7):
                    if day not in existing_days:
                        # Crear con valores predeterminados
                        new_day = gym_hours_repository.get_or_create_default(db, day=day, gym_id=gym_id)
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
        self, db: Session, day: int, gym_hours_data: Union[GymHoursCreate, GymHoursUpdate],
        gym_id: int, redis_client: Optional[Redis] = None
    ) -> Any:
        """
        Crear o actualizar los horarios del gimnasio para un día específico (con invalidación de caché).
        
        Args:
            db: Sesión de base de datos
            day: Día de la semana (0=Lunes, 6=Domingo)
            gym_hours_data: Datos del horario a crear o actualizar
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional
        """
        # Ejecutar operación de creación/actualización
        result = self.create_or_update_gym_hours(db, day, gym_hours_data, gym_id)
        
        # Invalidar caché si la operación fue exitosa
        if result and redis_client:
            await self._invalidate_gym_hours_cache(redis_client, gym_id, day=day)
            
        return result
    
    def _create_default_hours(self, db: Session, gym_id: int) -> List[Any]:
        """
        Crea los horarios predeterminados para un gimnasio.
        Método interno usado para reemplazar initialize_default_hours.
        
        Args:
            db: Sesión de base de datos
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
            existing_hours = gym_hours_repository.get_by_day(db, day=day, gym_id=gym_id)
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
                    hours = gym_hours_repository.update(db, db_obj=existing_hours, obj_in=update_data)
                else:
                    hours = existing_hours
            else:
                # Si no existen, crear nuevos usando obj_in_data (que ya tiene gym_id)
                hours = gym_hours_repository.create(db, obj_in=obj_in_data)
            
            default_hours.append(hours)
        
        return default_hours
    
    def get_hours_for_date(self, db: Session, date_value: date, gym_id: int) -> Dict[str, Any]:
        """
        Obtener los horarios del gimnasio para una fecha específica.
        
        Args:
            db: Sesión de base de datos
            date_value: Fecha a consultar
            gym_id: ID del gimnasio
        """
        # Wrapper que llama a la versión cacheada con redis_client=None
        return asyncio.run(self.get_hours_for_date_cached(db, date_value, gym_id, redis_client=None))
    
    async def get_hours_for_date_cached(self, db: Session, date_value: date, gym_id: int, redis_client: Optional[Redis] = None) -> Dict[str, Any]:
        """
        Obtener los horarios del gimnasio para una fecha específica (con caché).
        
        Args:
            db: Sesión de base de datos
            date_value: Fecha a consultar
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional
        """
        if not redis_client:
            return await self._get_hours_for_date_internal(db, date_value, gym_id)
            
        date_str = date_value.isoformat()
        cache_key = f"gym_hours:date:{date_str}:gym:{gym_id}"
        tracking_set_key = f"cache_keys:gym_hours:{gym_id}"
        
        # Indica si el resultado vino de la BD
        fetched_from_db = False
        
        async def db_fetch():
            nonlocal fetched_from_db
            result = await self._get_hours_for_date_internal(db, date_value, gym_id)
            fetched_from_db = True
            return result
            
        # Esta función no usa un modelo de Pydantic directamente, sino un diccionario de resultados
        # Usamos expiry_seconds más corto ya que este dato puede cambiar con más frecuencia
        # debido a la configuración de horarios especiales
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
    
    def create_or_update_gym_hours(
        self, db: Session, day: int, gym_hours_data: Union[GymHoursCreate, GymHoursUpdate],
        gym_id: int
    ) -> Any:
        """
        Crear o actualizar los horarios del gimnasio para un día específico.
        
        Args:
            db: Sesión de base de datos
            day: Día de la semana (0=Lunes, 6=Domingo)
            gym_hours_data: Datos del horario a crear o actualizar
            gym_id: ID del gimnasio
        """
        # Verificar si ya existen horarios para este día
        existing_hours = gym_hours_repository.get_by_day(db, day=day, gym_id=gym_id)
        
        if existing_hours:
            # Actualizar horarios existentes
            return gym_hours_repository.update(
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
            
            return gym_hours_repository.create(db, obj_in=obj_in)
    
    def _create_default_hours(self, db: Session, gym_id: int) -> List[Any]:
        """
        Crea los horarios predeterminados para un gimnasio.
        Método interno usado para reemplazar initialize_default_hours.
        
        Args:
            db: Sesión de base de datos
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
            existing_hours = gym_hours_repository.get_by_day(db, day=day, gym_id=gym_id)
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
                    hours = gym_hours_repository.update(db, db_obj=existing_hours, obj_in=update_data)
                else:
                    hours = existing_hours
            else:
                # Si no existen, crear nuevos usando obj_in_data (que ya tiene gym_id)
                hours = gym_hours_repository.create(db, obj_in=obj_in_data)
            
            default_hours.append(hours)
        
        return default_hours
    
    def get_hours_for_date(self, db: Session, date_value: date, gym_id: int) -> Dict[str, Any]:
        """
        Obtener los horarios del gimnasio para una fecha específica.
        
        Args:
            db: Sesión de base de datos
            date_value: Fecha a consultar
            gym_id: ID del gimnasio
        """
        # Wrapper que llama a la versión cacheada con redis_client=None
        return asyncio.run(self.get_hours_for_date_cached(db, date_value, gym_id, redis_client=None))

    # Implementación interna para la versión cacheada
    async def _get_hours_for_date_internal(self, db: Session, date_value: date, gym_id: int) -> Dict[str, Any]:
        """
        Implementación interna del método get_hours_for_date para ser usada por get_hours_for_date_cached.
        
        Args:
            db: Sesión de base de datos
            date_value: Fecha a consultar
            gym_id: ID del gimnasio
        """
        # Verificar si hay horarios especiales para esta fecha
        special_hours = gym_special_hours_repository.get_by_date(db, date_value=date_value, gym_id=gym_id)
        
        # Obtener día de la semana (0=Lunes, 6=Domingo)
        day_of_week = date_value.weekday()
        
        # Obtener horarios regulares para este día
        regular_hours = gym_hours_repository.get_by_day(db, day=day_of_week, gym_id=gym_id)
        if not regular_hours:
            # Si no hay horarios regulares, crear con valores predeterminados
            regular_hours = gym_hours_repository.get_or_create_default(db, day=day_of_week, gym_id=gym_id)
        
        # Preparar la respuesta con la información completa y mejorada
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
        
        # Si hay horarios especiales, incluirlos en la respuesta
        if special_hours:
            result["special_hours"] = {
                "id": special_hours.id,
                "open_time": special_hours.open_time,
                "close_time": special_hours.close_time,
                "is_closed": special_hours.is_closed,
                "description": special_hours.description
            }
            
        # Determinar el horario efectivo para esta fecha (especial o regular)
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

    def apply_defaults_to_range(
        self, db: Session, start_date: date, end_date: date, gym_id: int, overwrite_existing: bool = False
    ) -> List[GymSpecialHours]:
        """
        Aplica el horario semanal predeterminado a un rango de fechas específicas.
        
        Args:
            db: Sesión de base de datos
            start_date: Fecha de inicio del rango
            end_date: Fecha de fin del rango
            gym_id: ID del gimnasio
            overwrite_existing: Si es True, sobrescribe las excepciones manuales existentes
            
        Returns:
            Lista de objetos GymSpecialHours creados o actualizados
        """
        # Wrapper que llama a la versión cacheada con redis_client=None
        return asyncio.run(self.apply_defaults_to_range_cached(db, start_date, end_date, gym_id, overwrite_existing, redis_client=None))
        
    async def apply_defaults_to_range_cached(
        self, db: Session, start_date: date, end_date: date, gym_id: int, 
        overwrite_existing: bool = False, redis_client: Optional[Redis] = None
    ) -> List[GymSpecialHours]:
        """
        Asegura que existan los horarios semanales base para el gimnasio.
        Ya NO crea registros especiales - solo valida/crea la plantilla semanal.
        
        Args:
            db: Sesión de base de datos
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
            weekly_hours = self._create_default_hours(db, gym_id=gym_id)
            
            # Invalidar caché de horarios semanales si se crearon nuevos
            if redis_client:
                await self._invalidate_gym_hours_cache(redis_client, gym_id)
        
        # Ya no creamos registros especiales
        # Simplemente devolvemos una lista vacía para mantener compatibilidad con la API
        return []
        
    def get_schedule_for_date_range(
        self, db: Session, start_date: date, end_date: date, gym_id: int
    ) -> List[Dict[str, Any]]:
        """
        Obtener el horario del gimnasio para un rango de fechas.
        
        Args:
            db: Sesión de base de datos
            start_date: Fecha de inicio
            end_date: Fecha de fin
            gym_id: ID del gimnasio
        """
        # Wrapper que llama a la versión cacheada con redis_client=None
        return asyncio.run(self.get_schedule_for_date_range_cached(db, start_date, end_date, gym_id, redis_client=None))
        
    async def get_schedule_for_date_range_cached(
        self, db: Session, start_date: date, end_date: date, gym_id: int, redis_client: Optional[Redis] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtener el horario del gimnasio para un rango de fechas (con caché).
        
        Args:
            db: Sesión de base de datos
            start_date: Fecha de inicio
            end_date: Fecha de fin
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional
        """
        # Si no hay Redis, o el rango es muy grande, procesar sin caché
        if not redis_client or (end_date - start_date).days > 31:  # Si es más de un mes, no cachear
            # Implementación directa sin caché para evitar recursión
            # Verificar que el rango de fechas sea válido
            if end_date < start_date:
                raise ValueError("La fecha de fin no puede ser anterior a la fecha de inicio")
                
            # Obtener los horarios especiales para este rango
            special_hours = gym_special_hours_repository.get_by_date_range(
                db, start_date=start_date, end_date=end_date, gym_id=gym_id
            )
            
            # Crear un diccionario de horarios especiales por fecha para acceso rápido
            special_hours_dict = {str(hour.date): hour for hour in special_hours}
            
            # Obtener los horarios semanales predeterminados (usando la versión cacheada)
            weekly_hours = await self.get_all_gym_hours_cached(db, gym_id=gym_id, redis_client=None)
            if not weekly_hours:
                # Si no hay horarios semanales, crearlos con valores predeterminados
                weekly_hours = self._create_default_hours(db, gym_id=gym_id)
                
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


class GymSpecialHoursService:
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

    async def get_special_hours_cached(self, db: Session, special_day_id: int, redis_client: Optional[Redis] = None) -> Any:
        """
        Obtener un día especial por ID (con caché).
        
        Args:
            db: Sesión de base de datos
            special_day_id: ID del día especial
            redis_client: Cliente Redis opcional
        """
        if not redis_client:
            return self.get_special_hours(db, special_day_id)
            
        cache_key = f"special_day:detail:{special_day_id}"
        
        async def db_fetch():
            return gym_special_hours_repository.get(db, id=special_day_id)
        
        special_day = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=GymSpecialHours,
            expiry_seconds=3600 * 12, # 12 horas
            is_list=False
        )
        
        return special_day
    
    def get_special_hours(self, db: Session, special_day_id: int) -> Any:
        """Obtener un día especial por ID (versión no-caché)"""
        return gym_special_hours_repository.get(db, id=special_day_id)
    
    async def get_special_hours_by_date_cached(self, db: Session, date_value: date, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """
        Obtener horarios especiales para una fecha específica (con caché).
        
        Args:
            db: Sesión de base de datos
            date_value: Fecha a consultar
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional
        """
        if not redis_client:
            return self.get_special_hours_by_date(db, date_value, gym_id)
            
        date_str = date_value.isoformat()
        cache_key = f"special_day:date:{date_str}:gym:{gym_id}"
        tracking_set_key = f"cache_keys:special_days:{gym_id}"
        
        # Indica si el resultado vino de la BD
        fetched_from_db = False
        
        async def db_fetch():
            nonlocal fetched_from_db
            result = gym_special_hours_repository.get_by_date(db, date_value=date_value, gym_id=gym_id)
            fetched_from_db = True
            return result
        
        special_day = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=GymSpecialHours,
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
    
    def get_special_hours_by_date(self, db: Session, date_value: date, gym_id: int) -> Any:
        """
        Obtener horarios especiales para una fecha específica (versión no-caché).
        
        Args:
            db: Sesión de base de datos
            date_value: Fecha a consultar
            gym_id: ID del gimnasio
        """
        return gym_special_hours_repository.get_by_date(db, date_value=date_value, gym_id=gym_id)
    
    async def get_upcoming_special_days_cached(self, db: Session, limit: int = 10, gym_id: int = None, redis_client: Optional[Redis] = None) -> List[Any]:
        """
        Obtener los próximos días especiales (con caché).
        
        Args:
            db: Sesión de base de datos
            limit: Número máximo de registros a devolver
            gym_id: ID del gimnasio para filtrar
            redis_client: Cliente Redis opcional
        """
        if not redis_client or not gym_id:
            return self.get_upcoming_special_days(db, limit, gym_id)
            
        cache_key = f"special_days:upcoming:gym:{gym_id}:limit:{limit}"
        tracking_set_key = f"cache_keys:special_days:{gym_id}"
        
        # Indica si el resultado vino de la BD
        fetched_from_db = False
        
        async def db_fetch():
            nonlocal fetched_from_db
            result = gym_special_hours_repository.get_upcoming_special_days(db, limit=limit, gym_id=gym_id)
            fetched_from_db = True
            return result
        
        special_days = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=GymSpecialHours,
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
    
    def get_upcoming_special_days(self, db: Session, limit: int = 10, gym_id: int = None) -> List[Any]:
        """
        Obtener los próximos días especiales (versión no-caché).
        
        Args:
            db: Sesión de base de datos
            limit: Número máximo de registros a devolver
            gym_id: ID del gimnasio para filtrar
        """
        return gym_special_hours_repository.get_upcoming_special_days(db, limit=limit, gym_id=gym_id)
    
    async def create_special_day_cached(self, db: Session, special_hours_data: GymSpecialHoursCreate, gym_id: int = None, redis_client: Optional[Redis] = None) -> Any:
        """
        Crear un nuevo día especial e invalidar caché.
        
        Args:
            db: Sesión de base de datos
            special_hours_data: Datos del día especial a crear
            gym_id: ID del gimnasio al que pertenece el día especial
            redis_client: Cliente Redis opcional
        """
        # Crear el día especial
        result = self.create_special_day(db, special_hours_data, gym_id)
        
        # Invalidar cachés afectadas
        if result and redis_client:
            await self._invalidate_special_hours_cache(
                redis_client, 
                gym_id, 
                date_value=result.date
            )
            
        return result
    
    def create_special_day(self, db: Session, special_hours_data: GymSpecialHoursCreate, gym_id: int = None) -> Any:
        """
        Crear un nuevo día especial (versión no-caché)
        
        Args:
            db: Sesión de base de datos
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
        return gym_special_hours_repository.create(db, obj_in=obj_in_data)
    
    async def update_special_day_cached(
        self, db: Session, special_day_id: int, special_hours_data: GymSpecialHoursUpdate, redis_client: Optional[Redis] = None
    ) -> Any:
        """
        Actualizar un día especial existente e invalidar caché.
        
        Args:
            db: Sesión de base de datos
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
        result = self.update_special_day(db, special_day_id, special_hours_data)
        
        # Invalidar cachés afectadas
        if result and redis_client:
            await self._invalidate_special_hours_cache(
                redis_client, 
                special_day.gym_id, 
                special_day_id=special_day_id,
                date_value=special_day.date
            )
            
        return result
    
    def update_special_day(
        self, db: Session, special_day_id: int, special_hours_data: GymSpecialHoursUpdate
    ) -> Any:
        """
        Actualizar un día especial existente (versión no-caché)
        
        Args:
            db: Sesión de base de datos
            special_day_id: ID del día especial a actualizar
            special_hours_data: Datos a actualizar
        """
        special_day = gym_special_hours_repository.get(db, id=special_day_id)
        if not special_day:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Día especial no encontrado"
            )
        
        return gym_special_hours_repository.update(
            db, db_obj=special_day, obj_in=special_hours_data
        )
    
    async def delete_special_day_cached(self, db: Session, special_day_id: int, redis_client: Optional[Redis] = None) -> Any:
        """
        Eliminar un día especial e invalidar caché.
        
        Args:
            db: Sesión de base de datos
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
        result = self.delete_special_day(db, special_day_id)
        
        # Invalidar cachés afectadas
        if result and redis_client:
            await self._invalidate_special_hours_cache(
                redis_client, 
                special_day.gym_id, 
                special_day_id=special_day_id,
                date_value=special_day.date
            )
            
        return result
    
    def delete_special_day(self, db: Session, special_day_id: int) -> Any:
        """
        Eliminar un día especial (versión no-caché)
        
        Args:
            db: Sesión de base de datos
            special_day_id: ID del día especial a eliminar
        """
        special_day = gym_special_hours_repository.get(db, id=special_day_id)
        if not special_day:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Día especial no encontrado"
            )
        
        return gym_special_hours_repository.remove(db, id=special_day_id)


# --- Añadir Servicio para Categorías Personalizadas --- 
class ClassCategoryService:
    # --- Añadir método helper para invalidación --- 
    async def _invalidate_custom_category_caches(self, redis_client: Redis, gym_id: int, category_id: Optional[int] = None):
        if not redis_client:
            return
        logger = logging.getLogger(__name__)
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
    
    async def get_category(self, db: Session, category_id: int, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """Obtener una categoría por ID (con caché) asegurando que pertenece al gimnasio"""
        
        cache_key = f"category:custom:detail:{category_id}"
        
        async def db_fetch():
            # Verificar que la categoría existe en la BD
            category_db = class_category_repository.get(db, id=category_id)
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
    
    async def get_categories_by_gym(self, db: Session, gym_id: int, active_only: bool = True, redis_client: Optional[Redis] = None) -> List[Any]:
        """Obtener categorías para un gimnasio específico (con caché) y registrar la clave en un Set."""
        
        cache_key = f"categories:custom:gym:{gym_id}:active:{active_only}"
        tracking_set_key = f"cache_keys:categories:gym:{gym_id}"
        
        async def db_fetch():
            if active_only:
                return class_category_repository.get_active_categories(db, gym_id=gym_id)
            return class_category_repository.get_by_gym(db, gym_id=gym_id)

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
    
    async def create_category(self, db: Session, category_data: ClassCategoryCustomCreate, gym_id: int, created_by_id: Optional[int] = None, redis_client: Optional[Redis] = None) -> Any:
        """Crear una nueva categoría personalizada e invalidar caché"""
        existing_category = class_category_repository.get_by_name_and_gym(
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
            db.commit()
            db.refresh(db_obj)
            # Invalidar caché después del commit exitoso
            await self._invalidate_custom_category_caches(redis_client, gym_id=gym_id)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al guardar la categoría en la base de datos"
            )
            
        return db_obj
    
    async def update_category(self, db: Session, category_id: int, category_data: ClassCategoryCustomUpdate, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """Actualizar una categoría existente e invalidar caché"""
        # Usar get_category sin caché para obtener el objeto a actualizar
        # No podemos usar la versión cacheada porque necesitamos el objeto de SQLAlchemy
        category = class_category_repository.get(db, id=category_id)
        if not category or category.gym_id != gym_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoría no encontrada en este gimnasio"
            )
        
        if category_data.name and category_data.name != category.name:
            existing_category = class_category_repository.get_by_name_and_gym(
                db, name=category_data.name, gym_id=gym_id
            )
            if existing_category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ya existe otra categoría con este nombre en este gimnasio"
                )
        
        updated_category = class_category_repository.update(db, db_obj=category, obj_in=category_data)
        # Invalidar caché después de la actualización
        await self._invalidate_custom_category_caches(redis_client, gym_id=gym_id, category_id=category_id)
        return updated_category
    
    async def delete_category(self, db: Session, category_id: int, gym_id: int, redis_client: Optional[Redis] = None) -> None:
        """Eliminar/inactivar una categoría e invalidar caché"""
        # Usar get_category sin caché para la verificación inicial
        category = class_category_repository.get(db, id=category_id)
        if not category or category.gym_id != gym_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoría no encontrada en este gimnasio"
            )
        
        classes_with_category = db.query(Class.id).filter(Class.category_id == category_id).count() # Optimizado para contar
        
        try:
            if classes_with_category > 0:
                class_category_repository.update(
                    db, db_obj=category, obj_in={"is_active": False}
                )
            else:
                class_category_repository.remove(db, id=category_id)
            # Invalidar caché después de eliminar/inactivar
            await self._invalidate_custom_category_caches(redis_client, gym_id=gym_id, category_id=category_id)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al eliminar/inactivar categoría: {e}"
            )
# --- Fin Servicio --- 

class ClassService:
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
        patterns_to_delete.append(f"schedule:classes:all:*") # Por si acaso, aunque no la estamos usando ahora mismo
        
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
    
    async def get_class(self, db: Session, class_id: int, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """Obtener una clase por ID (con caché), asegurando que pertenece al gimnasio"""
        
        cache_key = f"schedule:class:detail:{class_id}"
        
        async def db_fetch():
            class_obj = class_repository.get(db, id=class_id)
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
        self, db: Session, skip: int = 0, limit: int = 100, active_only: bool = True,
        gym_id: Optional[int] = None, redis_client: Optional[Redis] = None
    ) -> List[Any]:
        """
        Obtener todas las clases, opcionalmente filtradas por gimnasio (con caché).
        """
        # Si no hay gym_id, no usar caché y ejecutar consulta directa
        if gym_id is None:
            logger.warning("Attempted to get classes without gym_id. Cache disabled and no gym filtering applied.")
            query = db.query(Class)
            if active_only:
                query = query.filter(Class.is_active == True)
            return query.offset(skip).limit(limit).all()
        
        # Si tenemos gym_id, usar caché
        cache_key = f"schedule:classes:gym:{gym_id}:active:{active_only}:skip:{skip}:limit:{limit}"
        
        async def db_fetch():
            query = db.query(Class).filter(Class.gym_id == gym_id)
            if active_only:
                query = query.filter(Class.is_active == True)
            return query.offset(skip).limit(limit).all()
    
        classes = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=ClassSchema,
            expiry_seconds=1800, # 30 minutos para listas
            is_list=True
        )
        return classes
    
    async def create_class(self, db: Session, class_data: ClassCreate, created_by_id: Optional[int] = None, gym_id: int = None, redis_client: Optional[Redis] = None) -> Any:
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
        db_obj = class_repository.create(db, obj_in=obj_in_data)
        
        # Invalidar caché relevante
        await self._invalidate_class_caches(
            redis_client=redis_client, 
            gym_id=gym_id, 
            category_id=db_obj.category_id, 
            difficulty=db_obj.difficulty_level.value if db_obj.difficulty_level else None
        )
        
        return db_obj
    
    async def update_class(self, db: Session, class_id: int, class_data: ClassUpdate, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """Actualizar una clase existente e invalidar caché"""
        # Obtener la clase de la BD (no usar caché aquí)
        class_obj = class_repository.get(db, id=class_id)
        if not class_obj or class_obj.gym_id != gym_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clase no encontrada en este gimnasio"
            )
        
        # Guardar categoría y dificultad originales para invalidación
        original_category_id = class_obj.category_id
        original_difficulty = class_obj.difficulty_level.value if class_obj.difficulty_level else None
        
        # Actualizar en BD
        updated_class = class_repository.update(db, db_obj=class_obj, obj_in=class_data)
        
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
    
    async def delete_class(self, db: Session, class_id: int, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """Eliminar o inactivar una clase e invalidar caché"""
        # Obtener la clase de la BD (no usar caché)
        class_obj = class_repository.get(db, id=class_id)
        if not class_obj or class_obj.gym_id != gym_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clase no encontrada en este gimnasio"
            )
        
        # Guardar categoría y dificultad para invalidación antes de eliminar/inactivar
        category_id = class_obj.category_id
        difficulty = class_obj.difficulty_level.value if class_obj.difficulty_level else None
        
        # Verificar si hay sesiones programadas para esta clase
        sessions = class_session_repository.get_by_class(db, class_id=class_id)
        if sessions:
            # Actualizar el estado de la clase a inactivo en lugar de eliminarla
            result = class_repository.update(
                db, db_obj=class_obj, obj_in={"is_active": False}
            )
            action = "inactivated"
        else:
            # Eliminar la clase
            result = class_repository.remove(db, id=class_id)
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
        return result # Devuelve el objeto actualizado o None si se eliminó
    
    async def get_classes_by_category(
        self, db: Session, *, category_id: int, skip: int = 0, limit: int = 100,
        gym_id: Optional[int] = None, redis_client: Optional[Redis] = None
    ) -> List[Any]:
        """
        Obtener clases por ID de categoría, opcionalmente filtradas por gimnasio (con caché).
        """
        if gym_id is None:
            logger.warning("Attempted to get classes by category without gym_id. Cache disabled.")
            query = db.query(Class).filter(Class.category_id == category_id, Class.is_active == True)
            return query.offset(skip).limit(limit).all()
            
        cache_key = f"schedule:classes:category:{category_id}:gym:{gym_id}:skip:{skip}:limit:{limit}"
        
        async def db_fetch():
            query = db.query(Class).filter(
                Class.category_id == category_id, 
                Class.gym_id == gym_id, 
                Class.is_active == True
                )
            return query.offset(skip).limit(limit).all()
    
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
        self, db: Session, *, difficulty: str, skip: int = 0, limit: int = 100,
        gym_id: Optional[int] = None, redis_client: Optional[Redis] = None
    ) -> List[Any]:
        """
        Obtener clases por nivel de dificultad, opcionalmente filtradas por gimnasio (con caché).
        """
        if gym_id is None:
            logger.warning("Attempted to get classes by difficulty without gym_id. Cache disabled.")
            
            return query.offset(skip).limit(limit).all()
            
        cache_key = f"schedule:classes:difficulty:{difficulty}:gym:{gym_id}:skip:{skip}:limit:{limit}"
        
        async def db_fetch():
            query = db.query(Class).filter(
                Class.difficulty_level == difficulty, 
                Class.gym_id == gym_id, 
                Class.is_active == True
            )
            return query.offset(skip).limit(limit).all()
    
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
        self, db: Session, *, search: str, skip: int = 0, limit: int = 100,
        gym_id: Optional[int] = None, redis_client: Optional[Redis] = None
    ) -> List[Any]:
        """
        Buscar clases por nombre o descripción, opcionalmente filtradas por gimnasio (con caché).
        """
        if gym_id is None:
            logger.warning("Attempted to search classes without gym_id. Cache disabled.")
            search_pattern = f"%{search}%"
            query = db.query(Class).filter(
                or_(
                    Class.name.ilike(search_pattern),
                    Class.description.ilike(search_pattern)
                ),
                Class.is_active == True
            )
            return query.offset(skip).limit(limit).all()
            
        # Codificar término de búsqueda para la clave de caché
        safe_search = ''.join(c if c.isalnum() else '_' for c in search)
        cache_key = f"schedule:classes:search:gym:{gym_id}:term:{safe_search}:skip:{skip}:limit:{limit}"
        
        async def db_fetch():
            search_pattern = f"%{search}%"
            query = db.query(Class).filter(
                    or_(
                        Class.name.ilike(search_pattern),
                        Class.description.ilike(search_pattern)
                    ),
                    Class.gym_id == gym_id,
                    Class.is_active == True
                )
            return query.offset(skip).limit(limit).all()
        
        classes = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=ClassSchema,
            expiry_seconds=600, # 10 mins para búsquedas
            is_list=True
        )
        return classes


class ClassSessionService:
    async def get_session(self, db: Session, session_id: int, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """Obtener una sesión por ID con caché"""
        # Verificar que la sesión pertenece al gimnasio
        session = class_session_repository.get(db, id=session_id)
        if not session or session.gym_id != gym_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión no encontrada en este gimnasio"
            )
        
        # Si no hay redis_client, devolver directamente
        if not redis_client:
            return session
        
        cache_key = f"schedule:session:detail:{session_id}"
        
        async def db_fetch():
            return class_session_repository.get(db, id=session_id)
        
        # Usar el servicio de caché genérico
        from app.services.cache_service import cache_service
        from app.schemas.schedule import ClassSession
        
        cached_session = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=ClassSession,
            expiry_seconds=1800,  # 30 minutos para sesiones individuales
            is_list=False
        )
        
        return cached_session
    
    async def get_session_with_details(self, db: Session, session_id: int, gym_id: int, redis_client: Optional[Redis] = None) -> Dict[str, Any]:
        """Obtener una sesión con detalles completos (clase, trainer, participantes) con caché"""
        # Verificar que la sesión pertenece al gimnasio
        session = class_session_repository.get(db, id=session_id)
        if not session or session.gym_id != gym_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión no encontrada en este gimnasio"
            )
        
        # Si no hay redis_client, usar versión sin caché
        if not redis_client:
            return class_session_repository.get_with_availability(db, session_id=session_id)
        
        cache_key = f"schedule:session:detail_with_availability:{session_id}"
        
        async def db_fetch():
            raw = class_session_repository.get_with_availability(db, session_id=session_id)

            if not raw:
                return None

            # Convertir los modelos ORM a esquemas serializables
            from app.schemas.schedule import ClassSession, Class

            try:
                raw["session"] = ClassSession.model_validate(raw["session"]).model_dump()
                raw["class"] = Class.model_validate(raw["class"]).model_dump()
            except Exception as e:
                logger.error(f"Error al convertir modelos a dict para caché: {e}")

            return raw
        
        # Usar el servicio de caché genérico
        from app.services.cache_service import cache_service
        
        # Para este caso, no podemos usar un schema específico porque devuelve un dict complejo
        # Usamos serialización JSON directa
        session_details = await cache_service.get_or_set_json(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            expiry_seconds=900,  # 15 minutos para detalles con disponibilidad
        )
        
        return session_details
    
    async def create_session(
        self, db: Session, session_data: ClassSessionCreate, gym_id: int, created_by_id: Optional[int] = None, redis_client: Optional[Redis] = None
    ) -> Any:
        """Crear una nueva sesión de clase e invalidar caché"""
        # Nota: Añadir gym_id y redis_client
        
        # Verificar que la clase exista, esté activa y pertenezca al gimnasio
        class_obj = class_repository.get(db, id=session_data.class_id)
        if not class_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clase no encontrada"
            )
        if not class_obj.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pueden crear sesiones para una clase inactiva"
            )
        if class_obj.gym_id != gym_id:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="La clase especificada no pertenece a este gimnasio"
            )
        
        # Obtener el gimnasio para su timezone
        from app.repositories.gym import gym_repository
        gym = gym_repository.get(db, id=gym_id)
        if not gym:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Gimnasio no encontrado"
            )
        
        # Calcular hora de fin si no se proporciona
        obj_in_data = session_data.model_dump()
        if not obj_in_data.get("end_time") and class_obj.duration:
            start_time = obj_in_data.get("start_time")
            if start_time:
                end_time = start_time + timedelta(minutes=class_obj.duration)
                obj_in_data["end_time"] = end_time
        
        # Convertir tiempos de hora local del gimnasio a UTC
        start_time_local = obj_in_data.get("start_time")
        end_time_local = obj_in_data.get("end_time")
        
        if start_time_local and end_time_local:
            # Convertir a UTC usando la timezone del gimnasio
            from app.core.timezone_utils import convert_gym_time_to_utc
            obj_in_data["start_time"] = convert_gym_time_to_utc(start_time_local, gym.timezone)
            obj_in_data["end_time"] = convert_gym_time_to_utc(end_time_local, gym.timezone)
        
        # Agregar ID del creador si se proporciona
        if created_by_id:
            obj_in_data["created_by"] = created_by_id
        
        # Asegurar que gym_id esté presente y sea el correcto
        obj_in_data["gym_id"] = gym_id
        
        # Crear la sesión
        created_session = class_session_repository.create(
            db, obj_in=ClassSessionCreate(**obj_in_data)
        )
    
        # Invalidar cachés relevantes (ej. listas de sesiones futuras, por fecha, por trainer, etc.)
        await self._invalidate_session_caches(redis_client, gym_id=gym_id, trainer_id=created_session.trainer_id, class_id=created_session.class_id)
        
        return created_session
    
    # Añadir método helper para invalidar caché de sesión
    async def _invalidate_session_caches(self, redis_client: Optional[Redis], gym_id: int, session_id: Optional[int] = None, trainer_id: Optional[int] = None, class_id: Optional[int] = None):
        """
        Invalidar cachés de sesiones de manera inteligente usando tracking sets.
        """
        if not redis_client:
            return
            
        from app.services.cache_service import cache_service
        
        keys_to_delete = []
        tracking_sets_to_process = []

        # Cachés específicos de sesión
        if session_id:
            keys_to_delete.extend([
                f"schedule:session:detail:{session_id}",
                f"schedule:session:detail_with_availability:{session_id}",
                f"schedule:participations:session:{session_id}:gym:{gym_id}:*"
            ])
        
        # Tracking sets a procesar para invalidación masiva
        tracking_sets_to_process.append(f"cache_keys:sessions:{gym_id}")
        
        if trainer_id:
            tracking_sets_to_process.append(f"cache_keys:sessions:trainer:{trainer_id}")
            
        if class_id:
            tracking_sets_to_process.append(f"cache_keys:sessions:class:{class_id}")
        
        try:
            # Eliminar claves específicas
            if keys_to_delete:
                # Separar claves directas de patrones
                direct_keys = [k for k in keys_to_delete if '*' not in k]
                pattern_keys = [k for k in keys_to_delete if '*' in k]
                
                if direct_keys:
                    deleted_keys = await redis_client.delete(*direct_keys)
                    logger.debug(f"Invalidated {deleted_keys} direct session keys: {direct_keys}")
                
                # Procesar patrones
                for pattern in pattern_keys:
                    deleted_count = await cache_service.delete_pattern(redis_client, pattern)
                    logger.debug(f"Invalidated {deleted_count} keys with pattern: {pattern}")
            
            # Procesar tracking sets para invalidación inteligente
            total_invalidated = 0
            for tracking_set in tracking_sets_to_process:
                try:
                    # Obtener todas las claves del tracking set
                    cached_keys = await redis_client.smembers(tracking_set)
                    if cached_keys:
                        # Convertir bytes a strings si es necesario
                        if isinstance(next(iter(cached_keys)), bytes):
                            cached_keys = [key.decode('utf-8') for key in cached_keys]
                        
                        # Eliminar las claves
                        deleted_count = await redis_client.delete(*cached_keys)
                        total_invalidated += deleted_count
                        
                        # Limpiar el tracking set
                        await redis_client.delete(tracking_set)
                        
                        logger.debug(f"Invalidated {deleted_count} cached keys from tracking set {tracking_set}")
                    
                except Exception as set_error:
                    logger.warning(f"Error processing tracking set {tracking_set}: {set_error}")
            
            if total_invalidated > 0:
                logger.info(f"Total invalidated session cache keys: {total_invalidated}")
            
        except Exception as e:
            logger.error(f"Error invalidating session caches for gym {gym_id}: {e}", exc_info=True)

    async def create_recurring_sessions(
        self, db: Session, 
        base_session_data: ClassSessionCreate, 
        start_date: date,
        end_date: date,
        days_of_week: List[int],  # 0=Lunes, 1=Martes, etc.
        created_by_id: Optional[int] = None,
        gym_id: int = None, # Añadir gym_id
        redis_client: Optional[Redis] = None # Añadir redis_client
    ) -> List[Any]:
        """Crear sesiones recurrentes basadas en días de la semana e invalidar caché"""
        if not gym_id:
             raise HTTPException(status_code=400, detail="Gym ID is required")

        # Verificar que la clase exista, esté activa y pertenezca al gimnasio
        class_obj = class_repository.get(db, id=base_session_data.class_id)
        if not class_obj or class_obj.gym_id != gym_id or not class_obj.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Clase inválida, inactiva o no pertenece a este gimnasio"
            )
        
        # Obtener el gimnasio para su timezone
        from app.repositories.gym import gym_repository
        gym = gym_repository.get(db, id=gym_id)
        if not gym:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Gimnasio no encontrado"
            )
        
        # Preparar datos base para las sesiones
        session_base_data = base_session_data.model_dump()
        session_base_data["gym_id"] = gym_id # Asegurar gym_id
        if created_by_id:
            session_base_data["created_by"] = created_by_id
            
        # Marcar que son sesiones recurrentes
        session_base_data["is_recurring"] = True
        session_base_data["recurrence_pattern"] = f"WEEKLY:{','.join(map(str, days_of_week))}"
        
        # Obtener la hora de inicio y fin de la sesión base
        base_start_time = session_base_data["start_time"]
        base_end_time = session_base_data["end_time"]
        
        # Necesitamos solo la hora/minutos, no la fecha
        base_start_hour = base_start_time.hour
        base_start_minute = base_start_time.minute
        
        # Si end_time está definido, extraer también su hora/minutos
        if base_end_time:
            base_end_hour = base_end_time.hour
            base_end_minute = base_end_time.minute
            # Calcular duración si no está disponible
            duration_minutes = ((base_end_hour * 60 + base_end_minute) - 
                              (base_start_hour * 60 + base_start_minute))
        else:
            # Si no hay end_time pero tenemos la duración de la clase
            duration_minutes = class_obj.duration
        
        created_sessions = []
        current_date = start_date
        
        # Iterar por cada día en el rango
        while current_date <= end_date:
            # Verificar si el día actual está en la lista de días seleccionados
            if current_date.weekday() in days_of_week:
                # Crear una copia de los datos base para esta sesión
                session_data = session_base_data.copy()
                
                # Crear datetime para este día específico con la hora base
                new_start_datetime = datetime.combine(
                    current_date, 
                    time(hour=base_start_hour, minute=base_start_minute)
                )
                
                session_data["start_time"] = new_start_datetime
                
                # Calcular end_time basado en la duración
                if "end_time" in session_data and session_data["end_time"]:
                    # Si tenemos end_time, crear uno nuevo con la misma fecha
                    new_end_datetime = datetime.combine(
                        current_date,
                        time(hour=base_end_hour, minute=base_end_minute)
                    )
                    session_data["end_time"] = new_end_datetime
                elif duration_minutes:
                    # Calcular end_time basado en la duración
                    new_end_datetime = new_start_datetime + timedelta(minutes=duration_minutes)
                    session_data["end_time"] = new_end_datetime
                
                # Convertir tiempos a UTC antes de crear la sesión
                from app.core.timezone_utils import convert_gym_time_to_utc
                session_data["start_time"] = convert_gym_time_to_utc(session_data["start_time"], gym.timezone)
                session_data["end_time"] = convert_gym_time_to_utc(session_data["end_time"], gym.timezone)
                
                # Crear la sesión
                session = class_session_repository.create(
                    db, obj_in=session_data
                )
                created_sessions.append(session)
                
            # Avanzar al siguiente día
            current_date += timedelta(days=1)
            
        # Invalidar cachés relevantes una vez después del bucle
        if created_sessions:
             await self._invalidate_session_caches(redis_client, gym_id=gym_id, trainer_id=base_session_data.trainer_id, class_id=base_session_data.class_id)
        
        return created_sessions
    
    async def update_session(
        self, db: Session, session_id: int, session_data: ClassSessionUpdate, gym_id: int, redis_client: Optional[Redis] = None
    ) -> Any:
        """Actualizar una sesión existente e invalidar caché"""
        # Nota: Añadir gym_id y redis_client
        session = class_session_repository.get(db, id=session_id)
        if not session or session.gym_id != gym_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión no encontrada en este gimnasio"
            )
        
        # Obtener el gimnasio para su timezone
        from app.repositories.gym import gym_repository
        gym = gym_repository.get(db, id=gym_id)
        if not gym:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Gimnasio no encontrado"
            )
        
        # Guardar datos originales para invalidación si cambian
        original_trainer_id = session.trainer_id
        original_class_id = session.class_id
        
        # Preparar datos de actualización
        update_data = session_data.model_dump(exclude_unset=True)
        
        # Si se están actualizando los tiempos, convertir a UTC
        if "start_time" in update_data or "end_time" in update_data:
            from app.core.timezone_utils import convert_gym_time_to_utc
            if "start_time" in update_data:
                update_data["start_time"] = convert_gym_time_to_utc(update_data["start_time"], gym.timezone)
            if "end_time" in update_data:
                update_data["end_time"] = convert_gym_time_to_utc(update_data["end_time"], gym.timezone)
        
        # Actualizar en BD
        updated_session = class_session_repository.update(
            db, db_obj=session, obj_in=update_data
        )
        
        # Invalidar caché
        await self._invalidate_session_caches(
            redis_client, 
            gym_id=gym_id, 
            session_id=session_id, 
            trainer_id=updated_session.trainer_id, 
            class_id=updated_session.class_id
        )
        # Invalidar también para trainer/clase original si cambiaron
        if original_trainer_id != updated_session.trainer_id:
             await self._invalidate_session_caches(redis_client, gym_id=gym_id, trainer_id=original_trainer_id)
        if original_class_id != updated_session.class_id:
             await self._invalidate_session_caches(redis_client, gym_id=gym_id, class_id=original_class_id)
             
        return updated_session
    
    async def cancel_session(self, db: Session, session_id: int, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """Cancelar una sesión e invalidar caché"""
        # Nota: Añadir gym_id y redis_client
        session = class_session_repository.get(db, id=session_id)
        if not session or session.gym_id != gym_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión no encontrada en este gimnasio"
            )
        
        # Guardar datos para invalidación
        trainer_id = session.trainer_id
        class_id = session.class_id
        
        # Actualizar el estado de la sesión a cancelado
        cancelled_session = class_session_repository.update(
            db, db_obj=session, 
            obj_in={"status": ClassSessionStatus.CANCELLED}
        )
    
        # Invalidar caché
        await self._invalidate_session_caches(
            redis_client, 
            gym_id=gym_id, 
            session_id=session_id, 
            trainer_id=trainer_id, 
            class_id=class_id
        )
        
        return cancelled_session
    
    async def get_upcoming_sessions(
        self, db: Session, skip: int = 0, limit: int = 100, gym_id: Optional[int] = None, redis_client: Optional[Redis] = None
    ) -> List[Any]:
        """
        Obtener las próximas sesiones programadas, opcionalmente filtradas por gimnasio (con caché).
        """
        # Si no hay gym_id, usar versión sin caché
        if gym_id is None:
            logger.warning("Attempted to get upcoming sessions without gym_id. Cache disabled.")
            return class_session_repository.get_upcoming_sessions(db, skip=skip, limit=limit)
        
        # Si no hay redis_client, usar versión sin caché
        if not redis_client:
            return class_session_repository.get_upcoming_sessions(
                db, skip=skip, limit=limit, gym_id=gym_id
            )
            
        cache_key = f"schedule:sessions:upcoming:gym:{gym_id}:skip:{skip}:limit:{limit}"
        tracking_set_key = f"cache_keys:sessions:{gym_id}"
        
        # Indica si el resultado vino de la BD
        fetched_from_db = False
        
        async def db_fetch():
            nonlocal fetched_from_db
            result = class_session_repository.get_upcoming_sessions(
                db, skip=skip, limit=limit, gym_id=gym_id
            )
            fetched_from_db = True
            return result
        
        # Usar el servicio de caché genérico
        from app.services.cache_service import cache_service
        from app.schemas.schedule import ClassSession
        
        sessions = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=ClassSession,
            expiry_seconds=300,  # 5 minutos para sesiones próximas
            is_list=True
        )
        
        # Añadir a tracking set para invalidación
        if fetched_from_db:
            try:
                await redis_client.sadd(tracking_set_key, cache_key)
                await redis_client.expire(tracking_set_key, 3600)  # 1 hora de tracking
            except Exception as e:
                logger.warning(f"No se pudo añadir clave a tracking set: {e}")
        
        return sessions
    
    async def get_sessions_by_date_range(
        self, db: Session, start_date: date, end_date: date, 
        skip: int = 0, limit: int = 100, gym_id: Optional[int] = None, redis_client: Optional[Redis] = None
    ) -> List[Any]:
        """
        Obtener sesiones en un rango de fechas, opcionalmente filtradas por gimnasio (con caché).
        """
        # Si no hay gym_id, usar versión sin caché
        if gym_id is None:
            logger.warning("Attempted to get sessions by date range without gym_id. Cache disabled.")
            start_datetime = datetime.combine(start_date, time.min)
            end_datetime = datetime.combine(end_date, time.max)
            return class_session_repository.get_by_date_range(db, start_date=start_datetime, end_date=end_datetime, skip=skip, limit=limit)

        # Si no hay redis_client, usar versión sin caché
        if not redis_client:
            start_datetime = datetime.combine(start_date, time.min)
            end_datetime = datetime.combine(end_date, time.max)
            return class_session_repository.get_by_date_range(
                db, start_date=start_datetime, end_date=end_datetime,
                skip=skip, limit=limit, gym_id=gym_id
            )

        # Formatear fechas para la clave
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()
        cache_key = f"schedule:sessions:range:gym:{gym_id}:start:{start_str}:end:{end_str}:skip:{skip}:limit:{limit}"
        tracking_set_key = f"cache_keys:sessions:{gym_id}"
        
        # Indica si el resultado vino de la BD
        fetched_from_db = False
        
        async def db_fetch():
            nonlocal fetched_from_db
            start_datetime = datetime.combine(start_date, time.min)
            end_datetime = datetime.combine(end_date, time.max)
            result = class_session_repository.get_by_date_range(
                db, start_date=start_datetime, end_date=end_datetime,
                skip=skip, limit=limit, gym_id=gym_id
            )
            fetched_from_db = True
            return result
        
        # Usar el servicio de caché genérico
        from app.services.cache_service import cache_service
        from app.schemas.schedule import ClassSession
        
        sessions = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=ClassSession,
            expiry_seconds=900,  # 15 minutos para rangos de fechas
            is_list=True
        )
        
        # Añadir a tracking set para invalidación
        if fetched_from_db:
            try:
                await redis_client.sadd(tracking_set_key, cache_key)
                await redis_client.expire(tracking_set_key, 3600)  # 1 hora de tracking
            except Exception as e:
                logger.warning(f"No se pudo añadir clave a tracking set: {e}")
        
        return sessions
    
    async def get_sessions_by_trainer(
        self, db: Session, trainer_id: int, skip: int = 0, limit: int = 100,
        upcoming_only: bool = False, gym_id: Optional[int] = None, redis_client: Optional[Redis] = None
    ) -> List[Any]:
        """
        Obtener sesiones de un entrenador específico, opcionalmente filtradas por gimnasio (con caché).
        """
        # Si no hay gym_id, usar versión sin caché
        if gym_id is None:
            logger.warning("Attempted to get sessions by trainer without gym_id. Cache disabled.")
            if upcoming_only:
                return class_session_repository.get_trainer_upcoming_sessions(db, trainer_id=trainer_id, skip=skip, limit=limit)
            return class_session_repository.get_by_trainer(db, trainer_id=trainer_id, skip=skip, limit=limit)
        
        # Si no hay redis_client, usar versión sin caché
        if not redis_client:
            if upcoming_only:
                return class_session_repository.get_trainer_upcoming_sessions(
                    db, trainer_id=trainer_id, skip=skip, limit=limit, gym_id=gym_id
                )
            return class_session_repository.get_by_trainer(
                db, trainer_id=trainer_id, skip=skip, limit=limit, gym_id=gym_id
            )
            
        cache_key = f"schedule:sessions:trainer:{trainer_id}:gym:{gym_id}:upcoming:{upcoming_only}:skip:{skip}:limit:{limit}"
        tracking_set_key = f"cache_keys:sessions:{gym_id}"
        trainer_tracking_key = f"cache_keys:sessions:trainer:{trainer_id}"
        
        # Indica si el resultado vino de la BD
        fetched_from_db = False
        
        async def db_fetch():
            nonlocal fetched_from_db
            if upcoming_only:
                result = class_session_repository.get_trainer_upcoming_sessions(
                    db, trainer_id=trainer_id, skip=skip, limit=limit, gym_id=gym_id
                )
            else:
                result = class_session_repository.get_by_trainer(
                    db, trainer_id=trainer_id, skip=skip, limit=limit, gym_id=gym_id
                )
            fetched_from_db = True
            return result
        
        # Usar el servicio de caché genérico
        from app.services.cache_service import cache_service
        from app.schemas.schedule import ClassSession
        
        sessions = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=ClassSession,
            expiry_seconds=600,  # 10 minutos para sesiones por trainer
            is_list=True
        )
        
        # Añadir a tracking sets para invalidación
        if fetched_from_db:
            try:
                await redis_client.sadd(tracking_set_key, cache_key)
                await redis_client.sadd(trainer_tracking_key, cache_key)
                await redis_client.expire(tracking_set_key, 3600)  # 1 hora de tracking
                await redis_client.expire(trainer_tracking_key, 3600)  # 1 hora de tracking
            except Exception as e:
                logger.warning(f"No se pudo añadir clave a tracking sets: {e}")
        
        return sessions
    
    async def get_sessions_by_class(
        self, db: Session, class_id: int, skip: int = 0, limit: int = 100, gym_id: Optional[int] = None, redis_client: Optional[Redis] = None
    ) -> List[Any]:
        """
        Obtener sesiones de una clase específica, opcionalmente filtradas por gimnasio (con caché).
        """
        # Si no hay gym_id, usar versión sin caché
        if gym_id is None:
            logger.warning("Attempted to get sessions by class without gym_id. Cache disabled.")
            return class_session_repository.get_by_class(db, class_id=class_id, skip=skip, limit=limit)

        # Si no hay redis_client, usar versión sin caché
        if not redis_client:
            return class_session_repository.get_by_class(
                db, class_id=class_id, skip=skip, limit=limit, gym_id=gym_id
            )

        cache_key = f"schedule:sessions:class:{class_id}:gym:{gym_id}:skip:{skip}:limit:{limit}"
        tracking_set_key = f"cache_keys:sessions:{gym_id}"
        class_tracking_key = f"cache_keys:sessions:class:{class_id}"
        
        # Indica si el resultado vino de la BD
        fetched_from_db = False
        
        async def db_fetch():
            nonlocal fetched_from_db
            result = class_session_repository.get_by_class(
                db, class_id=class_id, skip=skip, limit=limit, gym_id=gym_id
            )
            fetched_from_db = True
            return result
        
        # Usar el servicio de caché genérico
        from app.services.cache_service import cache_service
        from app.schemas.schedule import ClassSession
        
        sessions = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=ClassSession,
            expiry_seconds=600,  # 10 minutos para sesiones por clase
            is_list=True
        )
        
        # Añadir a tracking sets para invalidación
        if fetched_from_db:
            try:
                await redis_client.sadd(tracking_set_key, cache_key)
                await redis_client.sadd(class_tracking_key, cache_key)
                await redis_client.expire(tracking_set_key, 3600)  # 1 hora de tracking
                await redis_client.expire(class_tracking_key, 3600)  # 1 hora de tracking
            except Exception as e:
                logger.warning(f"No se pudo añadir clave a tracking sets: {e}")
        
        return sessions


class ClassParticipationService:
    async def register_for_class(self, db: Session, member_id: int, session_id: int, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """Registrar a un miembro en una sesión de clase e invalidar caché de sesión"""
        # Nota: Añadir gym_id y redis_client
        # Verificar si la sesión existe, está programada y pertenece al gimnasio
        session_data = class_session_repository.get_with_availability(db, session_id=session_id)
        if not session_data or session_data["session"].gym_id != gym_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión no encontrada en este gimnasio"
            )
        
        session = session_data["session"]
        class_obj = session_data["class"] # Ya sabemos que la sesión pertenece al gym_id
        
        # Validar que la sesión esté en estado programado
        if session.status != ClassSessionStatus.SCHEDULED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede registrar en una sesión que no está programada"
            )
        
        # Obtener información del gimnasio para usar su timezone
        from app.repositories.gym import gym_repository
        gym = gym_repository.get(db, id=gym_id)
        if not gym:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Gimnasio no encontrado"
            )
        
        # Validar que la sesión no haya comenzado aún usando timezone del gimnasio
        if not is_session_in_future(session.start_time, gym.timezone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede registrar en una sesión que ya ha comenzado o terminado"
            )
        
        # Validar que la sesión no esté llena
        if session_data["is_full"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La sesión está llena"
            )
        
        # Verificar si el miembro ya está registrado
        existing = class_participation_repository.get_by_session_and_member(
            db, session_id=session_id, member_id=member_id, gym_id=gym_id # Añadir gym_id
        )
        
        participation_result = None
        if existing:
            if existing.status == ClassParticipationStatus.CANCELLED:
                # Reactivar registro
                participation_result = class_participation_repository.update(
                    db, db_obj=existing,
                    obj_in={
                        "status": ClassParticipationStatus.REGISTERED,
                        "cancellation_time": None,
                        "cancellation_reason": None
                    }
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ya estás registrado en esta clase"
                )
        else:
            # Crear nueva participación
            participation_data = {
                "session_id": session_id,
                "member_id": member_id,
                "status": ClassParticipationStatus.REGISTERED,
                "gym_id": gym_id  # Asignar el gym_id
            }
            participation_result = class_participation_repository.create(
                db, obj_in=participation_data
            )
        
        # Actualizar contador de participantes y validar resultado
        if participation_result:
            class_session_repository.update_participant_count(db, session_id=session_id)
            # Invalidar cachés de sesión al final
            await self._invalidate_session_caches_from_participation(
                session_id=session_id,
                gym_id=gym_id,
                redis_client=redis_client,
                trainer_id=session.trainer_id, 
                class_id=session.class_id
            )
            return participation_result
        else:
             # Si por alguna razón no se creó/actualizó la participación
             raise HTTPException(status_code=500, detail="No se pudo completar el registro")

    async def cancel_registration(self, db: Session, member_id: int, session_id: int, gym_id: int, reason: Optional[str] = None, redis_client: Optional[Redis] = None) -> Any:
        """Cancelar el registro de un miembro en una sesión e invalidar caché de sesión"""
        # Nota: Añadir gym_id y redis_client
        # Verificar si la participación existe y pertenece al gimnasio
        participation = class_participation_repository.get_by_session_and_member(
            db, session_id=session_id, member_id=member_id, gym_id=gym_id # Añadir gym_id
        )
        
        if not participation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No estás registrado en esta clase"
            )
        
        # ... (resto de validaciones: status) ...
        session = class_session_repository.get(db, id=session_id) # Necesitamos la sesión para invalidar
        
        # Cancelar la participación
        cancelled_participation = class_participation_repository.cancel_participation(
            db, session_id=session_id, member_id=member_id, reason=reason, gym_id=gym_id # Pasar gym_id
        )
        
        # Actualizar contador y validar resultado
        if cancelled_participation:
            # Actualizar contador (cancel_participation ya lo hace, pero aseguramos)
            class_session_repository.update_participant_count(db, session_id=session_id)
            # Invalidar cachés de sesión
            if session: # Asegurar que tenemos la sesión
                await self._invalidate_session_caches_from_participation(
                    session_id=session_id,
                    gym_id=gym_id,
                    redis_client=redis_client,
                    trainer_id=session.trainer_id, 
                    class_id=session.class_id
                )
            return cancelled_participation
        else:
             raise HTTPException(status_code=500, detail="No se pudo completar la cancelación")
    
    async def mark_attendance(self, db: Session, member_id: int, session_id: int, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """Marcar la asistencia de un miembro a una sesión"""
        # Nota: Añadir gym_id. La invalidación no es estrictamente necesaria aquí
        #       a menos que afecte a listas futuras o algo similar.
        # Verificar si la participación existe y pertenece al gimnasio
        participation = class_participation_repository.get_by_session_and_member(
            db, session_id=session_id, member_id=member_id, gym_id=gym_id
        )
        
        if not participation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El miembro no está registrado en esta clase"
            )
        
        # ... (resto de validaciones: status) ...
        
        # Marcar la asistencia
        return class_participation_repository.mark_attendance(
            db, session_id=session_id, member_id=member_id, gym_id=gym_id # Pasar gym_id
        )
    
    async def mark_no_show(self, db: Session, member_id: int, session_id: int, gym_id: int, redis_client: Optional[Redis] = None) -> Any:
        """Marcar que un miembro no asistió a una sesión"""
        # Nota: Añadir gym_id. Similar a mark_attendance, la invalidación
        #       no suele ser crítica aquí.
        # Verificar si la participación existe y pertenece al gimnasio
        participation = class_participation_repository.get_by_session_and_member(
            db, session_id=session_id, member_id=member_id, gym_id=gym_id
        )
        
        if not participation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El miembro no está registrado en esta clase"
            )
        
        # ... (resto de validaciones: status) ...
        
        # Marcar como no-show
        updated = class_participation_repository.update(
            db, db_obj=participation,
            obj_in={"status": ClassParticipationStatus.NO_SHOW}
        )
        
        return updated
    
    async def get_session_participants(
        self, db: Session, session_id: int, skip: int = 0, limit: int = 100, gym_id: Optional[int] = None, redis_client: Optional[Redis] = None
    ) -> List[Any]:
        """Obtener todos los participantes de una sesión (con caché)"""
        # Nota: Añadir redis_client
        if gym_id is None:
             logger.warning("Attempted to get session participants without gym_id. Cache disabled.")
             return class_participation_repository.get_by_session(db, session_id=session_id, skip=skip, limit=limit)
             
        cache_key = f"schedule:participations:session:{session_id}:gym:{gym_id}:skip:{skip}:limit:{limit}"
        
        # ... (implementar con cache_service.get_or_set, requiere ClassParticipationSchema)
        
        # Por ahora, versión no cacheada
        return class_participation_repository.get_by_session(
            db, session_id=session_id, skip=skip, limit=limit, gym_id=gym_id
        )
    
    async def get_member_participations(
        self, db: Session, member_id: int, skip: int = 0, limit: int = 100, gym_id: Optional[int] = None, redis_client: Optional[Redis] = None
    ) -> List[Any]:
        """Obtener todas las participaciones de un miembro (con caché)"""
        # Nota: Añadir gym_id y redis_client
        # La clave de caché podría incluir gym_id si es relevante para las participaciones del miembro
        cache_key = f"schedule:participations:member:{member_id}:gym:{gym_id or 'all'}:skip:{skip}:limit:{limit}"
        
        # ... (implementar con cache_service.get_or_set, requiere ClassParticipationSchema)
        
        # Por ahora, versión no cacheada
        return class_participation_repository.get_by_member(
            db, member_id=member_id, skip=skip, limit=limit, gym_id=gym_id
        )
    
    async def get_member_upcoming_classes(
        self, db: Session, member_id: int, gym_id: int, skip: int = 0, limit: int = 100, 
        redis_client: Optional[Redis] = None
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming classes for a member (with Redis cache).

        Args:
            db (Session): Database session
            member_id (int): ID of the member
            gym_id (int): ID of the gym
            skip (int, optional): Pagination skip. Defaults to 0.
            limit (int, optional): Pagination limit. Defaults to 100.
            redis_client (Optional[Redis], optional): Redis client. Defaults to None.

        Returns:
            List[Dict[str, Any]]: List of dictionaries containing participation and session information
        """
        # Si no hay Redis, usar consulta directa
        if not redis_client:
            return await self._get_member_upcoming_classes_direct(db, member_id, gym_id, skip, limit)
        
        # Crear clave de caché
        cache_key = f"schedule:member_upcoming:member:{member_id}:gym:{gym_id}:skip:{skip}:limit:{limit}"
        
        # Función para obtener datos de la BD
        async def db_fetch():
            logger.info(f"Cache miss para upcoming classes: member={member_id}, gym={gym_id}")
            return await self._get_member_upcoming_classes_direct(db, member_id, gym_id, skip, limit)
        
        # Intentar obtener de caché o generar nuevos datos
        try:
            cached_data = await redis_client.get(cache_key)
            
            if cached_data:
                # Cache hit
                logger.debug(f"Cache HIT para upcoming classes: {cache_key}")
                data = json.loads(cached_data)
                
                # Reconstruir objetos desde cache
                result = []
                for item in data:
                    result.append({
                        "participation": ClassParticipationSchema.parse_obj(item["participation"]),
                        "session": ClassSessionSchema.parse_obj(item["session"]),
                        "gym_class": ClassSchema.parse_obj(item["gym_class"])
                    })
                return result
            
            # Cache miss - obtener de BD
            logger.debug(f"Cache MISS para upcoming classes: {cache_key}")
            raw_data = await db_fetch()
            
            # Serializar para cache (convertir objetos Pydantic a dict)
            cache_data = []
            for item in raw_data:
                cache_data.append({
                    "participation": item["participation"].dict(),
                    "session": item["session"].dict(),
                    "gym_class": item["gym_class"].dict()
                })
            
            # Guardar en caché (TTL: 5 minutos para datos dinámicos)
            await redis_client.set(
                cache_key,
                json.dumps(cache_data, default=str),  # default=str para datetime
                ex=300  # 5 minutos TTL
            )
            
            logger.debug(f"Datos guardados en cache: {cache_key}")
            return raw_data
            
        except Exception as e:
            logger.error(f"Error en cache para upcoming classes: {e}", exc_info=True)
            # Fallback a consulta directa
            return await self._get_member_upcoming_classes_direct(db, member_id, gym_id, skip, limit)

    async def _get_member_upcoming_classes_direct(
        self, db: Session, member_id: int, gym_id: int, skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Consulta directa a BD para obtener clases próximas del usuario (método privado).
        """
        now = datetime.utcnow()
        
        # Get the member's upcoming registrations where start_time > now
        upcoming_participations = (
            db.query(ClassParticipation, ClassSession, Class)
            .join(ClassSession, ClassParticipation.session_id == ClassSession.id)
            .join(Class, ClassSession.class_id == Class.id)
            .filter(
                ClassParticipation.member_id == member_id,
                ClassParticipation.gym_id == gym_id,
                ClassSession.start_time > now,
                # Only include registered (not cancelled, attended, or no-show)
                ClassParticipation.status == ClassParticipationStatus.REGISTERED
            )
            .order_by(ClassSession.start_time.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        # Format the results with proper serialization to avoid PydanticSerializationError
        result = []
        for participation, session, gym_class in upcoming_participations:
            # Convierte los modelos SQLAlchemy a esquemas Pydantic
            result.append({
                "participation": ClassParticipationSchema.parse_obj(participation.__dict__),
                "session": ClassSessionSchema.parse_obj(session.__dict__),
                "gym_class": ClassSchema.parse_obj(gym_class.__dict__)
            })
            
        return result
    
    async def get_member_attendance_history(
        self, db: Session, member_id: int, gym_id: int, 
        start_date: Optional[datetime] = None, end_date: Optional[datetime] = None,
        skip: int = 0, limit: int = 100, redis_client: Optional[Redis] = None
    ) -> List[Dict[str, Any]]:
        """
        Get attendance history for a member.

        Args:
            db (Session): Database session
            member_id (int): ID of the member
            gym_id (int): ID of the gym
            start_date (Optional[datetime], optional): If provided, only include attendances on or after this date
            end_date (Optional[datetime], optional): If provided, only include attendances on or before this date
            skip (int, optional): Pagination skip. Defaults to 0.
            limit (int, optional): Pagination limit. Defaults to 100.
            redis_client (Optional[Redis], optional): Redis client. Defaults to None.

        Returns:
            List[Dict[str, Any]]: List of dictionaries containing participation and session information
        """
        query = (
            db.query(ClassParticipation, ClassSession, Class)
            .join(ClassSession, ClassParticipation.session_id == ClassSession.id)
            .join(Class, ClassSession.class_id == Class.id)
            .filter(
                ClassParticipation.member_id == member_id,
                ClassParticipation.gym_id == gym_id,
                # Sessions that have already happened
                ClassSession.start_time <= datetime.utcnow()
            )
        )
        
        # Apply date filters if provided
        if start_date:
            query = query.filter(ClassSession.start_time >= start_date)
        if end_date:
            query = query.filter(ClassSession.start_time <= end_date)
        
        # Order by most recent first
        query = query.order_by(ClassSession.start_time.desc())
        
        # Apply pagination
        history = query.offset(skip).limit(limit).all()
        
        # Format the results
        result = []
        for participation, session, gym_class in history:
            result.append({
                "participation": participation,
                "session": session,
                "gym_class": gym_class
            })
            
        return result

    # Método helper para invalidar cachés de sesión cuando cambia una participación
    async def _invalidate_session_caches_from_participation(self, session_id: int, gym_id: int, redis_client: Optional[Redis] = None, trainer_id: Optional[int] = None, class_id: Optional[int] = None):
        """
        Invalida las cachés relacionadas con una sesión específica cuando cambia una participación
        (por ejemplo, un usuario se une o se va).
        
        Esto incluye:
        - Detalles de la sesión (con y sin disponibilidad).
        - Listas de participantes de esa sesión.
        - Posiblemente listas generales donde la disponibilidad podría cambiar (upcoming, range, etc.).
        """
        if not redis_client:
            return
            
        keys_to_delete = []
        patterns_to_delete = []

        # Claves de detalle de la sesión
        keys_to_delete.append(f"schedule:session:detail:{session_id}")
        keys_to_delete.append(f"schedule:session:detail_with_availability:{session_id}")
        
        # Patrón de participantes de esta sesión específica
        patterns_to_delete.append(f"schedule:participations:session:{session_id}:gym:{gym_id}:*")
        
        # Invalidar listas generales donde la disponibilidad podría cambiar (más seguro)
        patterns_to_delete.append(f"schedule:sessions:upcoming:gym:{gym_id}:*") 
        patterns_to_delete.append(f"schedule:sessions:range:gym:{gym_id}:*") 
        if trainer_id:
             patterns_to_delete.append(f"schedule:sessions:trainer:{trainer_id}:gym:{gym_id}:*")
        if class_id:
             patterns_to_delete.append(f"schedule:sessions:class:{class_id}:gym:{gym_id}:*")
             
        try:
            if keys_to_delete:
                deleted_keys = await redis_client.delete(*keys_to_delete)
                logger.debug(f"Invalidated {deleted_keys} session detail keys from participation change: {keys_to_delete}")
            
            deleted_pattern_count = 0
            for pattern in patterns_to_delete:
                deleted_count = await cache_service.delete_pattern(redis_client, pattern)
                deleted_pattern_count += deleted_count
                logger.debug(f"Invalidated {deleted_count} keys with pattern from participation change: {pattern}")
            logger.debug(f"Total invalidated keys from patterns due to participation change: {deleted_pattern_count}")
            
        except Exception as e:
             logger.error(f"Error invalidating session cache {session_id} from participation change: {e}", exc_info=True)


# Instantiate services
gym_hours_service = GymHoursService()
gym_special_hours_service = GymSpecialHoursService()
category_service = ClassCategoryService()
class_service = ClassService()
class_session_service = ClassSessionService()
class_participation_service = ClassParticipationService() 