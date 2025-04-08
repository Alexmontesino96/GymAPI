from typing import List, Optional, Dict, Any, Union
from datetime import datetime, time, timedelta, date
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.schedule import (
    gym_hours_repository,
    gym_special_hours_repository,
    class_repository,
    class_session_repository,
    class_participation_repository
)
from app.models.schedule import (
    ClassSessionStatus,
    ClassParticipationStatus,
    DayOfWeek
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
    ClassParticipationUpdate
)


class GymHoursService:
    def get_gym_hours_by_day(self, db: Session, day: int) -> Any:
        """Obtener los horarios del gimnasio para un día específico"""
        return gym_hours_repository.get_by_day(db, day=day)
    
    def get_all_gym_hours(self, db: Session) -> List[Any]:
        """Obtener los horarios del gimnasio para todos los días de la semana"""
        return gym_hours_repository.get_all_days(db)
    
    def create_or_update_gym_hours(
        self, db: Session, day: int, gym_hours_data: Union[GymHoursCreate, GymHoursUpdate]
    ) -> Any:
        """Crear o actualizar los horarios del gimnasio para un día específico"""
        existing_hours = gym_hours_repository.get_by_day(db, day=day)
        if existing_hours:
            return gym_hours_repository.update(db, db_obj=existing_hours, obj_in=gym_hours_data)
        
        # Crear nuevos horarios
        if isinstance(gym_hours_data, GymHoursUpdate):
            # Convertir GymHoursUpdate a GymHoursCreate con valores predeterminados
            create_data = {
                "day_of_week": day,
                "open_time": gym_hours_data.open_time or time(9, 0),
                "close_time": gym_hours_data.close_time or time(21, 0),
                "is_closed": gym_hours_data.is_closed if gym_hours_data.is_closed is not None else False
            }
            gym_hours_data = GymHoursCreate(**create_data)
        
        return gym_hours_repository.create(db, obj_in=gym_hours_data)
    
    def initialize_default_hours(self, db: Session) -> List[Any]:
        """Inicializar horarios predeterminados para todos los días de la semana"""
        results = []
        
        for day in range(7):  # 0-6 (Lunes-Domingo)
            hours = gym_hours_repository.get_or_create_default(db, day=day)
            results.append(hours)
        
        return results
    
    def get_hours_for_date(self, db: Session, date_value: date) -> Dict[str, Any]:
        """Obtener los horarios para una fecha específica, considerando días especiales"""
        # Verificar si hay horarios especiales para esta fecha
        special_hours = gym_special_hours_repository.get_by_date(db, date_value=date_value)
        
        if special_hours:
            # Si es un día especial, devolver esos horarios
            return {
                "date": date_value,
                "open_time": special_hours.open_time,
                "close_time": special_hours.close_time,
                "is_closed": special_hours.is_closed,
                "is_special": True,
                "description": special_hours.description
            }
        
        # Si no es un día especial, obtener los horarios regulares
        day_of_week = date_value.weekday()
        regular_hours = gym_hours_repository.get_by_day(db, day=day_of_week)
        
        if not regular_hours:
            # Si no hay horarios configurados para este día, crear predeterminados
            regular_hours = gym_hours_repository.get_or_create_default(db, day=day_of_week)
        
        return {
            "date": date_value,
            "open_time": regular_hours.open_time,
            "close_time": regular_hours.close_time,
            "is_closed": regular_hours.is_closed,
            "is_special": False,
            "description": None
        }


