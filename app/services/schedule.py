from typing import List, Optional, Dict, Any, Union
from datetime import datetime, time, timedelta, date
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

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
    ClassCategoryCustom
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
    ClassCategoryCustomUpdate
)

# --- Añadir importaciones para Caché --- 
import logging
from redis.asyncio import Redis
from app.services.cache_service import cache_service
from app.schemas.schedule import ClassCategoryCustom as ClassCategoryCustomSchema
# --- Fin importaciones Caché --- 


class GymHoursService:
    def get_gym_hours_by_day(self, db: Session, day: int, gym_id: int) -> Any:
        """
        Obtener los horarios del gimnasio para un día específico.
        
        Args:
            db: Sesión de base de datos
            day: Día de la semana (0=Lunes, 6=Domingo)
            gym_id: ID del gimnasio
        """
        return gym_hours_repository.get_by_day(db, day=day, gym_id=gym_id)
    
    def get_all_gym_hours(self, db: Session, gym_id: int) -> List[Any]:
        """
        Obtener los horarios para todos los días de la semana.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
        """
        return gym_hours_repository.get_all_days(db, gym_id=gym_id)
    
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
        # Verificar que el rango de fechas sea válido
        if end_date < start_date:
            raise ValueError("La fecha de fin no puede ser anterior a la fecha de inicio")
            
        # Obtener los horarios semanales predeterminados
        weekly_hours = self.get_all_gym_hours(db, gym_id=gym_id)
        if not weekly_hours:
            # Si no hay horarios semanales, crearlos con valores predeterminados
            weekly_hours = self._create_default_hours(db, gym_id=gym_id)
            
        # Crear un diccionario de horarios por día de la semana para acceso rápido
        weekly_hours_dict = {hour.day_of_week: hour for hour in weekly_hours}
        
        # Preparar los datos para crear o actualizar horarios especiales
        schedule_data = {}
        current_date = start_date
        
        while current_date <= end_date:
            # Obtener el día de la semana (0=Lunes, 6=Domingo)
            day_of_week = current_date.weekday()
            
            # Obtener el horario semanal para este día
            weekly_hour = weekly_hours_dict.get(day_of_week)
            if not weekly_hour:
                # Si no hay horario para este día, usar valores predeterminados
                is_closed = day_of_week == 6  # Cerrado en domingo
                open_time = time(9, 0) if not is_closed else None
                close_time = time(21, 0) if not is_closed else None
            else:
                # Usar el horario semanal para este día
                is_closed = weekly_hour.is_closed
                open_time = weekly_hour.open_time
                close_time = weekly_hour.close_time
                
            # Verificar si ya existe un horario especial para esta fecha
            special_hour = gym_special_hours_repository.get_by_date(db, date_value=current_date, gym_id=gym_id)
            
            # Si no existe o se debe sobrescribir, agregar a los datos a procesar
            if not special_hour or overwrite_existing:
                schedule_data[current_date] = {
                    "open_time": open_time,
                    "close_time": close_time,
                    "is_closed": is_closed,
                    "description": f"Aplicado desde plantilla ({day_of_week})"
                }
                
            # Avanzar al siguiente día
            current_date += timedelta(days=1)
            
        # Crear o actualizar los horarios especiales en bloque
        return gym_special_hours_repository.bulk_create_or_update(
            db, gym_id=gym_id, schedule_data=schedule_data
        )
        
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
        # Verificar que el rango de fechas sea válido
        if end_date < start_date:
            raise ValueError("La fecha de fin no puede ser anterior a la fecha de inicio")
            
        # Obtener los horarios especiales para este rango
        special_hours = gym_special_hours_repository.get_by_date_range(
            db, start_date=start_date, end_date=end_date, gym_id=gym_id
        )
        
        # Crear un diccionario de horarios especiales por fecha para acceso rápido
        special_hours_dict = {str(hour.date): hour for hour in special_hours}
        
        # Obtener los horarios semanales predeterminados
        weekly_hours = self.get_all_gym_hours(db, gym_id=gym_id)
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


