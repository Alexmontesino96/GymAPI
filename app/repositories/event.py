from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, and_, or_, select, update

from app.models.event import Event, EventParticipation, EventStatus, EventParticipationStatus
from app.models.user import User, UserRole
from app.schemas.event import EventCreate, EventUpdate, EventParticipationCreate, EventParticipationUpdate
from fastapi.encoders import jsonable_encoder


class EventRepository:
    """Repositorio para operaciones con eventos."""
    
    def create_event(self, db: Session, *, event_in: EventCreate, creator_id: int, gym_id: int = 1) -> Event:
        """Crear un nuevo evento. Espera un ID de creador interno (int)."""
        event_data = event_in.dict()
        
        # Eliminar el campo first_message_chat si existe, ya que no es parte del modelo Event
        # Este campo solo se usa para enviar un mensaje inicial al crear la sala de chat
        if 'first_message_chat' in event_data:
            event_data.pop('first_message_chat')
        
        # Ya no se maneja creator_id como string (Auth0 ID) aquí.
        # Se asume que el creator_id recibido es el ID interno del usuario.
        
        # Verificar si el usuario creador existe (opcional pero recomendable)
        # creator = db.query(User.id).filter(User.id == creator_id).first()
        # if not creator:
        #     raise ValueError(f"Creator user with internal ID {creator_id} not found")

        # Crear el evento directamente con el ID interno
        db_event = Event(**event_data, creator_id=creator_id, gym_id=gym_id)
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
        only_available: bool = False,
        gym_id: Optional[int] = None
    ) -> List[Event]:
        """Obtener eventos con filtros opcionales."""
        # Optimización: Construir la consulta de manera incremental basada en los criterios
        # y aprovechar los índices compuestos creados
        
        # Seleccionar las columnas específicas necesarias en lugar de cargar todos los datos
        query = db.query(Event)
        
        # Optimización: Usar selectinload para relaciones con múltiples hijos (participants)
        # Es más eficiente que joinedload para colecciones de muchos elementos
        query = query.options(selectinload(Event.participants))
        
        # Construir filtros de manera eficiente usando los índices compuestos cuando sea posible
        filters = []
        
        # Filtrar por gimnasio - usa índice ix_events_gym_id
        if gym_id is not None:
            filters.append(Event.gym_id == gym_id)
        
        # Filtrar por estado - aprovechar índice compuesto ix_events_gym_status si también hay gym_id
        if status:
            filters.append(Event.status == status)
        
        # Filtrar por fechas - aprovechar índice ix_events_date_range
        if start_date:
            filters.append(Event.end_time >= start_date)
            
        if end_date:
            filters.append(Event.start_time <= end_date)
            
        # Filtros de texto - estos suelen ser más costosos
        if title_contains:
            # Optimización: Usar búsqueda por índice GIN si está disponible
            filters.append(Event.title.ilike(f"%{title_contains}%"))
            
        if location_contains:
            filters.append(Event.location.ilike(f"%{location_contains}%"))
        
        # Filtrar por creador - aprovechar índice ix_events_creator_gym si también hay gym_id
        if created_by:
            # Optimización: si created_by es un string (auth0_id), usamos una subconsulta
            # en lugar de cargar todo el usuario
            if isinstance(created_by, str):
                # Nueva optimización: Usar EXISTS en lugar de subconsulta scalar
                from sqlalchemy import exists
                user_subquery = exists().where(
                    and_(
                        User.auth0_id == created_by,
                        User.id == Event.creator_id
                    )
                )
                filters.append(user_subquery)
            else:
                filters.append(Event.creator_id == created_by)
        
        # Aplicar todos los filtros normales
        if filters:
            query = query.filter(and_(*filters))
        
        # Optimización: manejar filtrado por disponibilidad de manera más eficiente
        if only_available:
            # Optimización: Usar EXISTS con correlate para mayor rendimiento
            from sqlalchemy import exists
            # Subquery correlacionada para contar participantes registrados
            registered_count_subq = (
                exists()
                .where(
                    and_(
                        EventParticipation.event_id == Event.id,
                        EventParticipation.status == EventParticipationStatus.REGISTERED
                    )
                )
                .correlate(Event)
                .scalar_subquery()
            )
            
            query = query.filter(
                or_(
                    # Sin límite de participantes
                    Event.max_participants == 0,
                    # Con cupo disponible (subconsulta correlacionada)
                    Event.max_participants > func.count(registered_count_subq)
                )
            )
        
        # Optimización: Añadir índice hint para el ordenamiento si está disponible
        query = query.order_by(Event.start_time)
        
        # Optimización: Use LIMIT/OFFSET solo cuando sea necesario
        if limit > 0:
            query = query.limit(limit)
            
        if skip > 0:
            query = query.offset(skip)
            
        # Ejecutar la consulta
        return query.all()
    
    def get_event(self, db: Session, event_id: int) -> Optional[Event]:
        """Obtener un evento por ID."""
        # Optimización: Usar selectinload para participantes, más eficiente para colecciones
        return db.query(Event).options(
            selectinload(Event.participants),
            joinedload(Event.creator),
            selectinload(Event.chat_rooms)
        ).filter(Event.id == event_id).first()
    
    def update_event(
        self, db: Session, *, event_id: int, event_in: EventUpdate
    ) -> Optional[Event]:
        """Actualizar un evento de manera optimizada."""
        # Carga del evento sin precargar participantes para mejorar rendimiento
        db_event = db.query(Event).filter(Event.id == event_id).first()
        if not db_event:
            return None
        
        # Optimización 1: Usar actualización directa para datos simples
        update_data = jsonable_encoder(event_in, exclude_unset=True)
        
        # Optimización 2: Actualizar solo si hay cambios
        if not update_data:
            return db_event
            
        # Optimización 3: Actualizar en memoria primero para evitar cambios innecesarios
        modified = False
        for field, value in update_data.items():
            if getattr(db_event, field) != value:
                setattr(db_event, field, value)
                modified = True
        
        # Solo persistir si hubo cambios reales
        if modified:
            # Optimización 4: Establecer updated_at manualmente para evitar triggers
            db_event.updated_at = datetime.now(timezone.utc)
            db.add(db_event)
            db.commit()
        
        # Cargar los participantes solo si son necesarios para la respuesta
        if hasattr(db_event, 'participants') and db_event.participants is None:
            db.refresh(db_event)
        else:
            # Optimización 5: Carga selectiva de relaciones si es necesario
            db_event.participants = db.query(EventParticipation).filter(
                EventParticipation.event_id == event_id
            ).all()
            
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
        self, db: Session, *, creator_id: Union[int, str], skip: int = 0, limit: int = 100, gym_id: Optional[int] = None
    ) -> List[Event]:
        """Obtener todos los eventos creados por un usuario específico."""
        if isinstance(creator_id, str):
            # Buscar usuario por auth0_id - Optimización: usar índice
            user = db.query(User).filter(User.auth0_id == creator_id).first()
            if user:
                creator_id = user.id
            else:
                # Si no se encuentra el usuario, no hay eventos
                return []
            
        # Usar selectinload para relaciones de colecciones - más eficiente que joinedload
        query = db.query(Event).options(selectinload(Event.participants)).filter(Event.creator_id == creator_id)
        
        # Filtrar por gimnasio si se proporciona - Optimización: usar índice compuesto
        if gym_id is not None:
            query = query.filter(Event.gym_id == gym_id)
            
        return query.order_by(Event.start_time).offset(skip).limit(limit).all()
    
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

    def get_events_with_counts(
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
        only_available: bool = False,
        gym_id: Optional[int] = None
    ) -> List[dict]:
        """
        Obtener eventos con filtros opcionales y el conteo de participantes calculado directamente en SQL.
        Esta versión es más eficiente que get_events al calcular los conteos en SQL en vez de Python.
        """
        from sqlalchemy import select, func, literal_column

        # Subconsulta para contar participantes registrados por evento - sintaxis corregida
        participants_count = (
            select(
                EventParticipation.event_id.label('event_id'),
                func.count(EventParticipation.id).label('count')
            )
            .where(EventParticipation.status == EventParticipationStatus.REGISTERED)
            .group_by(EventParticipation.event_id)
            .alias('participants_count')
        )
        
        # Construir los filtros de manera eficiente
        filters = []
        
        # Filtrar por gimnasio - usar índice ix_events_gym_id
        if gym_id is not None:
            filters.append(Event.gym_id == gym_id)
        
        # Filtrar por estado - aprovechar índice compuesto ix_events_gym_status
        if status:
            filters.append(Event.status == status)
        
        # Filtros de fechas - aprovechar índice ix_events_date_range
        if start_date:
            filters.append(Event.end_time >= start_date)
            
        if end_date:
            filters.append(Event.start_time <= end_date)
            
        # Filtros de texto
        if title_contains:
            filters.append(Event.title.ilike(f"%{title_contains}%"))
            
        if location_contains:
            filters.append(Event.location.ilike(f"%{location_contains}%"))
        
        # Filtrar por creador
        if created_by:
            if isinstance(created_by, str):
                # Usar una subconsulta para auth0_id
                user_id = db.query(User.id).filter(User.auth0_id == created_by).scalar()
                if user_id:
                    filters.append(Event.creator_id == user_id)
                else:
                    return []
            else:
                filters.append(Event.creator_id == created_by)
                
        # Consulta principal para eventos con JOIN para conteo de participantes
        query = (
            db.query(
                Event,
                func.coalesce(participants_count.c.count, 0).label('participants_count')
            )
            .outerjoin(participants_count, Event.id == participants_count.c.event_id)
        )
        
        # Aplicar filtros
        if filters:
            query = query.filter(and_(*filters))
            
        # Filtrar por disponibilidad
        if only_available:
            query = query.filter(
                or_(
                    # Sin límite de participantes
                    Event.max_participants == 0,
                    # Con cupo disponible
                    Event.max_participants > func.coalesce(participants_count.c.count, 0)
                )
            )
        
        # Ordenar y paginar
        query = query.order_by(Event.start_time)
        
        if limit > 0:
            query = query.limit(limit)
            
        if skip > 0:
            query = query.offset(skip)
            
        # Ejecutar la consulta y formatear resultados
        results = []
        for event, count in query.all():
            # Convertir a diccionario eficientemente
            event_dict = {c.name: getattr(event, c.name) for c in event.__table__.columns}
            # Añadir conteo de participantes
            event_dict['participants_count'] = count
            results.append(event_dict)
            
        return results

    def update_event_efficient(
        self, db: Session, *, event_id: int, event_in: EventUpdate
    ) -> Optional[Event]:
        """
        Actualizar un evento usando UPDATE directo para máxima eficiencia.
        Esta versión evita cargar el objeto completo si solo se necesita actualizar algunos campos.
        """
        # Verificar si el evento existe sin cargar el objeto completo
        exists = db.query(db.query(Event.id).filter(Event.id == event_id).exists()).scalar()
        if not exists:
            return None
            
        # Extraer sólo los campos con valores para actualizar
        update_data = jsonable_encoder(event_in, exclude_unset=True)
        if not update_data:
            # Si no hay datos para actualizar, obtener solo datos básicos del evento sin participantes
            return db.query(Event).filter(Event.id == event_id).first()
            
        # Añadir timestamp de actualización
        update_data['updated_at'] = datetime.now(timezone.utc)
        
        try: 
            # En lugar de hacer un UPDATE con RETURNING, que puede tener problemas de mapeo, 
            # actualizamos el objeto y lo devolvemos de manera más segura
            
            # 1. Primero obtenemos el evento existente
            db_event = db.query(Event).filter(Event.id == event_id).first()
            if not db_event:
                return None
                
            # 2. Aplicamos los cambios al objeto s
            for field, value in update_data.items():
                setattr(db_event, field, value)
                
            # 3. Guardamos los cambios
            db.add(db_event)
            db.commit()
            
            # 4. Devolvemos el objeto actualizado (sin participantes para mayor eficiencia)
            # No hacemos refresh para evitar cargar relaciones innecesarias
            return db_event
            
        except Exception as e:
            # Registrar error, hacer rollback y devolver None en caso de fallo
            db.rollback()
            print(f"Error al actualizar evento: {e}")
            return None
            
    def mark_event_completed(self, db: Session, *, event_id: int) -> Optional[Event]:
        """
        Marca un evento como COMPLETED de manera eficiente.
        
        Args:
            db: Sesión de base de datos
            event_id: ID del evento a marcar como completado
            
        Returns:
            El evento actualizado o None si no existe o hay un error
        """
        try:
            # Verificar si el evento existe y está aún programado
            event = db.query(Event).filter(
                Event.id == event_id,
                Event.status == EventStatus.SCHEDULED
            ).first()
            
            if not event:
                return None
                
            # Actualizar el estado a COMPLETED
            event.status = EventStatus.COMPLETED
            event.updated_at = datetime.now(timezone.utc)
            
            # Guardar los cambios
            db.add(event)
            db.commit()
            
            return event
        except Exception as e:
            # Registrar error, hacer rollback y devolver None en caso de fallo
            db.rollback()
            print(f"Error al marcar evento como completado: {e}")
            return None

    def _promote_from_waiting_list(self, db: Session, event_id: int) -> Optional[EventParticipation]:
        """Promover al primer miembro en lista de espera a registrado."""
        from app.models.event import Event, PaymentStatusType
        from datetime import datetime, timedelta

        # Obtener el evento para verificar si es de pago
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            return None

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

            # Si el evento es de pago, establecer fecha límite para pagar
            if event.is_paid and event.price_cents:
                waiting.payment_status = PaymentStatusType.PENDING
                # Dar 24 horas para completar el pago
                waiting.payment_expiry = datetime.utcnow() + timedelta(hours=24)

                # TODO: Aquí se debería enviar una notificación al usuario
                # informándole que tiene un lugar disponible y debe pagar
                import logging
                logger = logging.getLogger(__name__)
                logger.info(
                    f"Usuario {waiting.member_id} promovido de lista de espera "
                    f"para evento de pago {event_id}. Fecha límite de pago: {waiting.payment_expiry}"
                )

            db.add(waiting)
            db.commit()
            db.refresh(waiting)
            return waiting

        return None