class GymSpecialHoursService:
    def get_special_day(self, db: Session, date_value: date) -> Any:
        """Obtener un día especial por fecha"""
        return gym_special_hours_repository.get_by_date(db, date_value=date_value)
    
    def get_special_days_range(
        self, db: Session, start_date: date, end_date: date
    ) -> List[Any]:
        """Obtener días especiales en un rango de fechas"""
        return gym_special_hours_repository.get_by_date_range(
            db, start_date=start_date, end_date=end_date
        )
    
    def create_special_day(
        self, db: Session, special_hours_data: GymSpecialHoursCreate
    ) -> Any:
        """Crear un nuevo día especial"""
        # Convertir la fecha a datetime.date si es datetime
        if isinstance(special_hours_data.date, datetime):
            date_value = special_hours_data.date.date()
        else:
            date_value = special_hours_data.date
        
        # Verificar si ya existe un día especial para esta fecha
        existing = gym_special_hours_repository.get_by_date(db, date_value=date_value)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un día especial para la fecha {date_value}"
            )
        
        return gym_special_hours_repository.create(db, obj_in=special_hours_data)
    
    def update_special_day(
        self, db: Session, special_day_id: int, special_hours_data: GymSpecialHoursUpdate
    ) -> Any:
        """Actualizar un día especial existente"""
        existing = gym_special_hours_repository.get(db, id=special_day_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Día especial no encontrado"
            )
        
        return gym_special_hours_repository.update(
            db, db_obj=existing, obj_in=special_hours_data
        )
    
    def delete_special_day(self, db: Session, special_day_id: int) -> Any:
        """Eliminar un día especial"""
        existing = gym_special_hours_repository.get(db, id=special_day_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Día especial no encontrado"
            )
        
        return gym_special_hours_repository.remove(db, id=special_day_id)
    
    def get_upcoming_special_days(self, db: Session, limit: int = 10) -> List[Any]:
        """Obtener los próximos días especiales"""
        return gym_special_hours_repository.get_upcoming_special_days(db, limit=limit)


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
        self, db: Session, skip: int = 0, limit: int = 100, active_only: bool = True
    ) -> List[Any]:
        """Obtener todas las clases"""
        if active_only:
            return class_repository.get_active_classes(db, skip=skip, limit=limit)
        return class_repository.get_multi(db, skip=skip, limit=limit)
    
    def create_class(self, db: Session, class_data: ClassCreate, created_by_id: Optional[int] = None) -> Any:
        """Crear una nueva clase"""
        # Agregar ID del creador si se proporciona
        obj_in_data = class_data.model_dump()
        if created_by_id:
            obj_in_data["created_by"] = created_by_id
        
        return class_repository.create(db, obj_in=ClassCreate(**obj_in_data))
    
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
        self, db: Session, category: str, skip: int = 0, limit: int = 100
    ) -> List[Any]:
        """Obtener clases por categoría"""
        return class_repository.get_by_category(
            db, category=category, skip=skip, limit=limit
        )
    
    def get_classes_by_difficulty(
        self, db: Session, difficulty: str, skip: int = 0, limit: int = 100
    ) -> List[Any]:
        """Obtener clases por nivel de dificultad"""
        return class_repository.get_by_difficulty(
            db, difficulty=difficulty, skip=skip, limit=limit
        )
    
    def search_classes(
        self, db: Session, search: str, skip: int = 0, limit: int = 100
    ) -> List[Any]:
        """Buscar clases por nombre o descripción"""
        return class_repository.search_classes(
            db, search=search, skip=skip, limit=limit
        )


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
        self, db: Session, skip: int = 0, limit: int = 100
    ) -> List[Any]:
        """Obtener las próximas sesiones programadas"""
        return class_session_repository.get_upcoming_sessions(
            db, skip=skip, limit=limit
        )
    
    def get_sessions_by_date_range(
        self, db: Session, start_date: date, end_date: date, 
        skip: int = 0, limit: int = 100
    ) -> List[Any]:
        """Obtener sesiones en un rango de fechas"""
        start_datetime = datetime.combine(start_date, time.min)
        end_datetime = datetime.combine(end_date, time.max)
        
        return class_session_repository.get_by_date_range(
            db, start_date=start_datetime, end_date=end_datetime,
            skip=skip, limit=limit
        )
    
    def get_sessions_by_trainer(
        self, db: Session, trainer_id: int, skip: int = 0, limit: int = 100,
        upcoming_only: bool = False
    ) -> List[Any]:
        """Obtener sesiones de un entrenador específico"""
        if upcoming_only:
            return class_session_repository.get_trainer_upcoming_sessions(
                db, trainer_id=trainer_id, skip=skip, limit=limit
            )
        return class_session_repository.get_by_trainer(
            db, trainer_id=trainer_id, skip=skip, limit=limit
        )
    
    def get_sessions_by_class(
        self, db: Session, class_id: int, skip: int = 0, limit: int = 100
    ) -> List[Any]:
        """Obtener sesiones de una clase específica"""
        return class_session_repository.get_by_class(
            db, class_id=class_id, skip=skip, limit=limit
        )


class ClassParticipationService:
    def register_for_class(
        self, db: Session, member_id: int, session_id: int
    ) -> Any:
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
            status=ClassParticipationStatus.REGISTERED
        )
        
        participation = class_participation_repository.create(
            db, obj_in=participation_data
        )
        
        # Actualizar contador de participantes
        class_session_repository.update_participant_count(db, session_id=session_id)
        
        return participation
    
    def cancel_registration(
        self, db: Session, member_id: int, session_id: int, reason: Optional[str] = None
    ) -> Any:
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
        return class_participation_repository.cancel_participation(
            db, session_id=session_id, member_id=member_id, reason=reason
        )
    
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
        self, db: Session, session_id: int, skip: int = 0, limit: int = 100
    ) -> List[Any]:
        """Obtener todos los participantes de una sesión"""
        return class_participation_repository.get_by_session(
            db, session_id=session_id, skip=skip, limit=limit
        )
    
    def get_member_participations(
        self, db: Session, member_id: int, skip: int = 0, limit: int = 100
    ) -> List[Any]:
        """Obtener todas las participaciones de un miembro"""
        return class_participation_repository.get_by_member(
            db, member_id=member_id, skip=skip, limit=limit
        )
    
    def get_member_upcoming_classes(
        self, db: Session, member_id: int, skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Obtener las próximas clases de un miembro"""
        return class_participation_repository.get_member_upcoming_classes(
            db, member_id=member_id, skip=skip, limit=limit
        )


# Instantiate services
gym_hours_service = GymHoursService()
gym_special_hours_service = GymSpecialHoursService()
class_service = ClassService()
class_session_service = ClassSessionService()
class_participation_service = ClassParticipationService() 