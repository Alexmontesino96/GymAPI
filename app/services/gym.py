from typing import List, Optional, Dict, Any, Union, cast
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_
import logging

from app.models.gym import Gym
from app.models.user_gym import UserGym, GymRoleType
from app.models.user import User
from app.models.event import Event
from app.models.schedule import ClassSession
from app.models.gym_module import GymModule
from app.models.module import Module

from app.schemas.gym import GymCreate, GymUpdate, GymWithStats
from app.repositories.gym import gym_repository
from fastapi import HTTPException, status

# Importar UserRole para la comparación
from app.models.user import UserRole 
from redis.asyncio import Redis # Importar Redis
from app.services.cache_service import cache_service # Importar cache_service
from app.schemas.user import GymUserSummary # Importar schema de respuesta

logger = logging.getLogger(__name__)

class GymService:
    def create_gym(self, db: Session, *, gym_in: GymCreate) -> Gym:
        """
        Crear un nuevo gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_in: Datos del gimnasio a crear
            
        Returns:
            El gimnasio creado
        """
        return gym_repository.create(db, obj_in=gym_in)
    
    def get_gym(self, db: Session, gym_id: int) -> Optional[Gym]:
        """
        Obtener un gimnasio por su ID.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            
        Returns:
            El gimnasio o None si no existe
        """
        return gym_repository.get(db, id=gym_id)
    
    def get_gym_by_subdomain(self, db: Session, subdomain: str) -> Optional[Gym]:
        """
        Obtener un gimnasio por su subdominio.
        
        Args:
            db: Sesión de base de datos
            subdomain: Subdominio del gimnasio
            
        Returns:
            El gimnasio o None si no existe
        """
        return db.query(Gym).filter(Gym.subdomain == subdomain).first()
    
    def get_gyms(
        self, db: Session, *, skip: int = 0, limit: int = 100, is_active: Optional[bool] = None
    ) -> List[Gym]:
        """
        Obtener lista de gimnasios con filtros opcionales.
        
        Args:
            db: Sesión de base de datos
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver
            is_active: Filtrar por estado activo/inactivo
            
        Returns:
            Lista de gimnasios
        """
        query = db.query(Gym)
        
        if is_active is not None:
            query = query.filter(Gym.is_active == is_active)
            
        return query.offset(skip).limit(limit).all()
    
    def update_gym(
        self, db: Session, *, gym: Gym, gym_in: Union[GymUpdate, Dict[str, Any]]
    ) -> Gym:
        """
        Actualizar un gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym: Objeto gimnasio a actualizar
            gym_in: Datos actualizados
            
        Returns:
            El gimnasio actualizado
        """
        return gym_repository.update(db, db_obj=gym, obj_in=gym_in)
    
    def update_gym_status(self, db: Session, *, gym_id: int, is_active: bool) -> Gym:
        """
        Actualizar el estado de un gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            is_active: Nuevo estado
            
        Returns:
            El gimnasio actualizado
            
        Raises:
            HTTPException: Si el gimnasio no existe
        """
        gym = self.get_gym(db, gym_id=gym_id)
        if not gym:
            raise HTTPException(status_code=404, detail="Gimnasio no encontrado")
            
        return gym_repository.update(db, db_obj=gym, obj_in={"is_active": is_active})
    
    def delete_gym(self, db: Session, *, gym_id: int) -> Gym:
        """
        Eliminar un gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            
        Returns:
            El gimnasio eliminado
            
        Raises:
            HTTPException: Si el gimnasio no existe
        """
        gym = self.get_gym(db, gym_id=gym_id)
        if not gym:
            raise HTTPException(status_code=404, detail="Gimnasio no encontrado")
            
        return gym_repository.remove(db, id=gym_id)
    
    def add_user_to_gym(
        self,
        db: Session,
        *,
        gym_id: int,
        user_id: int,
        role: GymRoleType = GymRoleType.MEMBER
    ) -> UserGym:
        """
        Añade un usuario a un gimnasio con el rol especificado.
        Por defecto, el rol es MEMBER.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            user_id: ID del usuario
            role: Rol del usuario en el gimnasio (default: MEMBER)
            
        Returns:
            UserGym: La relación usuario-gimnasio creada
            
        Raises:
            ValueError: Si el usuario ya pertenece al gimnasio
        """
        # Verificar que el usuario no pertenece ya al gimnasio
        existing = self.check_user_in_gym(db, user_id=user_id, gym_id=gym_id)
        if existing:
            raise ValueError(f"El usuario {user_id} ya pertenece al gimnasio {gym_id}")
        
        # Crear la relación usuario-gimnasio
        user_gym = UserGym(
            user_id=user_id,
            gym_id=gym_id,
            role=role
        )
        db.add(user_gym)
        db.commit()
        db.refresh(user_gym)
        
        # 🆕 HOOK: Agregar usuario al canal general del gimnasio
        try:
            from app.services.gym_chat import gym_chat_service
            
            # Agregar al canal general
            success = gym_chat_service.add_user_to_general_channel(db, gym_id, user_id)
            if success:
                logger.info(f"Usuario {user_id} agregado al canal general de gym {gym_id}")
                
                # Intentar enviar mensaje de bienvenida (opcional)
                try:
                    gym_chat_service.send_welcome_message(db, gym_id, user_id)
                    logger.info(f"Mensaje de bienvenida enviado para usuario {user_id} en gym {gym_id}")
                except Exception as welcome_error:
                    logger.warning(f"No se pudo enviar mensaje de bienvenida para usuario {user_id} en gym {gym_id}: {welcome_error}")
            else:
                logger.warning(f"No se pudo agregar usuario {user_id} al canal general de gym {gym_id}")
                
        except Exception as chat_error:
            logger.error(f"Error agregando usuario {user_id} al canal general de gym {gym_id}: {chat_error}")
            # No fallar la operación principal por un error en el chat
        
        return user_gym
    
    def remove_user_from_gym(self, db: Session, *, gym_id: int, user_id: int) -> None:
        """
        Eliminar un usuario de un gimnasio.
        Impide eliminar usuarios SUPER_ADMIN.
        """
        # Verificar que el usuario a eliminar existe y NO es SUPER_ADMIN
        user_to_remove = db.query(User).filter(User.id == user_id).first()
        if not user_to_remove:
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con ID {user_id} no encontrado."
            )
        if user_to_remove.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, # Usar 403 Forbidden aquí
                detail="No se pueden eliminar administradores de plataforma de los gimnasios."
            )
            
        # Buscar la asociación
        user_gym = db.query(UserGym).filter(
            UserGym.user_id == user_id,
            UserGym.gym_id == gym_id
        ).first()
        
        if not user_gym:
            # Si no existe la asociación, no hay nada que hacer (o lanzar 404)
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El usuario {user_id} no pertenece al gimnasio {gym_id}"
            )
            
        # 🆕 HOOK: Remover usuario del canal general del gimnasio
        try:
            from app.services.gym_chat import gym_chat_service
            gym_chat_service.remove_user_from_general_channel(db, gym_id, user_id)
            logger.info(f"Usuario {user_id} removido del canal general de gym {gym_id}")
        except Exception as chat_error:
            logger.error(f"Error removiendo usuario {user_id} del canal general de gym {gym_id}: {chat_error}")
            # No fallar la operación principal por un error en el chat
        
        # Eliminar la asociación (sin commit aquí)
        db.delete(user_gym)
        # El commit se maneja fuera
    
    def update_user_role(
        self, db: Session, *, gym_id: int, user_id: int, role: GymRoleType
    ) -> UserGym:
        """
        Actualizar el rol de un usuario en un gimnasio.
        Impide modificar el rol de usuarios SUPER_ADMIN.
        """
         # Verificar que el usuario a modificar existe y NO es SUPER_ADMIN
        user_to_update = db.query(User).filter(User.id == user_id).first()
        if not user_to_update:
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con ID {user_id} no encontrado."
            )
        if user_to_update.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No se puede modificar el rol de un administrador de plataforma a nivel de gimnasio."
            )
            
        # Buscar la asociación
        user_gym = db.query(UserGym).filter(
            UserGym.user_id == user_id,
            UserGym.gym_id == gym_id
        ).first()
        
        if not user_gym:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El usuario {user_id} no pertenece al gimnasio {gym_id}"
            )
            
        # Actualizar el rol (sin commit aquí)
        user_gym.role = role
        # El commit y refresh se manejan fuera
        return user_gym
    
    def get_user_gyms(
        self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Obtener todos los gimnasios a los que pertenece un usuario,
        incluyendo el email del usuario y su rol en cada gimnasio.
        
        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver
            
        Returns:
            Lista de diccionarios representando la pertenencia del usuario a cada gimnasio.
            
        Raises:
             HTTPException 404: Si el usuario no existe.
        """
        # Obtener primero el usuario para asegurar que existe y obtener su email
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            # Considerar lanzar una excepción si el usuario no se encuentra
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con ID {user_id} no encontrado."
            )
            # O devolver lista vacía: return [] 
            
        user_email = user.email # Guardar el email del usuario
        
        # Consultar las asociaciones y los gimnasios
        user_gyms = db.query(UserGym, Gym).join(
            Gym, UserGym.gym_id == Gym.id
        ).filter(
            UserGym.user_id == user_id,
            Gym.is_active == True
        ).order_by(Gym.name).offset(skip).limit(limit).all()
        
        result = []
        for user_gym, gym in user_gyms:
            gym_membership_dict = {
                # Campos del Gym
                "id": gym.id,
                "name": gym.name,
                "subdomain": gym.subdomain,
                "logo_url": gym.logo_url,
                "address": gym.address,
                "phone": gym.phone,
                "email": gym.email, # Email del gimnasio
                "description": gym.description,
                "is_active": gym.is_active,
                "created_at": gym.created_at,
                "updated_at": gym.updated_at,
                # Campos añadidos
                "user_email": user_email, # Email del usuario solicitado
                "user_role_in_gym": user_gym.role # Rol del usuario en ESTE gimnasio
            }
            result.append(gym_membership_dict)
            
        return result
    
    def get_gym_users(
        self, 
        db: Session, 
        *, 
        gym_id: int, 
        role: Optional[GymRoleType] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Obtener todos los usuarios de un gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            role: Filtrar por rol específico
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver
            
        Returns:
            Lista de usuarios con su rol en el gimnasio
        """
        query = db.query(UserGym, User).join(
            User, UserGym.user_id == User.id
        ).filter(
            UserGym.gym_id == gym_id
        )
        
        if role:
            query = query.filter(UserGym.role == role)
            
        users = query.offset(skip).limit(limit).all()
        
        result = []
        for user_gym, user in users:
            # Combinar first_name y last_name para crear el nombre completo
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            
            user_dict = {
                "id": user.id,
                "email": user.email,
                "full_name": full_name,
                "role": user_gym.role.value,
                "joined_at": user_gym.created_at
            }
            result.append(user_dict)
            
        return result
    
    def get_gym_with_stats(self, db: Session, *, gym_id: int) -> Optional[GymWithStats]:
        """
        Obtener un gimnasio con estadísticas básicas.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            
        Returns:
            Gimnasio con estadísticas o None si no existe
        """
        gym = self.get_gym(db, gym_id=gym_id)
        if not gym:
            return None
        
        # Contar usuarios por rol
        role_counts = db.query(
            UserGym.role,
            func.count(UserGym.id).label("count")
        ).filter(
            UserGym.gym_id == gym_id
        ).group_by(UserGym.role).all()
        
        # Inicializar contadores
        members_count = 0
        trainers_count = 0
        admins_count = 0
        
        # Asignar contadores según roles
        for role, count in role_counts:
            if role == GymRoleType.MEMBER:
                members_count = count
            elif role == GymRoleType.TRAINER:
                trainers_count = count
            elif role in (GymRoleType.ADMIN, GymRoleType.OWNER):
                admins_count += count
        
        # Contar eventos
        events_count = db.query(func.count(Event.id)).filter(
            Event.gym_id == gym_id
        ).scalar() or 0
        
        # Contar clases
        classes_count = db.query(func.count(ClassSession.id)).filter(
            ClassSession.gym_id == gym_id
        ).scalar() or 0
        
        # Crear objeto con estadísticas
        gym_dict = {
            "id": gym.id,
            "name": gym.name,
            "subdomain": gym.subdomain,
            "logo_url": gym.logo_url,
            "address": gym.address,
            "phone": gym.phone,
            "email": gym.email,
            "description": gym.description,
            "is_active": gym.is_active,
            "created_at": gym.created_at,
            "updated_at": gym.updated_at,
            "members_count": members_count,
            "trainers_count": trainers_count,
            "admins_count": admins_count,
            "events_count": events_count,
            "classes_count": classes_count
        }
        
        return GymWithStats(**gym_dict)
    
    def check_user_in_gym(
        self, db: Session, *, user_id: int, gym_id: int
    ) -> Optional[UserGym]:
        """
        Verificar si un usuario pertenece a un gimnasio.
        
        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio
            
        Returns:
            La asociación usuario-gimnasio o None si no existe
        """
        print(f"DEBUG check_user_in_gym: Verificando user_id={user_id}, gym_id={gym_id}")
        try:
            # Realizar la consulta y capturar el SQL generado
            query = db.query(UserGym).filter(
            UserGym.user_id == user_id,
            UserGym.gym_id == gym_id
            )
            print(f"DEBUG check_user_in_gym: SQL Query = {str(query)}")
            
            # Ejecutar la consulta
            result = query.first()
            print(f"DEBUG check_user_in_gym: Resultado = {result}")
            
            # Si existe, mostrar detalles de la relación
            if result:
                print(f"DEBUG check_user_in_gym: Encontrada relación - user_id={result.user_id}, gym_id={result.gym_id}, role={result.role}")
            else:
                print(f"DEBUG check_user_in_gym: No se encontró relación")
                
                # Verificar si el usuario existe
                user_exists = db.query(User).filter(User.id == user_id).first() is not None
                print(f"DEBUG check_user_in_gym: ¿Usuario existe? {user_exists}")
                
                # Verificar si hay registros para ese usuario en cualquier gimnasio
                all_user_gyms = db.query(UserGym).filter(UserGym.user_id == user_id).all()
                print(f"DEBUG check_user_in_gym: Relaciones del usuario con otros gimnasios: {len(all_user_gyms)}")
                for ug in all_user_gyms:
                    print(f"DEBUG check_user_in_gym:   - gym_id={ug.gym_id}, role={ug.role}")
            
            return result
        except Exception as e:
            print(f"DEBUG check_user_in_gym: Error durante la consulta: {str(e)}")
            return None
    
    def check_user_role_in_gym(
        self, db: Session, *, user_id: int, gym_id: int, required_roles: List[GymRoleType]
    ) -> bool:
        """
        Verificar si un usuario tiene uno de los roles requeridos en un gimnasio.
        
        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio
            required_roles: Lista de roles aceptables
            
        Returns:
            True si el usuario tiene uno de los roles requeridos, False en caso contrario
        """
        user_gym = self.check_user_in_gym(db, user_id=user_id, gym_id=gym_id)
        if not user_gym:
            return False
            
        return user_gym.role in required_roles

    def update_user_role_in_gym(
        self, db: Session, *, gym_id: int, user_id: int, role: GymRoleType
    ) -> UserGym:
        """
        Actualizar el rol de un usuario DENTRO de un gimnasio específico (GymRoleType).
        Impide modificar el rol de usuarios SUPER_ADMIN.
        """
         # Verificar que el usuario a modificar existe y NO es SUPER_ADMIN
        user_to_update = db.query(User).filter(User.id == user_id).first()
        if not user_to_update:
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con ID {user_id} no encontrado."
            )
        if user_to_update.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No se puede modificar el rol de un administrador de plataforma a nivel de gimnasio."
            )
            
        # Buscar la asociación
        user_gym = db.query(UserGym).filter(
            UserGym.user_id == user_id,
            UserGym.gym_id == gym_id
        ).first()
        
        if not user_gym:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El usuario {user_id} no pertenece al gimnasio {gym_id}"
            )
            
        # Actualizar el rol (sin commit aquí)
        user_gym.role = role
        db.add(user_gym) # Asegurar que se marca para guardar
        # El commit y refresh se manejan fuera
        return user_gym

    # <<< NUEVO MÉTODO CACHEADO PARA USUARIOS DEL GIMNASIO >>>
    async def get_gym_users_cached(
        self, 
        db: Session, 
        *,
        gym_id: int, 
        role: Optional[GymRoleType] = None,
        skip: int = 0, 
        limit: int = 100,
        redis_client: Redis
    ) -> List[Dict[str, Any]]: # Mantener el tipo de retorno original por ahora
        """
        Versión cacheada para obtener todos los usuarios de un gimnasio.
        """
        if not redis_client:
            # Llamar a la versión no cacheada si Redis no está disponible
            return self.get_gym_users(db=db, gym_id=gym_id, role=role, skip=skip, limit=limit)
            
        # Crear clave de caché
        cache_key = f"gym:{gym_id}:users:role:{role.value if role else 'all'}:skip:{skip}:limit:{limit}"
        
        # Función para obtener datos de la BD
        async def db_fetch():
            # La función get_gym_users es síncrona
            return self.get_gym_users(db=db, gym_id=gym_id, role=role, skip=skip, limit=limit)
            
        try:
            # Usar cache_service.get_or_set
            # IMPORTANTE: get_gym_users devuelve List[Dict], no un modelo Pydantic directamente.
            # Necesitamos adaptar get_or_set o la deserialización.
            # Por simplicidad aquí, asumiremos que el cache_service puede manejar List[Dict]
            # o ajustaremos la serialización/deserialización si es necesario.
            # Opcionalmente, podríamos definir un modelo Pydantic para esta salida (GymUserSummary ya existe).
            users = await cache_service.get_or_set(
                redis_client=redis_client,
                cache_key=cache_key,
                db_fetch_func=db_fetch,
                model_class=GymUserSummary, # Usar el schema correcto para la validación/deserialización
                expiry_seconds=300, # 5 minutos
                is_list=True
            )
            return users
        except Exception as e:
            logger.error(f"Error al obtener usuarios cacheados para gym {gym_id}: {str(e)}", exc_info=True)
            # Fallback a la versión no cacheada
            return self.get_gym_users(db=db, gym_id=gym_id, role=role, skip=skip, limit=limit)
    
    def get_gym_details_public(self, db: Session, *, gym_id: int):
        """
        Obtener detalles completos de un gimnasio para discovery público.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            
        Returns:
            GymDetailedPublicSchema: Detalles completos del gimnasio o None si no existe/inactivo
        """
        from app.schemas.gym import GymDetailedPublicSchema, GymHoursPublic, MembershipPlanPublic, GymModulePublic
        
        # Obtener gimnasio con todas las relaciones necesarias
        gym = db.query(Gym).options(
            joinedload(Gym.gym_hours),
            joinedload(Gym.membership_planes),
            joinedload(Gym.modules).joinedload(GymModule.module)  # Usar referencia de clase directamente
        ).filter(
            Gym.id == gym_id,
            Gym.is_active == True  # Solo gimnasios activos para público
        ).first()
        
        if not gym:
            return None
        
        # Convertir horarios
        gym_hours = []
        if gym.gym_hours:
            for hour in gym.gym_hours:
                gym_hours.append(GymHoursPublic(
                    day_of_week=hour.day_of_week,
                    open_time=hour.open_time,
                    close_time=hour.close_time,
                    is_closed=hour.is_closed
                ))
        
        # Convertir planes de membresía (solo activos)
        membership_plans = []
        if gym.membership_planes:
            for plan in gym.membership_planes:
                if plan.is_active:  # Solo planes activos para público
                    membership_plans.append(MembershipPlanPublic(
                        id=plan.id,
                        name=plan.name,
                        description=plan.description,
                        price_cents=plan.price_cents,
                        currency=plan.currency,
                        billing_interval=plan.billing_interval,
                        duration_days=plan.duration_days,
                        max_billing_cycles=plan.max_billing_cycles,
                        features=plan.features,
                        max_bookings_per_month=plan.max_bookings_per_month,
                        price_amount=plan.price_cents / 100.0  # Convertir centavos a euros
                    ))
        
        # Convertir módulos (solo activos)
        modules = []
        if gym.modules:
            for gym_module in gym.modules:
                if gym_module.active:  # Solo módulos activos para público
                    modules.append(GymModulePublic(
                        module_name=gym_module.module.name,  # Acceder al nombre del módulo relacionado
                        is_enabled=gym_module.active
                    ))
        
        # Crear el schema detallado
        return GymDetailedPublicSchema(
            id=gym.id,
            name=gym.name,
            subdomain=gym.subdomain,
            logo_url=gym.logo_url,
            address=gym.address,
            phone=gym.phone,
            email=gym.email,
            description=gym.description,
            timezone=gym.timezone,
            is_active=gym.is_active,
            gym_hours=gym_hours,
            membership_plans=membership_plans,
            modules=modules
        )

gym_service = GymService() 