class EventParticipationRepository:
    """Repositorio para operaciones con participaciones en eventos."""
    
    def create_participation(
        self, db: Session, *, participation_in: EventParticipationCreate, member_id: Union[int, str]
    ) -> Optional[EventParticipation]:
        """Crear una nueva participación en un evento de manera optimizada."""
        try:
            event_id = participation_in.event_id
            
            # Optimización 1: Consulta única para obtener evento y contar participantes
            # Usar una subconsulta más eficiente para contar participantes
            from sqlalchemy import select, func, and_
            
            # Subconsulta para contar participantes registrados
            registered_count_subq = (
                select(func.count(EventParticipation.id))
                .where(
                    and_(
                        EventParticipation.event_id == event_id,
                        EventParticipation.status == EventParticipationStatus.REGISTERED
                    )
                )
                .scalar_subquery()
            )
            
            # Consulta optimizada que obtiene evento y cuenta participantes en una sola operación
            query_result = db.query(
                Event,
                registered_count_subq.label('registered_count')
            ).filter(Event.id == event_id).first()
            
            if not query_result:
                return None
                
            event, registered_count = query_result
            gym_id = event.gym_id
            
            # Optimización 2: Evitar múltiples consultas para el mismo usuario
            user_id = None
            if isinstance(member_id, str):
                # Intentar convertir auth0_id a user_id en una sola consulta
                user_id = db.query(User.id).filter(User.auth0_id == member_id).scalar()
                
                if not user_id:
                    # Si no existe, crear usuario (solo si es necesario)
                    user = User(
                        auth0_id=member_id, 
                        email=f"temp_{member_id}@example.com", 
                        role=UserRole.MEMBER
                    )
                    db.add(user)
                    db.flush()  # Flush en lugar de commit para mantener la transacción
                    user_id = user.id
            else:
                user_id = member_id
            
            # Optimización 3: Verificar participación existente con consulta directa
            # Obtener participación existente si existe, para verificar su estado
            existing = db.query(EventParticipation).filter(
                EventParticipation.event_id == event_id,
                EventParticipation.member_id == user_id
            ).first()
            
            if existing:
                # Si ya existe pero está cancelada, reactivarla
                if existing.status == EventParticipationStatus.CANCELLED:
                    # Determinar estado basado en si es evento de pago o capacidad disponible
                    if event.is_paid and event.price_cents:
                        # Eventos de pago siempre empiezan en PENDING_PAYMENT
                        existing.status = EventParticipationStatus.PENDING_PAYMENT
                    elif event.max_participants == 0 or registered_count < event.max_participants:
                        # Eventos gratuitos con capacidad disponible
                        existing.status = EventParticipationStatus.REGISTERED
                    else:
                        # Eventos gratuitos sin capacidad
                        existing.status = EventParticipationStatus.WAITING_LIST

                    db.add(existing)
                    db.commit()
                    return existing
                else:
                    # Ya registrado (no cancelado), retornar la participación existente
                    return existing
            
            # Determinar el estado inicial
            # Para eventos de pago: PENDING_PAYMENT (no ocupa plaza hasta pagar)
            # Para eventos gratuitos: REGISTERED o WAITING_LIST según capacidad
            if event.is_paid and event.price_cents:
                # Eventos de pago siempre empiezan en PENDING_PAYMENT
                participation_status = EventParticipationStatus.PENDING_PAYMENT
            else:
                # Eventos gratuitos: verificar capacidad
                participation_status = EventParticipationStatus.REGISTERED
                if event.max_participants > 0 and registered_count >= event.max_participants:
                    participation_status = EventParticipationStatus.WAITING_LIST

            # Crear la participación con todos los datos necesarios
            now = datetime.now(timezone.utc)  # Usar la misma marca de tiempo para ambos campos
            db_participation = EventParticipation(
                event_id=event_id,
                member_id=user_id,
                gym_id=gym_id,
                status=participation_status,
                registered_at=now,
                updated_at=now,
                attended=False
            )
            
            # Usar una sola transacción para todas las operaciones
            db.add(db_participation)
            db.commit()
            
            # Evitar refresh completo y solo devolver el objeto creado
            return db_participation
            
        except Exception as e:
            # Manejar excepciones específicas
            db.rollback()
            print(f"Error al crear participación: {e}")
            # En vez de devolver None, que puede ser interpretado como "ya registrado",
            # propagamos la excepción para que sea manejada apropiadamente
            raise
    
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
        self, db: Session, *, db_obj: EventParticipation, participation_in: EventParticipationUpdate
    ) -> Optional[EventParticipation]:
        """Actualizar una participación (principalmente asistencia)."""
        # db_participation = self.get_participation(db, participation_id=participation_id)
        # if not db_participation:
        #     return None
        # Se recibe db_obj directamente para evitar búsqueda repetida.
        db_participation = db_obj 
        
        update_data = jsonable_encoder(participation_in, exclude_unset=True)
        
        # Actualizar cada campo si está presente (ahora solo será 'attended')
        updated = False
        for field, value in update_data.items():
            if hasattr(db_participation, field) and getattr(db_participation, field) != value:
                setattr(db_participation, field, value)
                updated = True
        
        # Solo hacer commit si hubo cambios
        if updated:
            db_participation.updated_at = datetime.now(timezone.utc) # Actualizar timestamp
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
        from app.models.event import Event, PaymentStatusType
        from datetime import datetime, timedelta

        # Obtener el evento para verificar si es de pago
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            return None

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

            # Si el evento es de pago, establecer fecha límite para pagar
            if event.is_paid and event.price_cents:
                waiting.payment_status = PaymentStatusType.PENDING
                # Dar 24 horas para completar el pago
                waiting.payment_expiry = datetime.utcnow() + timedelta(hours=24)

                # TODO: Aquí se debería enviar una notificación al usuario
                # informándole que tiene un lugar disponible y debe pagar
                import logging
                logger = logging.getLogger(__name__)
                logger.info(
                    f"Usuario {waiting.member_id} promovido de lista de espera "
                    f"para evento de pago {event_id}. Fecha límite de pago: {waiting.payment_expiry}"
                )

            db.add(waiting)
            db.commit()
            db.refresh(waiting)
            return waiting

        return None

    def fill_vacancies_from_waiting_list(self, db: Session, event_id: int) -> List[EventParticipation]:
        """Promueve usuarios de la WAITING_LIST hasta cubrir las plazas libres."""
        promoted: List[EventParticipation] = []

        from app.models.event import Event  # evitar ciclos

        event = db.query(Event).filter(Event.id == event_id).first()
        if not event or event.max_participants == 0:
            return promoted

        registered_count = (
            db.query(EventParticipation)
            .filter(
                EventParticipation.event_id == event_id,
                EventParticipation.status == EventParticipationStatus.REGISTERED,
            )
            .count()
        )

        available = max(event.max_participants - registered_count, 0)
        if available == 0:
            return promoted

        waiting_list = (
            db.query(EventParticipation)
            .filter(
                EventParticipation.event_id == event_id,
                EventParticipation.status == EventParticipationStatus.WAITING_LIST,
            )
            .order_by(EventParticipation.registered_at)
            .limit(available)
            .all()
        )

        for part in waiting_list:
            part.status = EventParticipationStatus.REGISTERED
            promoted.append(part)

        if promoted:
            db.bulk_save_objects(promoted)
            db.commit()

        return promoted


event_repository = EventRepository()
event_participation_repository = EventParticipationRepository() 