from typing import List, Optional, Dict, Any, Union, Type
from datetime import datetime, time, timedelta, date, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import datetime as dt

from app.repositories.base import BaseRepository
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


class GymHoursRepository(BaseRepository[GymHours, GymHoursCreate, GymHoursUpdate]):
    def get_by_day(self, db: Session, *, day: int, gym_id: Optional[int] = None) -> Optional[GymHours]:
        """
        Obtener los horarios para un día específico de la semana.
        
        Args:
            db: Sesión de base de datos
            day: Día de la semana (0=Lunes, 6=Domingo)
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        query = db.query(GymHours).filter(GymHours.day_of_week == day)
        
        if gym_id is not None:
            query = query.filter(GymHours.gym_id == gym_id)
            
        return query.first()
    
    def get_all_days(self, db: Session, *, gym_id: Optional[int] = None) -> List[GymHours]:
        """
        Obtener los horarios para todos los días de la semana.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        query = db.query(GymHours)
        
        if gym_id is not None:
            query = query.filter(GymHours.gym_id == gym_id)
            
        return query.order_by(GymHours.day_of_week).all()
    
    def get_or_create_default(self, db: Session, *, day: int, gym_id: int) -> GymHours:
        """
        Obtener horarios para un día o crear con valores predeterminados.
        
        Args:
            db: Sesión de base de datos
            day: Día de la semana (0=Lunes, 6=Domingo)
            gym_id: ID del gimnasio
        """
        hours = self.get_by_day(db, day=day, gym_id=gym_id)
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
        return self.create(db, obj_in=obj_in)


