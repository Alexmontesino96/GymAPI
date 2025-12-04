"""
AsyncGymService - Servicio async para gestión de gimnasios.

Este módulo proporciona un servicio totalmente async que encapsula la lógica de negocio
relacionada con gimnasios, usuarios y estadísticas utilizando repositorios async.

Migrado en FASE 3 de la conversión sync → async.
"""

from typing import List, Optional, Dict, Any, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, and_, select
from sqlalchemy.orm import joinedload
import logging

from app.models.gym import Gym
from app.models.user_gym import UserGym, GymRoleType
from app.models.user import User, UserRole
from app.models.event import Event
from app.models.schedule import ClassSession
from app.models.gym_module import GymModule

from app.schemas.gym import GymCreate, GymUpdate, GymWithStats
from app.repositories.async_gym import async_gym_repository
from fastapi import HTTPException, status
from redis.asyncio import Redis
from app.services.cache_service import cache_service
from app.schemas.user import GymUserSummary

logger = logging.getLogger(__name__)


class AsyncGymService:
    """
    Servicio async para gestionar gimnasios.

    Todos los métodos son async y utilizan AsyncSession y repositorios async.
    Incluye gestión de usuarios en gimnasios, roles, y estadísticas.

    Métodos principales:
    - create_gym() - Crear gimnasio
    - get_gym() - Obtener por ID
    - get_gym_by_subdomain() - Buscar por subdominio
    - get_gyms() - Lista con filtros
    - update_gym() - Actualizar datos
    - delete_gym() - Eliminar gimnasio
    - add_user_to_gym() - Agregar usuario con rol
    - remove_user_from_gym() - Remover usuario
    - update_user_role() - Cambiar rol de usuario
    - get_user_gyms() - Gimnasios de un usuario
    - get_gym_users() - Usuarios de un gimnasio
    - get_gym_with_stats() - Gimnasio con estadísticas
    - get_gym_details_public() - Detalles públicos para discovery
    """

    async def create_gym(
        self, db: AsyncSession, *, gym_in: GymCreate
    ) -> Gym:
        """
        Crear un nuevo gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_in: Datos del gimnasio a crear

        Returns:
            El gimnasio creado
        """
        return await async_gym_repository.create(db, obj_in=gym_in)

    async def get_gym(
        self, db: AsyncSession, gym_id: int
    ) -> Optional[Gym]:
        """
        Obtener un gimnasio por su ID.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            El gimnasio o None si no existe
        """
        return await async_gym_repository.get(db, id=gym_id)

    async def get_gym_by_subdomain(
        self, db: AsyncSession, subdomain: str
    ) -> Optional[Gym]:
        """
        Obtener un gimnasio por su subdominio.

        Args:
            db: Sesión async de base de datos
            subdomain: Subdominio del gimnasio

        Returns:
            El gimnasio o None si no existe
        """
        stmt = select(Gym).where(Gym.subdomain == subdomain)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_gyms(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None
    ) -> List[Gym]:
        """
        Obtener lista de gimnasios con filtros opcionales.

        Args:
            db: Sesión async de base de datos
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver
            is_active: Filtrar por estado activo/inactivo

        Returns:
            Lista de gimnasios
        """
        filters = {}
        if is_active is not None:
            filters["is_active"] = is_active

        return await async_gym_repository.get_multi(
            db, skip=skip, limit=limit, filters=filters
        )

    async def update_gym(
        self,
        db: AsyncSession,
        *,
        gym: Gym,
        gym_in: Union[GymUpdate, Dict[str, Any]]
    ) -> Gym:
        """
        Actualizar un gimnasio.

        Args:
            db: Sesión async de base de datos
            gym: Objeto gimnasio a actualizar
            gym_in: Datos actualizados

        Returns:
            El gimnasio actualizado
        """
        return await async_gym_repository.update(db, db_obj=gym, obj_in=gym_in)

    async def update_gym_status(
        self, db: AsyncSession, *, gym_id: int, is_active: bool
    ) -> Gym:
        """
        Actualizar el estado de un gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            is_active: Nuevo estado

        Returns:
            El gimnasio actualizado

        Raises:
            HTTPException: Si el gimnasio no existe
        """
        gym = await self.get_gym(db, gym_id=gym_id)
        if not gym:
            raise HTTPException(status_code=404, detail="Gimnasio no encontrado")

        return await async_gym_repository.update(
            db, db_obj=gym, obj_in={"is_active": is_active}
        )

    async def delete_gym(
        self, db: AsyncSession, *, gym_id: int
    ) -> Gym:
        """
        Eliminar un gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            El gimnasio eliminado

        Raises:
            HTTPException: Si el gimnasio no existe
        """
        gym = await self.get_gym(db, gym_id=gym_id)
        if not gym:
            raise HTTPException(status_code=404, detail="Gimnasio no encontrado")

        return await async_gym_repository.remove(db, id=gym_id)

    async def add_user_to_gym(
        self,
        db: AsyncSession,
        *,
        gym_id: int,
        user_id: int,
        role: GymRoleType = GymRoleType.MEMBER
    ) -> UserGym:
        """
        Añade un usuario a un gimnasio con el rol especificado.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            user_id: ID del usuario
            role: Rol del usuario en el gimnasio (default: MEMBER)

        Returns:
            UserGym: La relación usuario-gimnasio creada

        Raises:
            ValueError: Si el usuario ya pertenece al gimnasio

        Note:
            Hook integrado: Agrega usuario al canal general del gimnasio.
        """
        # Verificar que el usuario no pertenece ya al gimnasio
        stmt = select(UserGym).where(
            and_(UserGym.user_id == user_id, UserGym.gym_id == gym_id)
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise ValueError(f"El usuario {user_id} ya pertenece al gimnasio {gym_id}")

        # Crear la relación usuario-gimnasio
        user_gym = UserGym(
            user_id=user_id,
            gym_id=gym_id,
            role=role
        )
        db.add(user_gym)
        await db.flush()
        await db.refresh(user_gym)

        # Hook: Agregar usuario al canal general del gimnasio
        try:
            from app.services.gym_chat import gym_chat_service

            success = gym_chat_service.add_user_to_general_channel(db, gym_id, user_id)
            if success:
                logger.info(f"Usuario {user_id} agregado al canal general de gym {gym_id}")

                try:
                    gym_chat_service.send_welcome_message(db, gym_id, user_id)
                    logger.info(f"Mensaje de bienvenida enviado para usuario {user_id} en gym {gym_id}")
                except Exception as welcome_error:
                    logger.warning(f"No se pudo enviar mensaje de bienvenida: {welcome_error}")
            else:
                logger.warning(f"No se pudo agregar usuario {user_id} al canal general de gym {gym_id}")
        except Exception as chat_error:
            logger.error(f"Error agregando usuario al canal general: {chat_error}")

        return user_gym

    async def remove_user_from_gym(
        self, db: AsyncSession, *, gym_id: int, user_id: int
    ) -> None:
        """
        Eliminar un usuario de un gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            user_id: ID del usuario

        Raises:
            HTTPException: Si el usuario no existe, no pertenece al gym,
                          o es SUPER_ADMIN

        Note:
            Impide eliminar usuarios SUPER_ADMIN.
            Hook integrado: Remueve usuario del canal general.
        """
        # Verificar que el usuario existe y NO es SUPER_ADMIN
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user_to_remove = result.scalar_one_or_none()

        if not user_to_remove:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con ID {user_id} no encontrado."
            )

        if user_to_remove.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No se pueden eliminar administradores de plataforma de los gimnasios."
            )

        # Buscar la asociación
        stmt = select(UserGym).where(
            and_(UserGym.user_id == user_id, UserGym.gym_id == gym_id)
        )
        result = await db.execute(stmt)
        user_gym = result.scalar_one_or_none()

        if not user_gym:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El usuario {user_id} no pertenece al gimnasio {gym_id}"
            )

        # Hook: Remover usuario del canal general
        try:
            from app.services.gym_chat import gym_chat_service
            gym_chat_service.remove_user_from_general_channel(db, gym_id, user_id)
            logger.info(f"Usuario {user_id} removido del canal general de gym {gym_id}")
        except Exception as chat_error:
            logger.error(f"Error removiendo usuario del canal general: {chat_error}")

        # Eliminar la asociación
        await db.delete(user_gym)

    async def update_user_role(
        self, db: AsyncSession, *, gym_id: int, user_id: int, role: GymRoleType
    ) -> UserGym:
        """
        Actualizar el rol de un usuario en un gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            user_id: ID del usuario
            role: Nuevo rol del usuario

        Returns:
            UserGym actualizado

        Raises:
            HTTPException: Si el usuario no existe, no pertenece al gym,
                          o es SUPER_ADMIN

        Note:
            Impide modificar el rol de usuarios SUPER_ADMIN.
        """
        # Verificar que el usuario existe y NO es SUPER_ADMIN
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user_to_update = result.scalar_one_or_none()

        if not user_to_update:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con ID {user_id} no encontrado."
            )

        if user_to_update.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No se puede modificar el rol de un administrador de plataforma."
            )

        # Buscar la asociación
        stmt = select(UserGym).where(
            and_(UserGym.user_id == user_id, UserGym.gym_id == gym_id)
        )
        result = await db.execute(stmt)
        user_gym = result.scalar_one_or_none()

        if not user_gym:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El usuario {user_id} no pertenece al gimnasio {gym_id}"
            )

        # Actualizar el rol
        user_gym.role = role
        db.add(user_gym)

        return user_gym

    async def get_user_gyms(
        self, db: AsyncSession, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Obtener todos los gimnasios a los que pertenece un usuario.

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver

        Returns:
            Lista de diccionarios con datos del gimnasio y rol del usuario

        Raises:
            HTTPException 404: Si el usuario no existe
        """
        # Obtener primero el usuario
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con ID {user_id} no encontrado."
            )

        user_email = user.email

        # Consultar asociaciones y gimnasios
        stmt = (
            select(UserGym, Gym)
            .join(Gym, UserGym.gym_id == Gym.id)
            .where(UserGym.user_id == user_id, Gym.is_active == True)
            .order_by(Gym.name)
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        user_gyms = result.all()

        gym_list = []
        for user_gym, gym in user_gyms:
            gym_membership_dict = {
                "id": gym.id,
                "name": gym.name,
                "subdomain": gym.subdomain,
                "logo_url": gym.logo_url,
                "address": gym.address,
                "phone": gym.phone,
                "email": gym.email,
                "description": gym.description,
                "timezone": gym.timezone,
                "type": gym.type,
                "trainer_specialties": gym.trainer_specialties,
                "trainer_certifications": gym.trainer_certifications,
                "max_clients": gym.max_clients,
                "is_active": gym.is_active,
                "created_at": gym.created_at,
                "updated_at": gym.updated_at,
                "user_email": user_email,
                "user_role_in_gym": user_gym.role
            }
            gym_list.append(gym_membership_dict)

        return gym_list

    async def get_gym_users(
        self,
        db: AsyncSession,
        *,
        gym_id: int,
        role: Optional[GymRoleType] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Obtener todos los usuarios de un gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            role: Filtrar por rol específico
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver

        Returns:
            Lista de usuarios con su rol en el gimnasio
        """
        query = (
            select(UserGym, User)
            .join(User, UserGym.user_id == User.id)
            .where(UserGym.gym_id == gym_id)
        )

        if role:
            query = query.where(UserGym.role == role)

        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        users = result.all()

        user_list = []
        for user_gym, user in users:
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

            user_dict = {
                "id": user.id,
                "email": user.email,
                "full_name": full_name,
                "role": user_gym.role.value,
                "joined_at": user_gym.created_at
            }
            user_list.append(user_dict)

        return user_list

    async def get_gym_users_cached(
        self,
        db: AsyncSession,
        *,
        gym_id: int,
        role: Optional[GymRoleType] = None,
        skip: int = 0,
        limit: int = 100,
        redis_client: Optional[Redis] = None
    ) -> List[Dict[str, Any]]:
        """
        Versión cacheada para obtener todos los usuarios de un gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            role: Filtrar por rol específico
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver
            redis_client: Cliente Redis para caché

        Returns:
            Lista de usuarios con su rol en el gimnasio

        Note:
            Caché TTL: 5 minutos
            Usa GymUserSummary schema para validación
        """
        if not redis_client:
            return await self.get_gym_users(db=db, gym_id=gym_id, role=role, skip=skip, limit=limit)

        # Crear clave de caché
        cache_key = f"gym:{gym_id}:users:role:{role.value if role else 'all'}:skip:{skip}:limit:{limit}"

        # Función para obtener datos de la BD
        async def db_fetch():
            return await self.get_gym_users(db=db, gym_id=gym_id, role=role, skip=skip, limit=limit)

        try:
            users = await cache_service.get_or_set(
                redis_client=redis_client,
                cache_key=cache_key,
                db_fetch_func=db_fetch,
                model_class=GymUserSummary,
                expiry_seconds=300,  # 5 minutos
                is_list=True
            )
            return users
        except Exception as e:
            logger.error(f"Error al obtener usuarios cacheados para gym {gym_id}: {str(e)}", exc_info=True)
            return await self.get_gym_users(db=db, gym_id=gym_id, role=role, skip=skip, limit=limit)

    async def get_gym_with_stats(
        self, db: AsyncSession, *, gym_id: int
    ) -> Optional[GymWithStats]:
        """
        Obtener un gimnasio con estadísticas básicas.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            Gimnasio con estadísticas o None si no existe

        Note:
            Incluye contadores de:
            - Miembros por rol (members, trainers, admins)
            - Eventos totales
            - Clases totales
        """
        gym = await self.get_gym(db, gym_id=gym_id)
        if not gym:
            return None

        # Contar usuarios por rol
        stmt = (
            select(UserGym.role, func.count(UserGym.id).label("count"))
            .where(UserGym.gym_id == gym_id)
            .group_by(UserGym.role)
        )
        result = await db.execute(stmt)
        role_counts = result.all()

        # Inicializar contadores
        members_count = 0
        trainers_count = 0
        admins_count = 0

        for role, count in role_counts:
            if role == GymRoleType.MEMBER:
                members_count = count
            elif role == GymRoleType.TRAINER:
                trainers_count = count
            elif role in (GymRoleType.ADMIN, GymRoleType.OWNER):
                admins_count += count

        # Contar eventos
        stmt = select(func.count(Event.id)).where(Event.gym_id == gym_id)
        result = await db.execute(stmt)
        events_count = result.scalar() or 0

        # Contar clases
        stmt = select(func.count(ClassSession.id)).where(ClassSession.gym_id == gym_id)
        result = await db.execute(stmt)
        classes_count = result.scalar() or 0

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
            "timezone": gym.timezone,
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

    async def check_user_in_gym(
        self, db: AsyncSession, *, user_id: int, gym_id: int
    ) -> Optional[UserGym]:
        """
        Verificar si un usuario pertenece a un gimnasio.

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio

        Returns:
            La asociación usuario-gimnasio o None si no existe
        """
        stmt = select(UserGym).where(
            and_(UserGym.user_id == user_id, UserGym.gym_id == gym_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def check_user_role_in_gym(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        gym_id: int,
        required_roles: List[GymRoleType]
    ) -> bool:
        """
        Verificar si un usuario tiene uno de los roles requeridos en un gimnasio.

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio
            required_roles: Lista de roles aceptables

        Returns:
            True si el usuario tiene uno de los roles requeridos
        """
        user_gym = await self.check_user_in_gym(db, user_id=user_id, gym_id=gym_id)
        if not user_gym:
            return False

        return user_gym.role in required_roles

    async def get_gym_details_public(
        self, db: AsyncSession, *, gym_id: int
    ):
        """
        Obtener detalles completos de un gimnasio para discovery público.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            GymDetailedPublicSchema con todos los detalles públicos

        Note:
            Solo retorna gimnasios activos.
            Incluye: horarios, planes de membresía activos, módulos activos.
        """
        from app.schemas.gym import (
            GymDetailedPublicSchema,
            GymHoursPublic,
            MembershipPlanPublic,
            GymModulePublic
        )

        # Obtener gimnasio con relaciones
        stmt = (
            select(Gym)
            .options(
                joinedload(Gym.gym_hours),
                joinedload(Gym.membership_planes),
                joinedload(Gym.modules).joinedload(GymModule.module)
            )
            .where(Gym.id == gym_id, Gym.is_active == True)
        )
        result = await db.execute(stmt)
        gym = result.scalar_one_or_none()

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
                if plan.is_active:
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
                        price_amount=plan.price_cents / 100.0
                    ))

        # Convertir módulos (solo activos)
        modules = []
        if gym.modules:
            for gym_module in gym.modules:
                if gym_module.active:
                    modules.append(GymModulePublic(
                        module_name=gym_module.module.name,
                        is_enabled=gym_module.active
                    ))

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


# Instancia singleton del servicio async
async_gym_service = AsyncGymService()
