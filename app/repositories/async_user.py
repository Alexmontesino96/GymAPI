"""
AsyncUserRepository - Repositorio async para operaciones de usuario.

Este repositorio hereda de AsyncBaseRepository y agrega métodos específicos
para operaciones de usuario con full async/await.

Migrado en FASE 2 de la conversión sync → async.
"""
import json
from typing import Any, Dict, Optional, Union, List
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, and_, select

from app.models.user import User, UserRole
from app.repositories.async_base import AsyncBaseRepository
from app.schemas.user import UserCreate, UserUpdate, UserPublicProfile
from app.models.user_gym import UserGym, GymRoleType


class AsyncUserRepository(AsyncBaseRepository[User, UserCreate, UserUpdate]):
    """
    Repositorio async para operaciones de usuarios.

    Hereda de AsyncBaseRepository:
    - get(db, id, gym_id) - Obtener usuario por ID
    - get_multi(db, skip, limit, gym_id, filters) - Obtener múltiples usuarios
    - create(db, obj_in, gym_id) - Crear usuario
    - update(db, db_obj, obj_in, gym_id) - Actualizar usuario
    - remove(db, id, gym_id) - Eliminar usuario
    - exists(db, id, gym_id) - Verificar existencia

    Métodos específicos de User:
    - get_by_email() - Buscar por email
    - get_by_auth0_id() - Buscar por Auth0 ID
    - get_by_role() - Filtrar por rol
    - search() - Búsqueda avanzada multi-criterio
    - get_public_participants() - Perfiles públicos de participantes
    - create_from_auth0() - Crear desde datos de Auth0
    """

    async def get_by_email(self, db: AsyncSession, *, email: str) -> Optional[User]:
        """
        Obtener un usuario por email.

        Args:
            db: Sesión async de base de datos
            email: Email del usuario a buscar

        Returns:
            Usuario encontrado o None
        """
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_auth0_id(self, db: AsyncSession, *, auth0_id: str) -> Optional[User]:
        """
        Obtener un usuario por ID de Auth0.

        Args:
            db: Sesión async de base de datos
            auth0_id: ID de Auth0 del usuario

        Returns:
            Usuario encontrado o None
        """
        stmt = select(User).where(User.auth0_id == auth0_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_role(
        self,
        db: AsyncSession,
        *,
        role: UserRole,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """
        Obtener usuarios filtrados por rol global.

        Args:
            db: Sesión async de base de datos
            role: Rol a filtrar
            skip: Registros a omitir (paginación)
            limit: Límite de registros

        Returns:
            Lista de usuarios con el rol especificado
        """
        stmt = select(User).where(User.role == role).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_role_and_gym(
        self,
        db: AsyncSession,
        *,
        role: UserRole,
        gym_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """
        Obtener usuarios de un gimnasio específico, filtrados por su rol GLOBAL.

        Nota: Filtra por el rol definido en la tabla User, no el de UserGym.
        Para filtrar por rol dentro del gym (GymRoleType), usar get_gym_participants().

        Args:
            db: Sesión async de base de datos
            role: Rol global del usuario
            gym_id: ID del gimnasio
            skip: Registros a omitir
            limit: Límite de registros

        Returns:
            Lista de usuarios del gym con el rol especificado
        """
        stmt = select(User)
        stmt = stmt.join(UserGym, User.id == UserGym.user_id)
        stmt = stmt.where(UserGym.gym_id == gym_id)
        stmt = stmt.where(User.role == role)
        stmt = stmt.offset(skip).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self,
        db: AsyncSession,
        *,
        name: Optional[str] = None,
        email: Optional[str] = None,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        created_before: Optional[datetime] = None,
        created_after: Optional[datetime] = None,
        gym_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """
        Búsqueda avanzada de usuarios con múltiples criterios.

        Args:
            db: Sesión async de base de datos
            name: Búsqueda parcial en first_name o last_name
            email: Búsqueda parcial en email
            role: Filtrar por rol
            is_active: Filtrar por estado activo
            created_before: Filtrar usuarios creados antes de fecha
            created_after: Filtrar usuarios creados después de fecha
            gym_id: Filtrar usuarios de un gimnasio específico
            skip: Registros a omitir
            limit: Límite de registros

        Returns:
            Lista de usuarios que cumplen los criterios
        """
        stmt = select(User)

        # Join con UserGym si necesitamos filtrar por gimnasio
        if gym_id is not None:
            stmt = stmt.join(UserGym, User.id == UserGym.user_id)
            stmt = stmt.where(UserGym.gym_id == gym_id)

        # Aplicar filtros si están presentes
        if name:
            stmt = stmt.where(
                or_(
                    User.first_name.ilike(f"%{name}%"),
                    User.last_name.ilike(f"%{name}%")
                )
            )

        if email:
            stmt = stmt.where(User.email.ilike(f"%{email}%"))

        if role:
            stmt = stmt.where(User.role == role)

        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)

        if created_before:
            stmt = stmt.where(User.created_at <= created_before)

        if created_after:
            stmt = stmt.where(User.created_at >= created_after)

        # Aplicar paginación
        stmt = stmt.offset(skip).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_public_participants(
        self,
        db: AsyncSession,
        *,
        gym_id: int,
        roles: List[UserRole],
        name: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[UserPublicProfile]:
        """
        Obtiene perfiles públicos de participantes de un gym, filtrados y paginados.

        Filtra por el rol del usuario dentro del gimnasio (UserGym.role),
        no por su rol global.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            roles: Lista de roles a incluir (filtrado por rol en el gym)
            name: Búsqueda opcional por nombre
            skip: Registros a omitir
            limit: Límite de registros

        Returns:
            Lista de perfiles públicos de usuarios
        """
        role_values = [r.value if hasattr(r, "value") else str(r) for r in roles]

        stmt = select(
            User.id,
            User.first_name,
            User.last_name,
            User.picture,
            UserGym.role.label("role"),
            User.bio,
            User.is_active,
        )
        stmt = stmt.join(UserGym, User.id == UserGym.user_id)
        stmt = stmt.where(UserGym.gym_id == gym_id)
        stmt = stmt.where(UserGym.role.in_(role_values))

        if name:
            stmt = stmt.where(
                or_(
                    User.first_name.ilike(f"%{name}%"),
                    User.last_name.ilike(f"%{name}%")
                )
            )

        stmt = stmt.order_by(User.first_name, User.last_name, User.id)
        stmt = stmt.offset(skip).limit(limit)

        result = await db.execute(stmt)
        results = result.all()

        participants = [
            UserPublicProfile(
                id=row[0],
                first_name=row[1],
                last_name=row[2],
                picture=row[3],
                role=row[4],
                bio=row[5],
                is_active=row[6]
            ) for row in results
        ]
        return participants

    async def get_gym_participants(
        self,
        db: AsyncSession,
        *,
        gym_id: int,
        roles: List[UserRole],
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """
        Obtiene usuarios completos (modelo User) de un gym, filtrados por rol
        *dentro* del gimnasio y paginados.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            roles: Lista de roles a filtrar (rol dentro del gym)
            skip: Registros a omitir
            limit: Límite de registros

        Returns:
            Lista de usuarios con atributo gym_role añadido
        """
        role_values = [r.value if hasattr(r, "value") else str(r) for r in roles]

        stmt = select(User, UserGym.role.label('gym_role'))
        stmt = stmt.join(UserGym, User.id == UserGym.user_id)
        stmt = stmt.where(UserGym.gym_id == gym_id)
        stmt = stmt.where(UserGym.role.in_(role_values))
        stmt = stmt.order_by(User.first_name, User.last_name, User.id)
        stmt = stmt.offset(skip).limit(limit)

        result = await db.execute(stmt)
        results = result.all()

        users_with_roles = []
        for user, gym_role in results:
            user.gym_role = gym_role
            users_with_roles.append(user)
        return users_with_roles

    async def create_from_auth0(self, db: AsyncSession, *, auth0_user: Dict) -> User:
        """
        Crear un usuario a partir de datos de Auth0.

        Args:
            db: Sesión async de base de datos
            auth0_user: Diccionario con datos del usuario de Auth0

        Returns:
            Usuario creado
        """
        auth0_id = auth0_user.get("sub")
        email = auth0_user.get("email")
        name = auth0_user.get("name") or auth0_user.get("nickname") or ""
        picture = auth0_user.get("picture")
        locale = auth0_user.get("locale")

        # Si no hay email, crear uno temporal usando el auth0_id
        if not email and auth0_id:
            email = f"temp_{auth0_id.replace('|', '_')}@example.com"

        # Procesar el nombre completo
        name_parts = name.split(" ", 1) if name else ["", ""]
        first_name = name_parts[0] if len(name_parts) > 0 else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Crear usuario con datos de Auth0
        db_obj = User(
            auth0_id=auth0_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            picture=picture,
            locale=locale,
            auth0_metadata=json.dumps(auth0_user),
            role=UserRole.MEMBER  # Por defecto, nuevos usuarios son miembros
        )

        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def get_all_gym_users(self, db: AsyncSession, gym_id: int) -> List[User]:
        """
        Obtiene todos los usuarios activos asociados a un gimnasio específico.

        Args:
            db: Sesión de base de datos async
            gym_id: ID del gimnasio

        Returns:
            Lista de usuarios activos del gimnasio
        """
        stmt = select(User)
        stmt = stmt.join(UserGym, User.id == UserGym.user_id)
        stmt = stmt.where(UserGym.gym_id == gym_id)
        stmt = stmt.where(User.is_active == True)

        result = await db.execute(stmt)
        return list(result.scalars().all())


# Instancia singleton del repositorio async
async_user_repository = AsyncUserRepository(User)