class GymSpecialHoursService:
    def get_special_hours(self, db: Session, special_day_id: int) -> Any:
        """Obtener un día especial por ID"""
        return gym_special_hours_repository.get(db, id=special_day_id)
    
    def get_special_hours_by_date(self, db: Session, date_value: date, gym_id: int) -> Any:
        """
        Obtener horarios especiales para una fecha específica.
        
        Args:
            db: Sesión de base de datos
            date_value: Fecha a consultar
            gym_id: ID del gimnasio
        """
        return gym_special_hours_repository.get_by_date(db, date_value=date_value, gym_id=gym_id)
    
    def get_upcoming_special_days(self, db: Session, limit: int = 10, gym_id: int = None) -> List[Any]:
        """
        Obtener los próximos días especiales.
        
        Args:
            db: Sesión de base de datos
            limit: Número máximo de registros a devolver
            gym_id: ID del gimnasio para filtrar
        """
        return gym_special_hours_repository.get_upcoming_special_days(db, limit=limit, gym_id=gym_id)
    
    def create_special_day(self, db: Session, special_hours_data: GymSpecialHoursCreate, gym_id: int = None) -> Any:
        """
        Crear un nuevo día especial
        
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
    
    def update_special_day(
        self, db: Session, special_day_id: int, special_hours_data: GymSpecialHoursUpdate
    ) -> Any:
        """Actualizar un día especial existente"""
        special_day = gym_special_hours_repository.get(db, id=special_day_id)
        if not special_day:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Día especial no encontrado"
            )
        
        return gym_special_hours_repository.update(
            db, db_obj=special_day, obj_in=special_hours_data
        )
    
    def delete_special_day(self, db: Session, special_day_id: int) -> Any:
        """Eliminar un día especial"""
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
        try:
            if category_id:
                detail_key = f"category:custom:detail:{category_id}"
                await redis_client.delete(detail_key)
                logger.debug(f"Invalidated cache key: {detail_key}")
            list_pattern = f"categories:custom:gym:{gym_id}:*"
            deleted_count = await cache_service.delete_pattern(redis_client, list_pattern)
            logger.debug(f"Invalidated {deleted_count} keys with pattern: {list_pattern}")
        except Exception as e:
            logger.error(f"Error invalidating category cache: {e}", exc_info=True)
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
        """Obtener categorías para un gimnasio específico (con caché)"""
        
        cache_key = f"categories:custom:gym:{gym_id}:active:{active_only}"
        
        async def db_fetch():
            if active_only:
                return class_category_repository.get_active_categories(db, gym_id=gym_id)
            return class_category_repository.get_by_gym(db, gym_id=gym_id)

        categories = await cache_service.get_or_set(
            redis_client=redis_client,
            cache_key=cache_key,
            db_fetch_func=db_fetch,
            model_class=ClassCategoryCustomSchema,
            expiry_seconds=3600, # 1 hora
            is_list=True
        )
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
    def get_class(self, db: Session, class_id: int) -> Any:
        """Obtener una clase por ID"""
        class_obj = class_repository.get(db, id=class_id)
        if not class_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clase no encontrada"
            )
        return class_obj
    
    def get_classes(
        self, db: Session, skip: int = 0, limit: int = 100, active_only: bool = True,
        gym_id: Optional[int] = None
    ) -> List[Any]:
        """
        Obtener todas las clases, opcionalmente filtradas por gimnasio.
        
        Args:
            db: Sesión de base de datos
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver (paginación)
            active_only: Si es True, solo devuelve clases activas
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        query = db.query(Class)
        
        if active_only:
            query = query.filter(Class.is_active == True)
        
        if gym_id is not None:
            query = query.filter(Class.gym_id == gym_id)
        
        return query.offset(skip).limit(limit).all()
    
    def create_class(self, db: Session, class_data: ClassCreate, created_by_id: Optional[int] = None, gym_id: int = None) -> Any:
        """
        Crear una nueva clase
        
        Args:
            db: Sesión de base de datos
            class_data: Datos de la clase a crear
            created_by_id: ID del usuario que crea la clase (opcional)
            gym_id: ID del gimnasio al que pertenece la clase
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
        
        # Crear la clase
        return class_repository.create(db, obj_in=obj_in_data)
    
    def update_class(self, db: Session, class_id: int, class_data: ClassUpdate) -> Any:
        """Actualizar una clase existente"""
        class_obj = class_repository.get(db, id=class_id)
        if not class_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clase no encontrada"
            )
        
        return class_repository.update(db, db_obj=class_obj, obj_in=class_data)
    
    def delete_class(self, db: Session, class_id: int) -> Any:
        """Eliminar una clase"""
        class_obj = class_repository.get(db, id=class_id)
        if not class_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clase no encontrada"
            )
        
        # Verificar si hay sesiones programadas para esta clase
        sessions = class_session_repository.get_by_class(db, class_id=class_id)
        if sessions:
            # Actualizar el estado de la clase a inactivo en lugar de eliminarla
            return class_repository.update(
                db, db_obj=class_obj, obj_in={"is_active": False}
            )
        
        return class_repository.remove(db, id=class_id)
    
    def get_classes_by_category(
        self, db: Session, *, category: str, skip: int = 0, limit: int = 100,
        gym_id: Optional[int] = None
    ) -> List[Any]:
        """
        Obtener clases por categoría, opcionalmente filtradas por gimnasio.
        
        Args:
            db: Sesión de base de datos
            category: Categoría de clase a filtrar
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver (paginación)
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        query = db.query(Class).filter(Class.category_enum == category, Class.is_active == True)
        
        if gym_id is not None:
            query = query.filter(Class.gym_id == gym_id)
        
        return query.offset(skip).limit(limit).all()
    
    def get_classes_by_difficulty(
        self, db: Session, *, difficulty: str, skip: int = 0, limit: int = 100,
        gym_id: Optional[int] = None
    ) -> List[Any]:
        """
        Obtener clases por nivel de dificultad, opcionalmente filtradas por gimnasio.
        
        Args:
            db: Sesión de base de datos
            difficulty: Nivel de dificultad a filtrar
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver (paginación)
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        query = db.query(Class).filter(Class.difficulty_level == difficulty, Class.is_active == True)
        
        if gym_id is not None:
            query = query.filter(Class.gym_id == gym_id)
        
        return query.offset(skip).limit(limit).all()
    
    def search_classes(
        self, db: Session, *, search: str, skip: int = 0, limit: int = 100,
        gym_id: Optional[int] = None
    ) -> List[Any]:
        """
        Buscar clases por nombre o descripción, opcionalmente filtradas por gimnasio.
        
        Args:
            db: Sesión de base de datos
            search: Texto a buscar en nombre o descripción
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver (paginación)
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        search_pattern = f"%{search}%"
        query = db.query(Class).filter(
            or_(
                Class.name.ilike(search_pattern),
                Class.description.ilike(search_pattern)
            ),
            Class.is_active == True
        )
        
        if gym_id is not None:
            query = query.filter(Class.gym_id == gym_id)
        
        return query.offset(skip).limit(limit).all()


