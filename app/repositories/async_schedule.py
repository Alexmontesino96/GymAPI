"""
AsyncScheduleRepositories - Repositorios async para módulo de horarios y clases.

Este archivo contiene 6 repositorios async completamente separados para el módulo schedule:
- AsyncGymHoursRepository - Horarios regulares del gimnasio
- AsyncGymSpecialHoursRepository - Horarios especiales y excepciones
- AsyncClassCategoryCustomRepository - Categorías personalizadas de clases
- AsyncClassRepository - Definiciones de clases
- AsyncClassSessionRepository - Sesiones individuales de clases
- AsyncClassParticipationRepository - Participación de miembros en sesiones

Migrado en FASE 2 de la conversión sync → async.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, time, timedelta, date, timezone
import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, func, select

from app.repositories.async_base import AsyncBaseRepository
from app.models.schedule import (
    GymHours,
    GymSpecialHours,
    Class,
    ClassSession,
    ClassParticipation,
    ClassSessionStatus,
    ClassParticipationStatus,
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


class AsyncGymHoursRepository(AsyncBaseRepository[GymHours, GymHoursCreate, GymHoursUpdate]):
    """
    Repositorio async para horarios regulares del gimnasio.

    Hereda de AsyncBaseRepository:
    - get(db, id, gym_id) - Obtener horario por ID
    - get_multi(db, skip, limit, gym_id, filters) - Obtener múltiples horarios
    - create(db, obj_in, gym_id) - Crear horario
    - update(db, db_obj, obj_in, gym_id) - Actualizar horario
    - remove(db, id, gym_id) - Eliminar horario
    - exists(db, id, gym_id) - Verificar existencia

    Métodos específicos:
    - get_by_day() - Obtener horarios para un día de la semana
    - get_all_days() - Obtener horarios de todos los días
    - get_or_create_default() - Obtener o crear horarios predeterminados
    """

    async def get_by_day(
        self,
        db: AsyncSession,
        *,
        day: int,
        gym_id: Optional[int] = None
    ) -> Optional[GymHours]:
        """
        Obtener los horarios para un día específico de la semana.

        Args:
            db: Sesión async de base de datos
            day: Día de la semana (0=Lunes, 6=Domingo)
            gym_id: ID del gimnasio para filtrar (opcional)

        Returns:
            Horarios del día especificado o None
        """
        stmt = select(GymHours).where(GymHours.day_of_week == day)

        if gym_id is not None:
            stmt = stmt.where(GymHours.gym_id == gym_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_days(
        self,
        db: AsyncSession,
        *,
        gym_id: Optional[int] = None
    ) -> List[GymHours]:
        """
        Obtener los horarios para todos los días de la semana.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio para filtrar (opcional)

        Returns:
            Lista de horarios ordenados por día de la semana
        """
        stmt = select(GymHours)

        if gym_id is not None:
            stmt = stmt.where(GymHours.gym_id == gym_id)

        stmt = stmt.order_by(GymHours.day_of_week)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_or_create_default(
        self,
        db: AsyncSession,
        *,
        day: int,
        gym_id: int
    ) -> GymHours:
        """
        Obtener horarios para un día o crear con valores predeterminados.

        Args:
            db: Sesión async de base de datos
            day: Día de la semana (0=Lunes, 6=Domingo)
            gym_id: ID del gimnasio

        Returns:
            Horarios existentes o recién creados con valores por defecto

        Note:
            Valores predeterminados: 9:00 AM - 9:00 PM
            Domingo (day=6) se marca como cerrado por defecto
        """
        hours = await self.get_by_day(db, day=day, gym_id=gym_id)
        if hours:
            return hours

        # Crear horarios predeterminados (9:00 AM - 9:00 PM, cerrado en domingo)
        is_closed = day == 6  # Domingo
        default_open = time(9, 0)  # 9:00 AM
        default_close = time(21, 0)  # 9:00 PM

        obj_in = GymHoursCreate(
            day_of_week=day,
            open_time=default_open,
            close_time=default_close,
            is_closed=is_closed,
            gym_id=gym_id
        )

        db_obj = GymHours(**obj_in.model_dump())
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj


class AsyncGymSpecialHoursRepository(
    AsyncBaseRepository[GymSpecialHours, GymSpecialHoursCreate, GymSpecialHoursUpdate]
):
    """
    Repositorio async para horarios especiales y excepciones.

    Hereda de AsyncBaseRepository:
    - get(db, id, gym_id) - Obtener horario especial por ID
    - get_multi(db, skip, limit, gym_id, filters) - Obtener múltiples horarios especiales
    - create(db, obj_in, gym_id) - Crear horario especial
    - update(db, db_obj, obj_in, gym_id) - Actualizar horario especial
    - remove(db, id, gym_id) - Eliminar horario especial
    - exists(db, id, gym_id) - Verificar existencia

    Métodos específicos:
    - get_by_date() - Horarios para una fecha específica
    - get_by_date_range() - Horarios en rango de fechas
    - get_upcoming_special_days() - Próximos días especiales
    - get_or_create_by_date() - Obtener o crear horario para fecha
    - bulk_create_or_update() - Creación/actualización masiva
    """

    async def get_by_date(
        self,
        db: AsyncSession,
        *,
        date_value: date,
        gym_id: Optional[int] = None
    ) -> Optional[GymSpecialHours]:
        """
        Obtener horarios especiales para una fecha específica.

        Args:
            db: Sesión async de base de datos
            date_value: Fecha a consultar (tipo date)
            gym_id: ID del gimnasio para filtrar (opcional)

        Returns:
            Horarios especiales para la fecha o None
        """
        stmt = select(GymSpecialHours).where(GymSpecialHours.date == date_value)

        if gym_id is not None:
            stmt = stmt.where(GymSpecialHours.gym_id == gym_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_date_range(
        self,
        db: AsyncSession,
        *,
        start_date: date,
        end_date: date,
        gym_id: Optional[int] = None
    ) -> List[GymSpecialHours]:
        """
        Obtener horarios especiales para un rango de fechas.

        Args:
            db: Sesión async de base de datos
            start_date: Fecha de inicio (tipo date)
            end_date: Fecha de fin (tipo date)
            gym_id: ID del gimnasio para filtrar (opcional)

        Returns:
            Lista de horarios especiales ordenados por fecha
        """
        stmt = select(GymSpecialHours).where(
            GymSpecialHours.date >= start_date,
            GymSpecialHours.date <= end_date
        )

        if gym_id is not None:
            stmt = stmt.where(GymSpecialHours.gym_id == gym_id)

        stmt = stmt.order_by(GymSpecialHours.date)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_upcoming_special_days(
        self,
        db: AsyncSession,
        *,
        limit: int = 10,
        gym_id: Optional[int] = None
    ) -> List[GymSpecialHours]:
        """
        Obtener los próximos días especiales.

        Args:
            db: Sesión async de base de datos
            limit: Número máximo de registros a devolver
            gym_id: ID del gimnasio para filtrar (opcional)

        Returns:
            Lista de próximos días especiales ordenados por fecha
        """
        today = dt.date.today()

        stmt = select(GymSpecialHours).where(GymSpecialHours.date >= today)

        if gym_id is not None:
            stmt = stmt.where(GymSpecialHours.gym_id == gym_id)

        stmt = stmt.order_by(GymSpecialHours.date).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_or_create_by_date(
        self,
        db: AsyncSession,
        *,
        gym_id: int,
        date_value: date,
        defaults: Optional[Dict] = None
    ) -> GymSpecialHours:
        """
        Obtiene un registro por fecha y gym_id, o lo crea si no existe.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            date_value: Fecha específica
            defaults: Diccionario con valores para crear si no existe

        Returns:
            El objeto GymSpecialHours existente o recién creado
        """
        obj = await self.get_by_date(db=db, gym_id=gym_id, date_value=date_value)
        if obj:
            return obj

        if defaults is None:
            defaults = {}

        # Asegurar que los datos incluyan fecha y gym_id
        create_data = defaults.copy()
        create_data['date'] = date_value
        create_data['gym_id'] = gym_id

        try:
            validated_data = GymSpecialHoursCreate(**create_data)
        except Exception as e:
            print(f"Error validating data for GymSpecialHours creation: {e}")
            raise

        # Crear objeto SQLAlchemy
        db_obj = self.model(**validated_data.model_dump(), gym_id=gym_id)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def bulk_create_or_update(
        self,
        db: AsyncSession,
        *,
        gym_id: int,
        schedule_data: Dict[date, Dict]
    ) -> List[GymSpecialHours]:
        """
        Crea o actualiza múltiples registros de GymSpecialHours.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            schedule_data: Diccionario donde la clave es la fecha (date) y el valor es
                          un diccionario con los datos a crear/actualizar
                          (open_time, close_time, is_closed, description)

        Returns:
            Lista de objetos GymSpecialHours creados o actualizados

        Note:
            Operación eficiente para múltiples fechas:
            - Consulta existentes una sola vez
            - Batch insert para nuevos
            - Actualiza solo los campos modificados
        """
        dates = list(schedule_data.keys())
        if not dates:
            return []

        start_date = min(dates)
        end_date = max(dates)

        # 1. Obtener registros existentes
        stmt = select(GymSpecialHours).where(
            GymSpecialHours.gym_id == gym_id,
            GymSpecialHours.date.between(start_date, end_date)
        )
        result = await db.execute(stmt)
        existing_records = result.scalars().all()
        existing_map = {record.date: record for record in existing_records}

        objects_to_add = []
        updated_objects = []

        for date_value, data in schedule_data.items():
            defaults = {
                "open_time": data.get('open_time'),
                "close_time": data.get('close_time'),
                "is_closed": data.get('is_closed', False),
                "description": data.get('description')
            }

            if date_value in existing_map:
                # Actualizar existente
                db_obj = existing_map[date_value]
                update_needed = False
                update_schema_data = {}
                for key, value in defaults.items():
                    if getattr(db_obj, key) != value:
                        setattr(db_obj, key, value)
                        update_schema_data[key] = value
                        update_needed = True

                if update_needed:
                    try:
                        GymSpecialHoursUpdate(**update_schema_data)
                    except Exception as e:
                        print(f"Validation error during update for date {date_value}: {e}")
                        continue
                    db_obj.updated_at = dt.datetime.now(dt.timezone.utc)
                    updated_objects.append(db_obj)
            else:
                # Crear nuevo
                create_data = defaults.copy()
                create_data['date'] = date_value
                create_data['gym_id'] = gym_id
                try:
                    validated_data = GymSpecialHoursCreate(**create_data)
                    db_obj = self.model(**validated_data.model_dump(), gym_id=gym_id)
                    objects_to_add.append(db_obj)
                except Exception as e:
                    print(f"Validation error during create for date {date_value}: {e}")
                    continue

        # 2. Añadir nuevos registros
        if objects_to_add:
            for obj in objects_to_add:
                db.add(obj)

        # 3. Flush todos los cambios
        try:
            await db.flush()
        except Exception as e:
            await db.rollback()
            print(f"Error during bulk commit: {e}")
            raise

        # 4. Refresh y combinar resultados
        all_results = []
        for obj in objects_to_add:
            await db.refresh(obj)
            all_results.append(obj)
        all_results.extend(updated_objects)

        # Ordenar por fecha
        all_results.sort(key=lambda x: x.date)

        return all_results


class AsyncClassCategoryCustomRepository(
    AsyncBaseRepository[ClassCategoryCustom, ClassCategoryCustomCreate, ClassCategoryCustomUpdate]
):
    """
    Repositorio async para categorías personalizadas de clases.

    Hereda de AsyncBaseRepository:
    - get(db, id, gym_id) - Obtener categoría por ID
    - get_multi(db, skip, limit, gym_id, filters) - Obtener múltiples categorías
    - create(db, obj_in, gym_id) - Crear categoría
    - update(db, db_obj, obj_in, gym_id) - Actualizar categoría
    - remove(db, id, gym_id) - Eliminar categoría
    - exists(db, id, gym_id) - Verificar existencia

    Métodos específicos:
    - get_by_gym() - Todas las categorías de un gimnasio
    - get_active_categories() - Solo categorías activas
    - get_by_name_and_gym() - Buscar categoría por nombre (case-insensitive)
    """

    async def get_by_gym(
        self,
        db: AsyncSession,
        *,
        gym_id: int
    ) -> List[ClassCategoryCustom]:
        """
        Obtener categorías de clase personalizadas para un gimnasio específico.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            Lista de categorías ordenadas alfabéticamente
        """
        stmt = select(ClassCategoryCustom).where(
            ClassCategoryCustom.gym_id == gym_id
        ).order_by(ClassCategoryCustom.name)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_active_categories(
        self,
        db: AsyncSession,
        *,
        gym_id: int
    ) -> List[ClassCategoryCustom]:
        """
        Obtener categorías activas para un gimnasio específico.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            Lista de categorías activas ordenadas alfabéticamente
        """
        stmt = select(ClassCategoryCustom).where(
            ClassCategoryCustom.gym_id == gym_id,
            ClassCategoryCustom.is_active == True
        ).order_by(ClassCategoryCustom.name)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name_and_gym(
        self,
        db: AsyncSession,
        *,
        name: str,
        gym_id: int
    ) -> Optional[ClassCategoryCustom]:
        """
        Verificar si existe una categoría con el mismo nombre en el mismo gimnasio.

        Args:
            db: Sesión async de base de datos
            name: Nombre de la categoría
            gym_id: ID del gimnasio

        Returns:
            Categoría encontrada o None

        Note:
            Comparación case-insensitive para evitar duplicados
        """
        stmt = select(ClassCategoryCustom).where(
            func.lower(ClassCategoryCustom.name) == func.lower(name),
            ClassCategoryCustom.gym_id == gym_id
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()


class AsyncClassRepository(AsyncBaseRepository[Class, ClassCreate, ClassUpdate]):
    """
    Repositorio async para definiciones de clases.

    Hereda de AsyncBaseRepository:
    - get(db, id, gym_id) - Obtener clase por ID
    - get_multi(db, skip, limit, gym_id, filters) - Obtener múltiples clases
    - create(db, obj_in, gym_id) - Crear clase
    - update(db, db_obj, obj_in, gym_id) - Actualizar clase
    - remove(db, id, gym_id) - Eliminar clase
    - exists(db, id, gym_id) - Verificar existencia

    Métodos específicos:
    - get_active_classes() - Solo clases activas
    - get_by_category() - Filtrar por categoría
    - get_by_difficulty() - Filtrar por nivel de dificultad
    - search_classes() - Búsqueda por nombre o descripción
    """

    async def get_active_classes(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Class]:
        """
        Obtener todas las clases activas.

        Args:
            db: Sesión async de base de datos
            skip: Registros a omitir (paginación)
            limit: Máximo de registros

        Returns:
            Lista de clases activas
        """
        stmt = select(Class).where(Class.is_active == True).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_category(
        self,
        db: AsyncSession,
        *,
        category: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Class]:
        """
        Obtener clases por categoría.

        Args:
            db: Sesión async de base de datos
            category: Categoría de la clase
            skip: Registros a omitir
            limit: Máximo de registros

        Returns:
            Lista de clases activas de la categoría
        """
        stmt = select(Class).where(
            Class.category == category,
            Class.is_active == True
        ).offset(skip).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_difficulty(
        self,
        db: AsyncSession,
        *,
        difficulty: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Class]:
        """
        Obtener clases por nivel de dificultad.

        Args:
            db: Sesión async de base de datos
            difficulty: Nivel de dificultad (beginner, intermediate, advanced)
            skip: Registros a omitir
            limit: Máximo de registros

        Returns:
            Lista de clases activas del nivel especificado
        """
        stmt = select(Class).where(
            Class.difficulty_level == difficulty,
            Class.is_active == True
        ).offset(skip).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def search_classes(
        self,
        db: AsyncSession,
        *,
        search: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Class]:
        """
        Buscar clases por nombre o descripción.

        Args:
            db: Sesión async de base de datos
            search: Término de búsqueda
            skip: Registros a omitir
            limit: Máximo de registros

        Returns:
            Lista de clases activas que coinciden con la búsqueda

        Note:
            Búsqueda case-insensitive en nombre y descripción
        """
        search_pattern = f"%{search}%"
        stmt = select(Class).where(
            or_(
                Class.name.ilike(search_pattern),
                Class.description.ilike(search_pattern)
            ),
            Class.is_active == True
        ).offset(skip).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())


class AsyncClassSessionRepository(
    AsyncBaseRepository[ClassSession, ClassSessionCreate, ClassSessionUpdate]
):
    """
    Repositorio async para sesiones individuales de clases.

    Hereda de AsyncBaseRepository:
    - get(db, id, gym_id) - Obtener sesión por ID
    - get_multi(db, skip, limit, gym_id, filters) - Obtener múltiples sesiones
    - create(db, obj_in, gym_id) - Crear sesión
    - update(db, db_obj, obj_in, gym_id) - Actualizar sesión
    - remove(db, id, gym_id) - Eliminar sesión
    - exists(db, id, gym_id) - Verificar existencia

    Métodos específicos:
    - get_upcoming_sessions() - Próximas sesiones programadas
    - get_by_date_range() - Sesiones en rango de fechas
    - get_by_trainer() - Sesiones de un entrenador
    - get_trainer_upcoming_sessions() - Próximas sesiones de entrenador
    - get_by_class() - Sesiones de una clase específica
    - get_with_availability() - Sesión con info de disponibilidad
    - update_participant_count() - Actualizar contador de participantes
    """

    async def get_upcoming_sessions(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        gym_id: Optional[int] = None
    ) -> List[ClassSession]:
        """
        Obtener las próximas sesiones de clase.

        Args:
            db: Sesión async de base de datos
            skip: Registros a omitir (paginación)
            limit: Máximo de registros
            gym_id: ID del gimnasio para filtrar (opcional)

        Returns:
            Lista de sesiones futuras programadas ordenadas por hora de inicio
        """
        now = datetime.now(timezone.utc)

        stmt = select(ClassSession).where(
            ClassSession.start_time >= now,
            ClassSession.status == ClassSessionStatus.SCHEDULED
        )

        if gym_id is not None:
            stmt = stmt.where(ClassSession.gym_id == gym_id)

        stmt = stmt.order_by(ClassSession.start_time).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_date_range(
        self,
        db: AsyncSession,
        *,
        start_date: datetime,
        end_date: datetime,
        skip: int = 0,
        limit: int = 100,
        gym_id: Optional[int] = None
    ) -> List[ClassSession]:
        """
        Obtener sesiones en un rango de fechas.

        Args:
            db: Sesión async de base de datos
            start_date: Fecha de inicio
            end_date: Fecha de fin
            skip: Registros a omitir
            limit: Máximo de registros
            gym_id: ID del gimnasio para filtrar (opcional)

        Returns:
            Lista de sesiones en el rango ordenadas por hora de inicio

        Note:
            Asegura que los datetimes sean timezone-aware (UTC)
        """
        # Asegurar datetimes aware en UTC
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        stmt = select(ClassSession).where(
            ClassSession.start_time >= start_date,
            ClassSession.start_time <= end_date
        )

        if gym_id is not None:
            stmt = stmt.where(ClassSession.gym_id == gym_id)

        stmt = stmt.order_by(ClassSession.start_time).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_trainer(
        self,
        db: AsyncSession,
        *,
        trainer_id: int,
        skip: int = 0,
        limit: int = 100,
        gym_id: Optional[int] = None
    ) -> List[ClassSession]:
        """
        Obtener sesiones de un entrenador específico.

        Args:
            db: Sesión async de base de datos
            trainer_id: ID del entrenador
            skip: Registros a omitir
            limit: Máximo de registros
            gym_id: ID del gimnasio para filtrar (opcional)

        Returns:
            Lista de sesiones del entrenador ordenadas por hora de inicio
        """
        stmt = select(ClassSession).where(ClassSession.trainer_id == trainer_id)

        if gym_id is not None:
            stmt = stmt.where(ClassSession.gym_id == gym_id)

        stmt = stmt.order_by(ClassSession.start_time).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_trainer_upcoming_sessions(
        self,
        db: AsyncSession,
        *,
        trainer_id: int,
        skip: int = 0,
        limit: int = 100,
        gym_id: Optional[int] = None
    ) -> List[ClassSession]:
        """
        Obtener las próximas sesiones de un entrenador específico.

        Args:
            db: Sesión async de base de datos
            trainer_id: ID del entrenador
            skip: Registros a omitir
            limit: Máximo de registros
            gym_id: ID del gimnasio para filtrar (opcional)

        Returns:
            Lista de próximas sesiones programadas del entrenador
        """
        now = datetime.now(timezone.utc)

        stmt = select(ClassSession).where(
            ClassSession.trainer_id == trainer_id,
            ClassSession.start_time >= now,
            ClassSession.status == ClassSessionStatus.SCHEDULED
        )

        if gym_id is not None:
            stmt = stmt.where(ClassSession.gym_id == gym_id)

        stmt = stmt.order_by(ClassSession.start_time).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_class(
        self,
        db: AsyncSession,
        *,
        class_id: int,
        skip: int = 0,
        limit: int = 100,
        gym_id: Optional[int] = None
    ) -> List[ClassSession]:
        """
        Obtener sesiones de una clase específica.

        Args:
            db: Sesión async de base de datos
            class_id: ID de la clase
            skip: Registros a omitir
            limit: Máximo de registros
            gym_id: ID del gimnasio para filtrar (opcional)

        Returns:
            Lista de sesiones de la clase ordenadas por hora de inicio
        """
        stmt = select(ClassSession).where(ClassSession.class_id == class_id)

        if gym_id is not None:
            stmt = stmt.where(ClassSession.gym_id == gym_id)

        stmt = stmt.order_by(ClassSession.start_time).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_with_availability(
        self,
        db: AsyncSession,
        *,
        session_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Obtener sesión con información de disponibilidad.

        Args:
            db: Sesión async de base de datos
            session_id: ID de la sesión

        Returns:
            Diccionario con:
            - session: Objeto ClassSession
            - class: Objeto Class
            - registered_count: Número de participantes registrados
            - available_spots: Cupos disponibles
            - is_full: Boolean indicando si está llena

        Note:
            Usa override_capacity de la sesión si está definida,
            si no, usa max_capacity de la clase
        """
        # Get session
        session_stmt = select(ClassSession).where(ClassSession.id == session_id)
        session_result = await db.execute(session_stmt)
        session = session_result.scalar_one_or_none()
        if not session:
            return None

        # Get class
        class_stmt = select(Class).where(Class.id == session.class_id)
        class_result = await db.execute(class_stmt)
        class_obj = class_result.scalar_one_or_none()
        if not class_obj:
            return None

        # Count registered participants
        count_stmt = select(func.count(ClassParticipation.id)).where(
            ClassParticipation.session_id == session_id,
            ClassParticipation.status == ClassParticipationStatus.REGISTERED
        )
        count_result = await db.execute(count_stmt)
        registered_count = count_result.scalar()

        # Calculate availability
        capacity = session.override_capacity if session.override_capacity is not None else class_obj.max_capacity
        available_spots = capacity - registered_count
        is_full = available_spots <= 0

        return {
            "session": session,
            "class": class_obj,
            "registered_count": registered_count,
            "available_spots": available_spots,
            "is_full": is_full
        }

    async def update_participant_count(
        self,
        db: AsyncSession,
        *,
        session_id: int
    ) -> Optional[ClassSession]:
        """
        Actualizar el contador de participantes de una sesión.

        Args:
            db: Sesión async de base de datos
            session_id: ID de la sesión

        Returns:
            Sesión actualizada o None si no existe

        Note:
            Cuenta solo participantes con status REGISTERED
            (excluye cancelados y no-show)
        """
        # Get session
        session_stmt = select(ClassSession).where(ClassSession.id == session_id)
        session_result = await db.execute(session_stmt)
        session = session_result.scalar_one_or_none()
        if not session:
            return None

        # Count registered participants
        count_stmt = select(func.count(ClassParticipation.id)).where(
            ClassParticipation.session_id == session_id,
            ClassParticipation.status == ClassParticipationStatus.REGISTERED
        )
        count_result = await db.execute(count_stmt)
        registered_count = count_result.scalar()

        session.current_participants = registered_count
        await db.flush()
        await db.refresh(session)

        return session


