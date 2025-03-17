from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.models.event import Event, EventParticipation, EventStatus, EventParticipationStatus
from app.models.user import User, UserRole
from app.schemas.event import EventCreate, EventUpdate, EventParticipationCreate, EventParticipationUpdate


class EventRepository:
    """Repositorio para operaciones con eventos."""
    
    def create_event(self, db: Session, *, event_in: EventCreate, creator_id: Union[int, str]) -> Event:
        """Crear un nuevo evento."""
        event_data = event_in.dict()
        
        # Si creator_id es un string, buscar el usuario por auth0_id
        if isinstance(creator_id, str):
            user = db.query(User).filter(User.auth0_id == creator_id).first()
            if user:
                creator_id = user.id
            else:
                # Si no se encuentra el usuario, crear uno nuevo con el auth0_id
                user = User(auth0_id=creator_id, email=f"temp_{creator_id}@example.com", role=UserRole.MEMBER)
                db.add(user)
                db.commit()
                db.refresh(user)
                creator_id = user.id
        
        db_event = Event(**event_data, creator_id=creator_id)
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        return db_event
    
    def get_events(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[EventStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        title_contains: Optional[str] = None,
        location_contains: Optional[str] = None,
        created_by: Optional[Union[int, str]] = None,
        only_available: bool = False
    ) -> List[Event]:
        """Obtener eventos con filtros opcionales."""
        query = db.query(Event)
        
        # Aplicar filtros si existen
        if status:
            query = query.filter(Event.status == status)
        
        if start_date:
            query = query.filter(Event.end_time >= start_date)
            
        if end_date:
            query = query.filter(Event.start_time <= end_date)
            
        if title_contains:
            query = query.filter(Event.title.ilike(f"%{title_contains}%"))
            
        if location_contains:
            query = query.filter(Event.location.ilike(f"%{location_contains}%"))
            
        if created_by:
            # Si created_by es un string, buscar el usuario por auth0_id
            if isinstance(created_by, str):
                user = db.query(User).filter(User.auth0_id == created_by).first()
                if user:
                    query = query.filter(Event.creator_id == user.id)
                else:
                    # Si no se encuentra el usuario, no se mostrará ningún evento
                    return []
            else:
                query = query.filter(Event.creator_id == created_by)
        
        # Filtrar para eventos con cupo disponible
        if only_available:
            # Subconsulta para contar participantes registrados por evento
            subquery = (
                db.query(
                    EventParticipation.event_id,
                    func.count(EventParticipation.id).label("participant_count")
                )
                .filter(EventParticipation.status == EventParticipationStatus.REGISTERED)
                .group_by(EventParticipation.event_id)
                .subquery()
            )
            
            # Eventos que tienen cupo disponible o sin límite (max_participants = 0)
            query = (
                query
                .outerjoin(subquery, Event.id == subquery.c.event_id)
                .filter(
                    or_(
                        # Sin límite de participantes
                        Event.max_participants == 0,
                        # Con cupo disponible
                        and_(
                            Event.max_participants > 0,
                            or_(
                                # No hay participantes aún
                                subquery.c.participant_count.is_(None),
                                # Hay cupo disponible
                                Event.max_participants > subquery.c.participant_count
                            )
                        )
                    )
                )
            )
        
        # Aplicar paginación
        return query.order_by(Event.start_time).offset(skip).limit(limit).all()
    
    def get_event(self, db: Session, event_id: int) -> Optional[Event]:
        """Obtener un evento por ID."""
        return db.query(Event).filter(Event.id == event_id).first()
    
    def update_event(
        self, db: Session, *, event_id: int, event_in: EventUpdate
    ) -> Optional[Event]:
        """Actualizar un evento."""
        db_event = self.get_event(db, event_id=event_id)
        if not db_event:
            return None
        
        update_data = event_in.dict(exclude_unset=True)
        
        # Actualizar cada campo si está presente
        for field, value in update_data.items():
            setattr(db_event, field, value)
        
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        return db_event
    
    def delete_event(self, db: Session, *, event_id: int) -> bool:
        """Eliminar un evento."""
        db_event = self.get_event(db, event_id=event_id)
        if not db_event:
            return False
        
        db.delete(db_event)
        db.commit()
        return True
    
    def get_events_by_creator(
        self, db: Session, *, creator_id: Union[int, str], skip: int = 0, limit: int = 100
    ) -> List[Event]:
        """Obtener todos los eventos creados por un usuario específico."""
        if isinstance(creator_id, str):
            # Buscar usuario por auth0_id
            user = db.query(User).filter(User.auth0_id == creator_id).first()
            if user:
                creator_id = user.id
            else:
                # Si no se encuentra el usuario, no hay eventos
                return []
            
        return (
            db.query(Event)
            .filter(Event.creator_id == creator_id)
            .order_by(Event.start_time)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def is_event_creator(self, db: Session, *, event_id: int, user_id: Union[int, str]) -> bool:
        """Verificar si un usuario es el creador de un evento."""
        if isinstance(user_id, str):
            # Buscar usuario por auth0_id
            user = db.query(User).filter(User.auth0_id == user_id).first()
            if user:
                user_id = user.id
            else:
                return False
                
        event = self.get_event(db, event_id=event_id)
        if not event:
            return False
        
        return event.creator_id == user_id


class EventParticipationRepository:
    """Repositorio para operaciones con participaciones en eventos."""
    
    def create_participation(
        self, db: Session, *, participation_in: EventParticipationCreate, member_id: Union[int, str]
    ) -> Optional[EventParticipation]:
        """Crear una nueva participación en un evento."""
        # Primero verificar si ya existe una participación para este miembro y evento
        event_id = participation_in.event_id
        
        if isinstance(member_id, str):
            # Buscar usuario por auth0_id
            user = db.query(User).filter(User.auth0_id == member_id).first()
            if user:
                member_id = user.id
            else:
                # Si no se encuentra el usuario, crear uno nuevo con el auth0_id
                user = User(auth0_id=member_id, email=f"temp_{member_id}@example.com", role=UserRole.MEMBER)
                db.add(user)
                db.commit()
                db.refresh(user)
                member_id = user.id
        
        existing = db.query(EventParticipation).filter(
            EventParticipation.event_id == event_id,
            EventParticipation.member_id == member_id
        ).first()
        
        if existing:
            # Si ya existe una participación y está cancelada, la reactivamos
            if existing.status == EventParticipationStatus.CANCELLED:
                # Verificar si hay espacio disponible
                event = db.query(Event).filter(Event.id == event_id).first()
                if not event:
                    return None
                
                # Si no hay límite de participantes, o hay espacio disponible
                registered_count = db.query(func.count(EventParticipation.id)).filter(
                    EventParticipation.event_id == event_id,
                    EventParticipation.status == EventParticipationStatus.REGISTERED
                ).scalar()
                
                if event.max_participants == 0 or registered_count < event.max_participants:
                    existing.status = EventParticipationStatus.REGISTERED
                else:
                    # Si no hay espacio, lo ponemos en lista de espera
                    existing.status = EventParticipationStatus.WAITING_LIST
                
                existing.notes = participation_in.notes
                db.add(existing)
                db.commit()
                db.refresh(existing)
                return existing
            else:
                # Si ya existe y no está cancelada, no permitimos duplicados
                return None
        
        # Verificar si hay espacio disponible
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            return None
        
        # Determinar el estado inicial de la participación
        participation_status = EventParticipationStatus.REGISTERED
        
        # Si hay límite de participantes, verificar si hay espacio
        if event.max_participants > 0:
            registered_count = db.query(func.count(EventParticipation.id)).filter(
                EventParticipation.event_id == event_id,
                EventParticipation.status == EventParticipationStatus.REGISTERED
            ).scalar()
            
            if registered_count >= event.max_participants:
                # Si no hay espacio, lo ponemos en lista de espera
                participation_status = EventParticipationStatus.WAITING_LIST
        
        # Crear la nueva participación
        db_participation = EventParticipation(
            event_id=event_id,
            member_id=member_id,
            status=participation_status,
            notes=participation_in.notes
        )
        
        db.add(db_participation)
        db.commit()
        db.refresh(db_participation)
        return db_participation
    
    def get_participation(
        self, db: Session, *, participation_id: int
    ) -> Optional[EventParticipation]:
        """Obtener una participación por ID."""
        return db.query(EventParticipation).filter(
            EventParticipation.id == participation_id
        ).first()
    
    def get_participation_by_member_and_event(
        self, db: Session, *, member_id: Union[int, str], event_id: int
    ) -> Optional[EventParticipation]:
        """Obtener una participación específica por miembro y evento."""
        if isinstance(member_id, str):
            # Buscar usuario por auth0_id
            user = db.query(User).filter(User.auth0_id == member_id).first()
            if user:
                member_id = user.id
            else:
                return None
                
        return db.query(EventParticipation).filter(
            EventParticipation.event_id == event_id,
            EventParticipation.member_id == member_id
        ).first()
    
    def update_participation(
        self, db: Session, *, participation_id: int, participation_in: EventParticipationUpdate
    ) -> Optional[EventParticipation]:
        """Actualizar una participación."""
        db_participation = self.get_participation(db, participation_id=participation_id)
        if not db_participation:
            return None
        
        update_data = participation_in.dict(exclude_unset=True)
        
        # Actualizar cada campo si está presente
        for field, value in update_data.items():
            setattr(db_participation, field, value)
        
        db.add(db_participation)
        db.commit()
        db.refresh(db_participation)
        return db_participation
    
    def delete_participation(
        self, db: Session, *, participation_id: int
    ) -> bool:
        """Eliminar una participación."""
        db_participation = self.get_participation(db, participation_id=participation_id)
        if not db_participation:
            return False
        
        db.delete(db_participation)
        db.commit()
        return True
    
    def get_event_participants(
        self, db: Session, *, event_id: int, status: Optional[EventParticipationStatus] = None
    ) -> List[EventParticipation]:
        """Obtener todos los participantes de un evento."""
        query = db.query(EventParticipation).filter(EventParticipation.event_id == event_id)
        
        if status:
            query = query.filter(EventParticipation.status == status)
            
        return query.all()
    
    def get_member_events(
        self, db: Session, *, member_id: Union[int, str], status: Optional[EventParticipationStatus] = None
    ) -> List[EventParticipation]:
        """Obtener todos los eventos en que participa un miembro."""
        if isinstance(member_id, str):
            # Buscar usuario por auth0_id
            user = db.query(User).filter(User.auth0_id == member_id).first()
            if user:
                member_id = user.id
            else:
                return []
                
        query = db.query(EventParticipation).filter(EventParticipation.member_id == member_id)
        
        if status:
            query = query.filter(EventParticipation.status == status)
            
        return query.all()
    
    def cancel_participation(
        self, db: Session, *, member_id: Union[int, str], event_id: int
    ) -> Optional[EventParticipation]:
        """Cancelar la participación de un miembro en un evento y promover a alguien de la lista de espera."""
        if isinstance(member_id, str):
            # Buscar usuario por auth0_id
            user = db.query(User).filter(User.auth0_id == member_id).first()
            if user:
                member_id = user.id
            else:
                return None
                
        # Obtener la participación
        participation = self.get_participation_by_member_and_event(
            db=db, member_id=member_id, event_id=event_id
        )
        
        if not participation or participation.status == EventParticipationStatus.CANCELLED:
            return None
        
        # Verificar si estaba registrado (para promover a alguien de la lista de espera)
        was_registered = participation.status == EventParticipationStatus.REGISTERED
        
        # Cancelar la participación
        participation.status = EventParticipationStatus.CANCELLED
        db.add(participation)
        db.commit()
        db.refresh(participation)
        
        # Si estaba registrado, promover a alguien de la lista de espera
        if was_registered:
            self._promote_from_waiting_list(db, event_id)
        
        return participation
    
    def _promote_from_waiting_list(self, db: Session, event_id: int) -> Optional[EventParticipation]:
        """Promover al primer miembro en lista de espera a registrado."""
        # Obtener primer miembro en lista de espera (orden por fecha de registro)
        waiting = (
            db.query(EventParticipation)
            .filter(
                EventParticipation.event_id == event_id,
                EventParticipation.status == EventParticipationStatus.WAITING_LIST
            )
            .order_by(EventParticipation.registered_at)
            .first()
        )
        
        if waiting:
            waiting.status = EventParticipationStatus.REGISTERED
            db.add(waiting)
            db.commit()
            db.refresh(waiting)
            return waiting
        
        return None


event_repository = EventRepository()
event_participation_repository = EventParticipationRepository() 