class ClassSessionService:
    def get_session(self, db: Session, session_id: int) -> Any:
        """Obtener una sesión por ID"""
        session = class_session_repository.get(db, id=session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión no encontrada"
            )
        return session
    
    def get_session_with_details(self, db: Session, session_id: int) -> Dict[str, Any]:
        """Obtener una sesión con detalles de clase y disponibilidad"""
        session_data = class_session_repository.get_with_availability(db, session_id=session_id)
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión no encontrada"
            )
        return session_data
    
    def create_session(
        self, db: Session, session_data: ClassSessionCreate, created_by_id: Optional[int] = None
    ) -> Any:
        """Crear una nueva sesión de clase"""
        # Verificar que la clase exista y esté activa
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
        
        # Calcular hora de fin si no se proporciona
        obj_in_data = session_data.model_dump()
        if not obj_in_data.get("end_time") and class_obj.duration:
            start_time = obj_in_data.get("start_time")
            if start_time:
                end_time = start_time + timedelta(minutes=class_obj.duration)
                obj_in_data["end_time"] = end_time
        
        # Agregar ID del creador si se proporciona
        if created_by_id:
            obj_in_data["created_by"] = created_by_id
        
        # Asegurarse de que gym_id esté presente
        if "gym_id" not in obj_in_data or obj_in_data["gym_id"] is None:
            # Si no está presente, usar el gym_id de la clase
            obj_in_data["gym_id"] = class_obj.gym_id
            print(f"DEBUG: Usando gym_id={class_obj.gym_id} de la clase {class_obj.id}")
        
        # Confirmar que gym_id no sea None
        if obj_in_data.get("gym_id") is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El ID del gimnasio (gym_id) no puede ser nulo"
            )
        
        # Crear la sesión
        return class_session_repository.create(
            db, obj_in=ClassSessionCreate(**obj_in_data)
        )
    
    def create_recurring_sessions(
        self, db: Session, 
        base_session_data: ClassSessionCreate, 
        start_date: date,
        end_date: date,
        days_of_week: List[int],  # 0=Lunes, 1=Martes, etc.
        created_by_id: Optional[int] = None
    ) -> List[Any]:
        """Crear sesiones recurrentes basadas en días de la semana"""
        if not days_of_week:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe especificar al menos un día de la semana"
            )
        
        # Validar los días de la semana
        for day in days_of_week:
            if day < 0 or day > 6:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Día de la semana inválido: {day}"
                )
        
        # Verificar que la clase exista y esté activa
        class_obj = class_repository.get(db, id=base_session_data.class_id)
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
        
        # Preparar datos base de la sesión
        session_base_data = base_session_data.model_dump()
        if created_by_id:
            session_base_data["created_by"] = created_by_id
        
        # Crear el patrón de recurrencia (formato: "WEEKLY:0,2,4" para lunes, miércoles, viernes)
        recurrence_pattern = f"WEEKLY:{','.join(map(str, days_of_week))}"
        session_base_data["is_recurring"] = True
        session_base_data["recurrence_pattern"] = recurrence_pattern
        
        # Obtener la hora del día de la sesión base
        base_time = datetime.combine(date.today(), base_session_data.start_time.time())
        
        # Generar todas las fechas en el rango que coincidan con los días de la semana
        current_date = start_date
        created_sessions = []
        
        while current_date <= end_date:
            # Verificar si el día de la semana actual está en la lista
            if current_date.weekday() in days_of_week:
                # Crear los datos específicos para esta sesión
                session_data = session_base_data.copy()
                
                # Ajustar fecha y hora
                session_start = datetime.combine(current_date, base_time.time())
                session_data["start_time"] = session_start
                
                # Calcular hora de fin
                if not session_data.get("end_time") and class_obj.duration:
                    session_data["end_time"] = session_start + timedelta(minutes=class_obj.duration)
                
                # Crear la sesión
                session = class_session_repository.create(
                    db, obj_in=ClassSessionCreate(**session_data)
                )
                created_sessions.append(session)
            
            # Avanzar al siguiente día
            current_date += timedelta(days=1)
        
        return created_sessions
    
    def update_session(
        self, db: Session, session_id: int, session_data: ClassSessionUpdate
    ) -> Any:
        """Actualizar una sesión existente"""
        session = class_session_repository.get(db, id=session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión no encontrada"
            )
        
        # Si se cambia la hora de inicio pero no la de fin, recalcular la hora de fin
        update_data = session_data.model_dump(exclude_unset=True)
        if "start_time" in update_data and "end_time" not in update_data:
            # Obtener la duración de la clase
            class_obj = class_repository.get(db, id=session.class_id)
            if class_obj and class_obj.duration:
                new_start_time = update_data["start_time"]
                update_data["end_time"] = new_start_time + timedelta(minutes=class_obj.duration)
        
        return class_session_repository.update(
            db, db_obj=session, obj_in=update_data
        )
    
    def cancel_session(self, db: Session, session_id: int) -> Any:
        """Cancelar una sesión"""
        session = class_session_repository.get(db, id=session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión no encontrada"
            )
        
        # Actualizar el estado de la sesión a cancelado
        return class_session_repository.update(
            db, db_obj=session, 
            obj_in={"status": ClassSessionStatus.CANCELLED}
        )
    
    def get_upcoming_sessions(
        self, db: Session, skip: int = 0, limit: int = 100, gym_id: Optional[int] = None
    ) -> List[Any]:
        """
        Obtener las próximas sesiones programadas, opcionalmente filtradas por gimnasio.
        
        Args:
            db: Sesión de base de datos
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver (paginación)
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        return class_session_repository.get_upcoming_sessions(
            db, skip=skip, limit=limit, gym_id=gym_id
        )
    
    def get_sessions_by_date_range(
        self, db: Session, start_date: date, end_date: date, 
        skip: int = 0, limit: int = 100, gym_id: Optional[int] = None
    ) -> List[Any]:
        """
        Obtener sesiones en un rango de fechas, opcionalmente filtradas por gimnasio.
        
        Args:
            db: Sesión de base de datos
            start_date: Fecha de inicio
            end_date: Fecha de fin
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver (paginación)
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        start_datetime = datetime.combine(start_date, time.min)
        end_datetime = datetime.combine(end_date, time.max)
        
        return class_session_repository.get_by_date_range(
            db, start_date=start_datetime, end_date=end_datetime,
            skip=skip, limit=limit, gym_id=gym_id
        )
    
    def get_sessions_by_trainer(
        self, db: Session, trainer_id: int, skip: int = 0, limit: int = 100,
        upcoming_only: bool = False, gym_id: Optional[int] = None
    ) -> List[Any]:
        """
        Obtener sesiones de un entrenador específico, opcionalmente filtradas por gimnasio.
        
        Args:
            db: Sesión de base de datos
            trainer_id: ID del entrenador
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver (paginación)
            upcoming_only: Si es True, solo devuelve las sesiones futuras
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        if upcoming_only:
            return class_session_repository.get_trainer_upcoming_sessions(
                db, trainer_id=trainer_id, skip=skip, limit=limit, gym_id=gym_id
            )
        return class_session_repository.get_by_trainer(
            db, trainer_id=trainer_id, skip=skip, limit=limit, gym_id=gym_id
        )
    
    def get_sessions_by_class(
        self, db: Session, class_id: int, skip: int = 0, limit: int = 100, gym_id: Optional[int] = None
    ) -> List[Any]:
        """
        Obtener sesiones de una clase específica, opcionalmente filtradas por gimnasio.
        
        Args:
            db: Sesión de base de datos
            class_id: ID de la clase
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver (paginación)
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        return class_session_repository.get_by_class(
            db, class_id=class_id, skip=skip, limit=limit, gym_id=gym_id
        )