class GymSpecialHoursRepository(BaseRepository[GymSpecialHours, GymSpecialHoursCreate, GymSpecialHoursUpdate]):
    def get_by_date(self, db: Session, *, date_value: date, gym_id: Optional[int] = None) -> Optional[GymSpecialHours]:
        """
        Obtener horarios especiales para una fecha específica.
        
        Args:
            db: Sesión de base de datos
            date_value: Fecha a consultar (tipo date)
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        # Comparar directamente con la columna Date
        query = db.query(GymSpecialHours).filter(GymSpecialHours.date == date_value)
        
        if gym_id is not None:
            query = query.filter(GymSpecialHours.gym_id == gym_id)
            
        return query.first()
    
    def get_by_date_range(
        self, db: Session, *, start_date: date, end_date: date, gym_id: Optional[int] = None
    ) -> List[GymSpecialHours]:
        """
        Obtener horarios especiales para un rango de fechas.
        
        Args:
            db: Sesión de base de datos
            start_date: Fecha de inicio (tipo date)
            end_date: Fecha de fin (tipo date)
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        query = db.query(GymSpecialHours).filter(
            GymSpecialHours.date >= start_date, 
            GymSpecialHours.date <= end_date
        )
        
        if gym_id is not None:
            query = query.filter(GymSpecialHours.gym_id == gym_id)
            
        return query.order_by(GymSpecialHours.date).all()
    
    def get_upcoming_special_days(
        self, db: Session, *, limit: int = 10, gym_id: Optional[int] = None
    ) -> List[GymSpecialHours]:
        """
        Obtener los próximos días especiales.
        
        Args:
            db: Sesión de base de datos
            limit: Número máximo de registros a devolver
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        today = dt.date.today() # Usar date.today()
        
        query = db.query(GymSpecialHours).filter(GymSpecialHours.date >= today)
        
        if gym_id is not None:
            query = query.filter(GymSpecialHours.gym_id == gym_id)
            
        return query.order_by(GymSpecialHours.date).limit(limit).all()
        
    def get_or_create_by_date(self, db: Session, *, gym_id: int, date_value: date, defaults: Optional[Dict] = None) -> GymSpecialHours:
        """
        Obtiene un registro por fecha y gym_id, o lo crea si no existe.

        Args:
            db: Sesión de base de datos.
            gym_id: ID del gimnasio.
            date_value: Fecha específica.
            defaults: Diccionario con valores para crear si no existe.

        Returns:
            El objeto GymSpecialHours existente o recién creado.
        """
        obj = self.get_by_date(db=db, gym_id=gym_id, date_value=date_value)
        if obj:
            return obj
        if defaults is None:
            defaults = {}
        
        # Asegurar que los datos para crear incluyan fecha y gym_id
        create_data = defaults.copy()
        create_data['date'] = date_value
        create_data['gym_id'] = gym_id
        
        try:
            validated_data = GymSpecialHoursCreate(**create_data)
        except Exception as e:
            print(f"Error validating data for GymSpecialHours creation: {e}")
            raise

        # Crear objeto SQLAlchemy incluyendo gym_id explícitamente
        db_obj = self.model(**validated_data.model_dump(), gym_id=gym_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def bulk_create_or_update(self, db: Session, *, gym_id: int, schedule_data: Dict[date, Dict]) -> List[GymSpecialHours]:
        """
        Crea o actualiza múltiples registros de GymSpecialHours para un rango de fechas.
        Intenta ser eficiente usando consultas para encontrar existentes y luego insertando/actualizando.

        Args:
            db: Sesión de base de datos.
            gym_id: ID del gimnasio.
            schedule_data: Diccionario donde la clave es la fecha (date) y el valor es 
                           un diccionario con los datos a crear/actualizar 
                           (open_time, close_time, is_closed, description).

        Returns:
            Lista de objetos GymSpecialHours creados o actualizados.
        """
        dates = list(schedule_data.keys())
        if not dates:
            return []

        start_date = min(dates)
        end_date = max(dates)

        # 1. Obtener los registros existentes en el rango
        existing_records_query = db.query(GymSpecialHours).filter(
            GymSpecialHours.gym_id == gym_id,
            GymSpecialHours.date.between(start_date, end_date)
        )
        existing_map = {record.date: record for record in existing_records_query}

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
                # Actualizar existente si hay cambios
                db_obj = existing_map[date_value]
                update_needed = False
                update_schema_data = {}
                for key, value in defaults.items():
                    if getattr(db_obj, key) != value:
                        setattr(db_obj, key, value) # Actualizar en el objeto SQLAlchemy
                        update_schema_data[key] = value
                        update_needed = True
                
                if update_needed:
                    # Validar con el esquema de actualización (aunque ya se aplicó al obj)
                    try:
                        GymSpecialHoursUpdate(**update_schema_data)
                    except Exception as e:
                        print(f"Validation error during update for date {date_value}: {e}")
                        continue # O manejar el error
                    db_obj.updated_at = dt.datetime.now(dt.timezone.utc) # Manually set timestamp
                    # El objeto ya está en la sesión, se marcará como modificado.
                    updated_objects.append(db_obj)
            else:
                # Crear nuevo
                create_data = defaults.copy()
                create_data['date'] = date_value
                create_data['gym_id'] = gym_id
                try:
                    # Validar con esquema de creación
                    validated_data = GymSpecialHoursCreate(**create_data)
                    # validated_data no incluye gym_id (extra ignorado). Añadirlo al crear el modelo.
                    db_obj = self.model(**validated_data.model_dump(), gym_id=gym_id)
                    objects_to_add.append(db_obj)
                except Exception as e:
                     print(f"Validation error during create for date {date_value}: {e}")
                     continue # O manejar el error

        # 2. Añadir nuevos registros en bloque (si los hay)
        if objects_to_add:
            db.add_all(objects_to_add)

        # 3. Cometer todos los cambios (actualizaciones y nuevas inserciones)
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Error during bulk commit: {e}")
            raise

        # 4. Refrescar objetos para obtener IDs y timestamps generados por la BD
        #    y combinarlos con los actualizados que no necesitaron refresh.
        all_results = []
        for obj in objects_to_add:
            db.refresh(obj)
            all_results.append(obj)
        all_results.extend(updated_objects) # Añadir los que solo se actualizaron
        
        # Ordenar por fecha antes de devolver
        all_results.sort(key=lambda x: x.date)
        
        return all_results


class ClassCategoryCustomRepository(BaseRepository[ClassCategoryCustom, ClassCategoryCustomCreate, ClassCategoryCustomUpdate]):
    def get_by_gym(self, db: Session, *, gym_id: int) -> List[ClassCategoryCustom]:
        """Obtener categorías de clase personalizadas para un gimnasio específico"""
        return db.query(ClassCategoryCustom).filter(
            ClassCategoryCustom.gym_id == gym_id
        ).order_by(ClassCategoryCustom.name).all()
    
    def get_active_categories(self, db: Session, *, gym_id: int) -> List[ClassCategoryCustom]:
        """Obtener categorías activas para un gimnasio específico"""
        return db.query(ClassCategoryCustom).filter(
            ClassCategoryCustom.gym_id == gym_id,
            ClassCategoryCustom.is_active == True
        ).order_by(ClassCategoryCustom.name).all()
    
    def get_by_name_and_gym(self, db: Session, *, name: str, gym_id: int) -> Optional[ClassCategoryCustom]:
        """Verificar si existe una categoría con el mismo nombre en el mismo gimnasio"""
        return db.query(ClassCategoryCustom).filter(
            func.lower(ClassCategoryCustom.name) == func.lower(name), # Comparación case-insensitive
            ClassCategoryCustom.gym_id == gym_id
        ).first()


class ClassRepository(BaseRepository[Class, ClassCreate, ClassUpdate]):
    def get_active_classes(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Class]:
        """Obtener todas las clases activas"""
        return db.query(Class).filter(Class.is_active == True).offset(skip).limit(limit).all()
    
    def get_by_category(
        self, db: Session, *, category: str, skip: int = 0, limit: int = 100
    ) -> List[Class]:
        """Obtener clases por categoría"""
        return db.query(Class).filter(
            Class.category == category,
            Class.is_active == True
        ).offset(skip).limit(limit).all()
    
    def get_by_difficulty(
        self, db: Session, *, difficulty: str, skip: int = 0, limit: int = 100
    ) -> List[Class]:
        """Obtener clases por nivel de dificultad"""
        return db.query(Class).filter(
            Class.difficulty_level == difficulty,
            Class.is_active == True
        ).offset(skip).limit(limit).all()
    
    def search_classes(
        self, db: Session, *, search: str, skip: int = 0, limit: int = 100
    ) -> List[Class]:
        """Buscar clases por nombre o descripción"""
        search_pattern = f"%{search}%"
        return db.query(Class).filter(
            or_(
                Class.name.ilike(search_pattern),
                Class.description.ilike(search_pattern)
            ),
            Class.is_active == True
        ).offset(skip).limit(limit).all()


class ClassSessionRepository(BaseRepository[ClassSession, ClassSessionCreate, ClassSessionUpdate]):
    def get_upcoming_sessions(
        self, db: Session, *, skip: int = 0, limit: int = 100, gym_id: Optional[int] = None
    ) -> List[ClassSession]:
        """
        Obtener las próximas sesiones de clase.
        
        Args:
            db: Sesión de base de datos
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver (paginación)
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        now = datetime.now(timezone.utc)
        
        query = db.query(ClassSession).filter(
            ClassSession.start_time >= now,
            ClassSession.status == ClassSessionStatus.SCHEDULED
        )
        
        if gym_id is not None:
            query = query.filter(ClassSession.gym_id == gym_id)
            
        return query.order_by(ClassSession.start_time).offset(skip).limit(limit).all()
    
    def get_by_date_range(
        self, db: Session, *, start_date: datetime, end_date: datetime, 
        skip: int = 0, limit: int = 100, gym_id: Optional[int] = None
    ) -> List[ClassSession]:
        """
        Obtener sesiones en un rango de fechas.
        
        Args:
            db: Sesión de base de datos
            start_date: Fecha de inicio
            end_date: Fecha de fin
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver (paginación)
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        query = db.query(ClassSession).filter(
            ClassSession.start_time >= start_date,
            ClassSession.start_time <= end_date
        )
        
        if gym_id is not None:
            query = query.filter(ClassSession.gym_id == gym_id)
            
        return query.order_by(ClassSession.start_time).offset(skip).limit(limit).all()
    
    def get_by_trainer(
        self, db: Session, *, trainer_id: int, skip: int = 0, limit: int = 100, gym_id: Optional[int] = None
    ) -> List[ClassSession]:
        """
        Obtener sesiones de un entrenador específico.
        
        Args:
            db: Sesión de base de datos
            trainer_id: ID del entrenador
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver (paginación)
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        query = db.query(ClassSession).filter(ClassSession.trainer_id == trainer_id)
        
        if gym_id is not None:
            query = query.filter(ClassSession.gym_id == gym_id)
            
        return query.order_by(ClassSession.start_time).offset(skip).limit(limit).all()
    
    def get_trainer_upcoming_sessions(
        self, db: Session, *, trainer_id: int, skip: int = 0, limit: int = 100, gym_id: Optional[int] = None
    ) -> List[ClassSession]:
        """
        Obtener las próximas sesiones de un entrenador específico.
        
        Args:
            db: Sesión de base de datos
            trainer_id: ID del entrenador
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver (paginación)
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        now = datetime.now(timezone.utc)
        
        query = db.query(ClassSession).filter(
            ClassSession.trainer_id == trainer_id,
            ClassSession.start_time >= now,
            ClassSession.status == ClassSessionStatus.SCHEDULED
        )
        
        if gym_id is not None:
            query = query.filter(ClassSession.gym_id == gym_id)
            
        return query.order_by(ClassSession.start_time).offset(skip).limit(limit).all()
    
    def get_by_class(
        self, db: Session, *, class_id: int, skip: int = 0, limit: int = 100, gym_id: Optional[int] = None
    ) -> List[ClassSession]:
        """
        Obtener sesiones de una clase específica.
        
        Args:
            db: Sesión de base de datos
            class_id: ID de la clase
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver (paginación)
            gym_id: ID del gimnasio para filtrar (opcional)
        """
        query = db.query(ClassSession).filter(ClassSession.class_id == class_id)
        
        if gym_id is not None:
            query = query.filter(ClassSession.gym_id == gym_id)
            
        return query.order_by(ClassSession.start_time).offset(skip).limit(limit).all()
    
    def get_with_availability(
        self, db: Session, *, session_id: int
    ) -> Optional[Dict[str, Any]]:
        """Obtener sesión con información de disponibilidad"""
        session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
        if not session:
            return None
        
        class_obj = db.query(Class).filter(Class.id == session.class_id).first()
        if not class_obj:
            return None
        
        registered_count = db.query(ClassParticipation).filter(
            ClassParticipation.session_id == session_id,
            ClassParticipation.status == ClassParticipationStatus.REGISTERED
        ).count()
        
        # Usar la capacidad de la sesión si está definida, si no, la de la clase
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
    
    def update_participant_count(self, db: Session, *, session_id: int) -> Optional[ClassSession]:
        """Actualizar el contador de participantes de una sesión"""
        session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
        if not session:
            return None
        
        # Contar participantes registrados (no cancelados o no-show)
        registered_count = db.query(ClassParticipation).filter(
            ClassParticipation.session_id == session_id,
            ClassParticipation.status == ClassParticipationStatus.REGISTERED
        ).count()
        
        session.current_participants = registered_count
        db.commit()
        db.refresh(session)
        
        return session


class ClassParticipationRepository(BaseRepository[ClassParticipation, ClassParticipationCreate, ClassParticipationUpdate]):
    def get_by_session_and_member(
        self, db: Session, *, session_id: int, member_id: int, gym_id: Optional[int] = None
    ) -> Optional[ClassParticipation]:
        """Obtener la participación de un miembro en una sesión específica"""
        query = db.query(ClassParticipation).filter(
            ClassParticipation.session_id == session_id,
            ClassParticipation.member_id == member_id
        )
        
        # Filtrar por gym_id si se proporciona
        if gym_id is not None:
            query = query.filter(ClassParticipation.gym_id == gym_id)
            
        return query.first()
    
    def get_by_session(
        self, db: Session, *, session_id: int, skip: int = 0, limit: int = 100, gym_id: Optional[int] = None
    ) -> List[ClassParticipation]:
        """Obtener todas las participaciones para una sesión específica"""
        query = db.query(ClassParticipation).filter(
            ClassParticipation.session_id == session_id
        )
        
        # Filtrar por gym_id si se proporciona
        if gym_id is not None:
            query = query.filter(ClassParticipation.gym_id == gym_id)
            
        return query.offset(skip).limit(limit).all()
    
    def get_by_member(
        self, db: Session, *, member_id: int, skip: int = 0, limit: int = 100, gym_id: Optional[int] = None
    ) -> List[ClassParticipation]:
        """Obtener todas las participaciones de un miembro específico"""
        query = db.query(ClassParticipation).filter(
            ClassParticipation.member_id == member_id
        )
        
        # Filtrar por gym_id si se proporciona
        if gym_id is not None:
            query = query.filter(ClassParticipation.gym_id == gym_id)
            
        return query.offset(skip).limit(limit).all()
    
    def get_member_upcoming_classes(
        self, db: Session, *, member_id: int, skip: int = 0, limit: int = 100, gym_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Obtener las próximas clases de un miembro"""
        now = datetime.now(timezone.utc)
        
        # Construir la consulta base
        query = db.query(
            ClassParticipation, ClassSession, Class
        ).join(
            ClassSession, ClassParticipation.session_id == ClassSession.id
        ).join(
            Class, ClassSession.class_id == Class.id
        ).filter(
            ClassParticipation.member_id == member_id,
            ClassParticipation.status == ClassParticipationStatus.REGISTERED,
            ClassSession.start_time >= now,
            ClassSession.status == ClassSessionStatus.SCHEDULED
        )
        
        # Filtrar por gym_id si se proporciona
        if gym_id is not None:
            query = query.filter(ClassParticipation.gym_id == gym_id)
            
        # Ordenar y paginar los resultados
        participations = query.order_by(
            ClassSession.start_time
        ).offset(skip).limit(limit).all()
        
        result = []
        for participation, session, class_obj in participations:
            result.append({
                "participation": participation,
                "session": session,
                "class": class_obj
            })
        
        return result
    
    def mark_attendance(
        self, db: Session, *, session_id: int, member_id: int, gym_id: Optional[int] = None
    ) -> Optional[ClassParticipation]:
        """Marcar la asistencia de un miembro a una sesión"""
        participation = self.get_by_session_and_member(
            db, session_id=session_id, member_id=member_id, gym_id=gym_id
        )
        
        if not participation:
            return None
        
        # Actualizar el estado y la hora de asistencia
        participation.status = ClassParticipationStatus.ATTENDED
        participation.attendance_time = datetime.now()
        
        db.commit()
        db.refresh(participation)
        
        return participation
    
    def cancel_participation(
        self, db: Session, *, session_id: int, member_id: int, reason: Optional[str] = None, 
        gym_id: Optional[int] = None
    ) -> Optional[ClassParticipation]:
        """Cancelar la participación de un miembro en una sesión"""
        participation = self.get_by_session_and_member(
            db, session_id=session_id, member_id=member_id, gym_id=gym_id
        )
        
        if not participation:
            return None
        
        # Actualizar el estado, razón y hora de cancelación
        participation.status = ClassParticipationStatus.CANCELLED
        participation.cancellation_time = datetime.now()
        if reason:
            participation.cancellation_reason = reason
        
        db.commit()
        db.refresh(participation)
        
        # Actualizar el conteo de participantes en la sesión
        session_repo = ClassSessionRepository(ClassSession)
        session_repo.update_participant_count(db, session_id=session_id)
        
        return participation


# Instantiate repositories
gym_hours_repository = GymHoursRepository(GymHours)
gym_special_hours_repository = GymSpecialHoursRepository(GymSpecialHours)
class_category_repository = ClassCategoryCustomRepository(ClassCategoryCustom)
class_repository = ClassRepository(Class)
class_session_repository = ClassSessionRepository(ClassSession)
class_participation_repository = ClassParticipationRepository(ClassParticipation) 