class AsyncClassParticipationRepository(
    AsyncBaseRepository[ClassParticipation, ClassParticipationCreate, ClassParticipationUpdate]
):
    """
    Repositorio async para participación de miembros en sesiones.

    Hereda de AsyncBaseRepository:
    - get(db, id, gym_id) - Obtener participación por ID
    - get_multi(db, skip, limit, gym_id, filters) - Obtener múltiples participaciones
    - create(db, obj_in, gym_id) - Crear participación
    - update(db, db_obj, obj_in, gym_id) - Actualizar participación
    - remove(db, id, gym_id) - Eliminar participación
    - exists(db, id, gym_id) - Verificar existencia

    Métodos específicos:
    - get_by_session_and_member() - Participación específica
    - get_by_session() - Todas las participaciones de una sesión
    - get_by_member() - Todas las participaciones de un miembro
    - get_member_upcoming_classes() - Próximas clases de un miembro
    - mark_attendance() - Marcar asistencia
    - get_member_participation_status() - Estados de participación (optimizado)
    - cancel_participation() - Cancelar participación
    """

    async def get_by_session_and_member(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        member_id: int,
        gym_id: Optional[int] = None
    ) -> Optional[ClassParticipation]:
        """
        Obtener la participación de un miembro en una sesión específica.

        Args:
            db: Sesión async de base de datos
            session_id: ID de la sesión
            member_id: ID del miembro
            gym_id: ID del gimnasio para filtrar (opcional)

        Returns:
            Participación encontrada o None
        """
        stmt = select(ClassParticipation).where(
            ClassParticipation.session_id == session_id,
            ClassParticipation.member_id == member_id
        )

        if gym_id is not None:
            stmt = stmt.where(ClassParticipation.gym_id == gym_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_session(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        skip: int = 0,
        limit: int = 100,
        gym_id: Optional[int] = None
    ) -> List[ClassParticipation]:
        """
        Obtener todas las participaciones para una sesión específica.

        Args:
            db: Sesión async de base de datos
            session_id: ID de la sesión
            skip: Registros a omitir
            limit: Máximo de registros
            gym_id: ID del gimnasio para filtrar (opcional)

        Returns:
            Lista de participaciones de la sesión
        """
        stmt = select(ClassParticipation).where(
            ClassParticipation.session_id == session_id
        )

        if gym_id is not None:
            stmt = stmt.where(ClassParticipation.gym_id == gym_id)

        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_member(
        self,
        db: AsyncSession,
        *,
        member_id: int,
        skip: int = 0,
        limit: int = 100,
        gym_id: Optional[int] = None
    ) -> List[ClassParticipation]:
        """
        Obtener todas las participaciones de un miembro específico.

        Args:
            db: Sesión async de base de datos
            member_id: ID del miembro
            skip: Registros a omitir
            limit: Máximo de registros
            gym_id: ID del gimnasio para filtrar (opcional)

        Returns:
            Lista de participaciones del miembro
        """
        stmt = select(ClassParticipation).where(
            ClassParticipation.member_id == member_id
        )

        if gym_id is not None:
            stmt = stmt.where(ClassParticipation.gym_id == gym_id)

        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_member_upcoming_classes(
        self,
        db: AsyncSession,
        *,
        member_id: int,
        skip: int = 0,
        limit: int = 100,
        gym_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtener las próximas clases de un miembro.

        Args:
            db: Sesión async de base de datos
            member_id: ID del miembro
            skip: Registros a omitir
            limit: Máximo de registros
            gym_id: ID del gimnasio para filtrar (opcional)

        Returns:
            Lista de diccionarios con:
            - participation: Objeto ClassParticipation
            - session: Objeto ClassSession
            - class: Objeto Class

        Note:
            Solo incluye participaciones REGISTERED en sesiones SCHEDULED futuras
        """
        now = datetime.now(timezone.utc)

        stmt = select(
            ClassParticipation, ClassSession, Class
        ).join(
            ClassSession, ClassParticipation.session_id == ClassSession.id
        ).join(
            Class, ClassSession.class_id == Class.id
        ).where(
            ClassParticipation.member_id == member_id,
            ClassParticipation.status == ClassParticipationStatus.REGISTERED,
            ClassSession.start_time >= now,
            ClassSession.status == ClassSessionStatus.SCHEDULED
        )

        if gym_id is not None:
            stmt = stmt.where(ClassParticipation.gym_id == gym_id)

        stmt = stmt.order_by(ClassSession.start_time).offset(skip).limit(limit)
        result = await db.execute(stmt)
        participations = result.all()

        return [
            {
                "participation": participation,
                "session": session,
                "class": class_obj
            }
            for participation, session, class_obj in participations
        ]

    async def mark_attendance(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        member_id: int,
        gym_id: Optional[int] = None
    ) -> Optional[ClassParticipation]:
        """
        Marcar la asistencia de un miembro a una sesión.

        Args:
            db: Sesión async de base de datos
            session_id: ID de la sesión
            member_id: ID del miembro
            gym_id: ID del gimnasio para filtrar (opcional)

        Returns:
            Participación actualizada con asistencia marcada o None

        Note:
            Actualiza status a ATTENDED y registra attendance_time
        """
        participation = await self.get_by_session_and_member(
            db, session_id=session_id, member_id=member_id, gym_id=gym_id
        )

        if not participation:
            return None

        # Actualizar estado y tiempo de asistencia
        participation.status = ClassParticipationStatus.ATTENDED
        participation.attendance_time = datetime.now(timezone.utc)

        await db.flush()
        await db.refresh(participation)

        return participation

    async def get_member_participation_status(
        self,
        db: AsyncSession,
        *,
        member_id: int,
        start_date: datetime,
        end_date: datetime,
        gym_id: Optional[int] = None,
        session_ids: Optional[List[int]] = None
    ) -> List[ClassParticipation]:
        """
        Obtener estados de participación de un miembro (query ultra-optimizada).

        Este método está diseñado para ser extremadamente rápido ya que:
        - No hace joins innecesarios con session o class
        - Solo selecciona los campos mínimos necesarios
        - Usa indexes optimizados

        Args:
            db: Sesión async de base de datos
            member_id: ID del miembro
            start_date: Fecha de inicio (UTC)
            end_date: Fecha de fin (UTC)
            gym_id: ID del gimnasio para filtrar (opcional)
            session_ids: Lista específica de session_ids para filtrar (opcional)

        Returns:
            Lista de objetos ClassParticipation (solo con campos básicos)

        Note:
            Si se proporciona session_ids, ignora el filtro de fechas
        """
        stmt = select(ClassParticipation).where(
            ClassParticipation.member_id == member_id
        )

        if gym_id is not None:
            stmt = stmt.where(ClassParticipation.gym_id == gym_id)

        if session_ids:
            stmt = stmt.where(ClassParticipation.session_id.in_(session_ids))
        else:
            # Asegurar datetimes aware (UTC)
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=timezone.utc)
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)

            # Join con session solo para filtrar por fechas
            stmt = stmt.join(
                ClassSession, ClassParticipation.session_id == ClassSession.id
            ).where(
                ClassSession.start_time >= start_date,
                ClassSession.start_time <= end_date
            )

        stmt = stmt.order_by(ClassParticipation.registration_time.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def cancel_participation(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        member_id: int,
        reason: Optional[str] = None,
        gym_id: Optional[int] = None
    ) -> Optional[ClassParticipation]:
        """
        Cancelar la participación de un miembro en una sesión.

        Args:
            db: Sesión async de base de datos
            session_id: ID de la sesión
            member_id: ID del miembro
            reason: Razón de cancelación (opcional)
            gym_id: ID del gimnasio para filtrar (opcional)

        Returns:
            Participación cancelada o None si no existe

        Note:
            - Actualiza status a CANCELLED
            - Registra cancellation_time
            - Guarda cancellation_reason si se proporciona
            - Actualiza contador de participantes en la sesión
        """
        participation = await self.get_by_session_and_member(
            db, session_id=session_id, member_id=member_id, gym_id=gym_id
        )

        if not participation:
            return None

        # Actualizar estado, razón y hora de cancelación
        participation.status = ClassParticipationStatus.CANCELLED
        participation.cancellation_time = datetime.now(timezone.utc)
        if reason:
            participation.cancellation_reason = reason

        await db.flush()
        await db.refresh(participation)

        # Actualizar conteo de participantes en la sesión
        session_repo = AsyncClassSessionRepository(ClassSession)
        await session_repo.update_participant_count(db, session_id=session_id)

        return participation


# Instancias singleton de los repositorios async
async_gym_hours_repository = AsyncGymHoursRepository(GymHours)
async_gym_special_hours_repository = AsyncGymSpecialHoursRepository(GymSpecialHours)
async_class_category_repository = AsyncClassCategoryCustomRepository(ClassCategoryCustom)
async_class_repository = AsyncClassRepository(Class)
async_class_session_repository = AsyncClassSessionRepository(ClassSession)
async_class_participation_repository = AsyncClassParticipationRepository(ClassParticipation)
