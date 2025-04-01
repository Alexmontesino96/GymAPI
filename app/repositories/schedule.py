from typing import List, Optional, Dict, Any, Union, Type
from datetime import datetime, time, timedelta, date
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.repositories.base import BaseRepository
from app.models.schedule import (
    GymHours, 
    GymSpecialHours, 
    Class, 
    ClassSession, 
    ClassParticipation,
    ClassSessionStatus,
    ClassParticipationStatus
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


class GymHoursRepository(BaseRepository[GymHours, GymHoursCreate, GymHoursUpdate]):
    def get_by_day(self, db: Session, *, day: int) -> Optional[GymHours]:
        """Obtener los horarios para un día específico de la semana"""
        return db.query(GymHours).filter(GymHours.day_of_week == day).first()
    
    def get_all_days(self, db: Session) -> List[GymHours]:
        """Obtener los horarios para todos los días de la semana"""
        return db.query(GymHours).order_by(GymHours.day_of_week).all()
    
    def get_or_create_default(self, db: Session, *, day: int) -> GymHours:
        """Obtener horarios para un día o crear con valores predeterminados"""
        hours = self.get_by_day(db, day=day)
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
            is_closed=is_closed
        )
        return self.create(db, obj_in=obj_in)


class GymSpecialHoursRepository(BaseRepository[GymSpecialHours, GymSpecialHoursCreate, GymSpecialHoursUpdate]):
    def get_by_date(self, db: Session, *, date_value: date) -> Optional[GymSpecialHours]:
        """Obtener horarios especiales para una fecha específica"""
        # Convertir date a datetime para comparar con la columna date
        start_date = datetime.combine(date_value, time.min)
        end_date = datetime.combine(date_value, time.max)
        
        return db.query(GymSpecialHours).filter(
            GymSpecialHours.date.between(start_date, end_date)
        ).first()
    
    def get_by_date_range(
        self, db: Session, *, start_date: date, end_date: date
    ) -> List[GymSpecialHours]:
        """Obtener horarios especiales para un rango de fechas"""
        start_datetime = datetime.combine(start_date, time.min)
        end_datetime = datetime.combine(end_date, time.max)
        
        return db.query(GymSpecialHours).filter(
            GymSpecialHours.date.between(start_datetime, end_datetime)
        ).order_by(GymSpecialHours.date).all()
    
    def get_upcoming_special_days(
        self, db: Session, *, limit: int = 10
    ) -> List[GymSpecialHours]:
        """Obtener los próximos días especiales"""
        today = datetime.now()
        
        return db.query(GymSpecialHours).filter(
            GymSpecialHours.date >= today
        ).order_by(GymSpecialHours.date).limit(limit).all()


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
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ClassSession]:
        """Obtener las próximas sesiones de clase"""
        now = datetime.now()
        
        return db.query(ClassSession).filter(
            ClassSession.start_time >= now,
            ClassSession.status == ClassSessionStatus.SCHEDULED
        ).order_by(ClassSession.start_time).offset(skip).limit(limit).all()
    
    def get_by_date_range(
        self, db: Session, *, start_date: datetime, end_date: datetime, 
        skip: int = 0, limit: int = 100
    ) -> List[ClassSession]:
        """Obtener sesiones en un rango de fechas"""
        return db.query(ClassSession).filter(
            ClassSession.start_time >= start_date,
            ClassSession.start_time <= end_date
        ).order_by(ClassSession.start_time).offset(skip).limit(limit).all()
    
    def get_by_trainer(
        self, db: Session, *, trainer_id: int, skip: int = 0, limit: int = 100
    ) -> List[ClassSession]:
        """Obtener sesiones de un entrenador específico"""
        return db.query(ClassSession).filter(
            ClassSession.trainer_id == trainer_id
        ).order_by(ClassSession.start_time).offset(skip).limit(limit).all()
    
    def get_trainer_upcoming_sessions(
        self, db: Session, *, trainer_id: int, skip: int = 0, limit: int = 100
    ) -> List[ClassSession]:
        """Obtener las próximas sesiones de un entrenador específico"""
        now = datetime.now()
        
        return db.query(ClassSession).filter(
            ClassSession.trainer_id == trainer_id,
            ClassSession.start_time >= now,
            ClassSession.status == ClassSessionStatus.SCHEDULED
        ).order_by(ClassSession.start_time).offset(skip).limit(limit).all()
    
    def get_by_class(
        self, db: Session, *, class_id: int, skip: int = 0, limit: int = 100
    ) -> List[ClassSession]:
        """Obtener sesiones de una clase específica"""
        return db.query(ClassSession).filter(
            ClassSession.class_id == class_id
        ).order_by(ClassSession.start_time).offset(skip).limit(limit).all()
    
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
        
        available_spots = class_obj.max_capacity - registered_count
        
        return {
            "session": session,
            "class": class_obj,
            "registered_count": registered_count,
            "available_spots": available_spots,
            "is_full": available_spots <= 0
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
        self, db: Session, *, session_id: int, member_id: int
    ) -> Optional[ClassParticipation]:
        """Obtener la participación de un miembro en una sesión específica"""
        return db.query(ClassParticipation).filter(
            ClassParticipation.session_id == session_id,
            ClassParticipation.member_id == member_id
        ).first()
    
    def get_by_session(
        self, db: Session, *, session_id: int, skip: int = 0, limit: int = 100
    ) -> List[ClassParticipation]:
        """Obtener todas las participaciones para una sesión específica"""
        return db.query(ClassParticipation).filter(
            ClassParticipation.session_id == session_id
        ).offset(skip).limit(limit).all()
    
    def get_by_member(
        self, db: Session, *, member_id: int, skip: int = 0, limit: int = 100
    ) -> List[ClassParticipation]:
        """Obtener todas las participaciones de un miembro específico"""
        return db.query(ClassParticipation).filter(
            ClassParticipation.member_id == member_id
        ).offset(skip).limit(limit).all()
    
    def get_member_upcoming_classes(
        self, db: Session, *, member_id: int, skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Obtener las próximas clases de un miembro"""
        now = datetime.now()
        
        # Obtener participaciones del miembro en sesiones futuras
        participations = db.query(
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
        ).order_by(
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
        self, db: Session, *, session_id: int, member_id: int
    ) -> Optional[ClassParticipation]:
        """Marcar la asistencia de un miembro a una sesión"""
        participation = self.get_by_session_and_member(
            db, session_id=session_id, member_id=member_id
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
        self, db: Session, *, session_id: int, member_id: int, reason: Optional[str] = None
    ) -> Optional[ClassParticipation]:
        """Cancelar la participación de un miembro en una sesión"""
        participation = self.get_by_session_and_member(
            db, session_id=session_id, member_id=member_id
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
class_repository = ClassRepository(Class)
class_session_repository = ClassSessionRepository(ClassSession)
class_participation_repository = ClassParticipationRepository(ClassParticipation) 