class ClassParticipationService:
    async def register_for_class(self, db: Session, member_id: int, session_id: int, redis_client: Optional[Redis] = None) -> Any:
        """Registrar a un miembro en una sesión de clase"""
        # Verificar si la sesión existe y está programada
        session_data = class_session_repository.get_with_availability(db, session_id=session_id)
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión no encontrada"
            )
        
        session = session_data["session"]
        class_obj = session_data["class"]
        
        # Verificar si la sesión está programada
        if session.status != ClassSessionStatus.SCHEDULED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede registrar en una sesión con estado {session.status}"
            )
        
        # Verificar si la sesión ya comenzó
        if session.start_time <= datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede registrar en una sesión que ya ha comenzado"
            )
        
        # Verificar si hay espacio disponible
        if session_data["is_full"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La sesión está llena"
            )
        
        # Verificar si el miembro ya está registrado
        existing = class_participation_repository.get_by_session_and_member(
            db, session_id=session_id, member_id=member_id
        )
        
        if existing:
            # Si ya está registrado pero había cancelado, reactivar
            if existing.status == ClassParticipationStatus.CANCELLED:
                updated = class_participation_repository.update(
                    db, db_obj=existing,
                    obj_in={
                        "status": ClassParticipationStatus.REGISTERED,
                        "cancellation_time": None,
                        "cancellation_reason": None
                    }
                )
                
                # Actualizar contador de participantes
                class_session_repository.update_participant_count(db, session_id=session_id)
                
                # Invalidar cachés de sesión al final
                if redis_client and updated:
                    await self._invalidate_session_caches_from_participation(redis_client, session_id)
                return updated
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ya estás registrado en esta clase"
                )
        
        # Crear nueva participación
        participation_data = ClassParticipationCreate(
            session_id=session_id,
            member_id=member_id,
            status=ClassParticipationStatus.REGISTERED,
            gym_id=session.gym_id  # Asignar el gym_id de la sesión
        )
        
        participation = class_participation_repository.create(
            db, obj_in=participation_data
        )
        
        # Actualizar contador de participantes
        class_session_repository.update_participant_count(db, session_id=session_id)
        
        # Invalidar cachés de sesión al final
        if redis_client and participation:
            await self._invalidate_session_caches_from_participation(redis_client, session_id)
        return participation
    
    async def cancel_registration(self, db: Session, member_id: int, session_id: int, reason: Optional[str] = None, redis_client: Optional[Redis] = None) -> Any:
        """Cancelar el registro de un miembro en una sesión"""
        # Verificar si la participación existe
        participation = class_participation_repository.get_by_session_and_member(
            db, session_id=session_id, member_id=member_id
        )
        
        if not participation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No estás registrado en esta clase"
            )
        
        # Verificar si ya está cancelada
        if participation.status == ClassParticipationStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tu registro ya está cancelado"
            )
        
        # Verificar si la sesión ya terminó
        session = class_session_repository.get(db, id=session_id)
        if session and session.end_time and session.end_time <= datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede cancelar un registro para una clase que ya ha terminado"
            )
        
        # Cancelar la participación
        cancelled_participation = class_participation_repository.cancel_participation(
            db, session_id=session_id, member_id=member_id, reason=reason
        )
        
        # Actualizar contador de participantes
        class_session_repository.update_participant_count(db, session_id=session_id)
        
        # Invalidar cachés de sesión al final
        if redis_client and cancelled_participation:
            await self._invalidate_session_caches_from_participation(redis_client, session_id)
        return cancelled_participation
    
    def mark_attendance(self, db: Session, member_id: int, session_id: int) -> Any:
        """Marcar la asistencia de un miembro a una sesión"""
        # Verificar si la participación existe
        participation = class_participation_repository.get_by_session_and_member(
            db, session_id=session_id, member_id=member_id
        )
        
        if not participation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El miembro no está registrado en esta clase"
            )
        
        # Verificar si ya se marcó la asistencia
        if participation.status == ClassParticipationStatus.ATTENDED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La asistencia ya fue registrada"
            )
        
        # Verificar si la participación está cancelada
        if participation.status == ClassParticipationStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede marcar asistencia para un registro cancelado"
            )
        
        # Marcar la asistencia
        return class_participation_repository.mark_attendance(
            db, session_id=session_id, member_id=member_id
        )
    
    def mark_no_show(self, db: Session, member_id: int, session_id: int) -> Any:
        """Marcar que un miembro no asistió a una sesión"""
        # Verificar si la participación existe
        participation = class_participation_repository.get_by_session_and_member(
            db, session_id=session_id, member_id=member_id
        )
        
        if not participation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El miembro no está registrado en esta clase"
            )
        
        # Verificar si la participación está cancelada
        if participation.status == ClassParticipationStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede marcar no-show para un registro cancelado"
            )
        
        # Verificar si ya se marcó la asistencia
        if participation.status == ClassParticipationStatus.ATTENDED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede marcar no-show para un registro con asistencia"
            )
        
        # Marcar como no-show
        updated = class_participation_repository.update(
            db, db_obj=participation,
            obj_in={"status": ClassParticipationStatus.NO_SHOW}
        )
        
        return updated
    
    def get_session_participants(
        self, db: Session, session_id: int, skip: int = 0, limit: int = 100, gym_id: Optional[int] = None
    ) -> List[Any]:
        """Obtener todos los participantes de una sesión"""
        return class_participation_repository.get_by_session(
            db, session_id=session_id, skip=skip, limit=limit, gym_id=gym_id
        )
    
    def get_member_participations(
        self, db: Session, member_id: int, skip: int = 0, limit: int = 100
    ) -> List[Any]:
        """Obtener todas las participaciones de un miembro"""
        return class_participation_repository.get_by_member(
            db, member_id=member_id, skip=skip, limit=limit
        )
    
    def get_member_upcoming_classes(
        self, db: Session, member_id: int, skip: int = 0, limit: int = 100, gym_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Obtener las próximas clases de un miembro"""
        return class_participation_repository.get_member_upcoming_classes(
            db, member_id=member_id, skip=skip, limit=limit, gym_id=gym_id
        )

    # Añadir método helper para invalidar caché de sesión desde participación
    async def _invalidate_session_caches_from_participation(self, redis_client: Redis, session_id: int):
        # Podríamos hacer esto más eficiente si tuviéramos gym_id y trainer_id aquí,
        # pero por ahora invalidaremos solo el detalle de la sesión que es lo más importante
        # para el contador de participantes.
        if not redis_client:
            return
        logger = logging.getLogger(__name__)
        detail_key = f"schedule:session:detail:{session_id}"
        try:
            await redis_client.delete(detail_key)
            logger.debug(f"Invalidated session detail cache from participation change: {detail_key}")
        except Exception as e:
             logger.error(f"Error invalidating session cache {detail_key}: {e}", exc_info=True)


# Instantiate services
gym_hours_service = GymHoursService()
gym_special_hours_service = GymSpecialHoursService()
category_service = ClassCategoryService()
class_service = ClassService()
class_session_service = ClassSessionService()
class_participation_service = ClassParticipationService() 