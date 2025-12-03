import json
from typing import Any, Dict, Optional, Union, List
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, and_, select
from sqlalchemy.orm import selectinload
from fastapi.encoders import jsonable_encoder

from app.models.user import User, UserRole
from app.repositories.base import BaseRepository
from app.schemas.user import UserCreate, UserUpdate, UserPublicProfile
from app.models.gym import Gym
from app.models.user_gym import UserGym, GymRoleType


class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        """
        Obtener un usuario por email.
        """
        return db.query(User).filter(User.email == email).first()

    async def get_by_email_async(self, db: AsyncSession, *, email: str) -> Optional[User]:
        """
        Obtener un usuario por email (async).
        """
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    def get_by_auth0_id(self, db: Session, *, auth0_id: str) -> Optional[User]:
        """
        Obtener un usuario por ID de Auth0.
        """
        print(f"DEBUG: Inside repo get_by_auth0_id, type(db) = {type(db)}, db = {repr(db)}")
        return db.query(User).filter(User.auth0_id == auth0_id).first()

    async def get_by_auth0_id_async(self, db: AsyncSession, *, auth0_id: str) -> Optional[User]:
        """
        Obtener un usuario por ID de Auth0 (async).
        """
        stmt = select(User).where(User.auth0_id == auth0_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    def get_by_role(self, db: Session, *, role: UserRole, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Obtener usuarios filtrados por rol.
        """
        return db.query(User).filter(User.role == role).offset(skip).limit(limit).all()

    async def get_by_role_async(self, db: AsyncSession, *, role: UserRole, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Obtener usuarios filtrados por rol (async).
        """
        stmt = select(User).where(User.role == role).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()

    def get_by_role_and_gym(
        self, 
        db: Session, 
        *, 
        role: UserRole,
        gym_id: int,
        skip: int = 0, 
        limit: int = 100
    ) -> List[User]:
        """
        Obtener usuarios de un gimnasio específico, filtrados por su rol GLOBAL.
        Nota: Esto filtra por el rol definido en la tabla User, no el de UserGym.
        Si se necesita filtrar por el rol DENTRO del gym (GymRoleType), se necesita otro método.
        """
        return (
            db.query(self.model)
            .join(UserGym, self.model.id == UserGym.user_id)
            .filter(UserGym.gym_id == gym_id)
            .filter(self.model.role == role)
            .offset(skip)
            .limit(limit)
            .all()
        )

    async def get_by_role_and_gym_async(
        self,
        db: AsyncSession,
        *,
        role: UserRole,
        gym_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """
        Obtener usuarios de un gimnasio específico, filtrados por su rol GLOBAL (async).
        Nota: Esto filtra por el rol definido en la tabla User, no el de UserGym.
        """
        stmt = select(User)
        stmt = stmt.join(UserGym, User.id == UserGym.user_id)
        stmt = stmt.where(UserGym.gym_id == gym_id)
        stmt = stmt.where(User.role == role)
        stmt = stmt.offset(skip).limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

    def search(
        self,
        db: Session,
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
        Si se proporciona gym_id, filtra solo usuarios de ese gimnasio.
        """
        query = db.query(User)

        # Unir con UserGym si necesitamos filtrar por gimnasio
        if gym_id is not None:
            query = query.join(UserGym, User.id == UserGym.user_id)
            query = query.filter(UserGym.gym_id == gym_id)

        # Aplicar filtros si están presentes
        if name:
            query = query.filter(
                or_(
                    User.first_name.ilike(f"%{name}%"),
                    User.last_name.ilike(f"%{name}%")
                )
            )

        if email:
            query = query.filter(User.email.ilike(f"%{email}%"))

        if role:
            query = query.filter(User.role == role)

        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        if created_before:
            query = query.filter(User.created_at <= created_before)

        if created_after:
            query = query.filter(User.created_at >= created_after)

        # Aplicar paginación
        return query.offset(skip).limit(limit).all()

    async def search_async(
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
        Búsqueda avanzada de usuarios con múltiples criterios (async).
        Si se proporciona gym_id, filtra solo usuarios de ese gimnasio.
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
        return result.scalars().all()

    def get_public_participants(
        self,
        db: Session,
        *,
        gym_id: int,
        roles: List[UserRole],
        name: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[UserPublicProfile]:
        """
        Obtiene perfiles públicos de participantes de un gym, filtrados y paginados.
        Selecciona solo los campos necesarios para UserPublicProfile.
        A partir de ahora filtra por el rol del usuario dentro del gimnasio (UserGym.role),
        no por su rol global.
        """
        # Asegurarse de convertir la lista de roles (UserRole) a los valores string que usa GymRoleType
        role_values = [r.value if hasattr(r, "value") else str(r) for r in roles]

        query = db.query(
            User.id,
            User.first_name,
            User.last_name,
            User.picture,
            UserGym.role.label("role"),
            User.bio,
            User.is_active,
        )
        query = query.join(UserGym, User.id == UserGym.user_id)
        query = query.filter(UserGym.gym_id == gym_id)
        # <<<< Filtrado por rol dentro del gym >>>>
        query = query.filter(UserGym.role.in_(role_values))

        if name:
            # Filtrar por nombre o apellido (insensible a mayúsculas/minúsculas)
            query = query.filter(
                or_(
                    User.first_name.ilike(f"%{name}%"),
                    User.last_name.ilike(f"%{name}%")
                )
            )

        # Aplicar ordenamiento consistente para paginación
        query = query.order_by(User.first_name, User.last_name, User.id)

        # Aplicar paginación directamente en la consulta SQL
        results = query.offset(skip).limit(limit).all()

        # Construir la lista de UserPublicProfile directamente desde los resultados
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

    async def get_public_participants_async(
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
        Obtiene perfiles públicos de participantes de un gym, filtrados y paginados (async).
        Filtra por el rol del usuario dentro del gimnasio (UserGym.role).
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

    def get_gym_participants(
        self,
        db: Session,
        *,
        gym_id: int,
        roles: List[UserRole],
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """
        Obtiene usuarios completos (modelo User) de un gym, filtrados por rol
        *dentro* del gimnasio y paginados.
        """
        role_values = [r.value if hasattr(r, "value") else str(r) for r in roles]

        query = db.query(User, UserGym.role.label('gym_role'))
        query = query.join(UserGym, User.id == UserGym.user_id)
        query = query.filter(UserGym.gym_id == gym_id)
        # <<<< Filtrar por rol en el gimnasio (UserGym.role) >>>>
        query = query.filter(UserGym.role.in_(role_values))

        # Ordenar por nombre para paginación estable
        query = query.order_by(User.first_name, User.last_name, User.id)

        results = query.offset(skip).limit(limit).all()
        users_with_roles = []
        for user, gym_role in results:
            user.gym_role = gym_role  # Añadir el rol del gimnasio al objeto usuario
            users_with_roles.append(user)
        return users_with_roles

    async def get_gym_participants_async(
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
        *dentro* del gimnasio y paginados (async).
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

    def create(self, db: Session, *, obj_in: UserCreate) -> User:
        """
        Crear un usuario.
        """
        if isinstance(obj_in, dict):
            obj_in_data = obj_in
        else:
            obj_in_data = obj_in.model_dump(exclude_unset=True)

        db_obj = User(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    async def create_async(self, db: AsyncSession, *, obj_in: UserCreate) -> User:
        """
        Crear un usuario (async).
        """
        if isinstance(obj_in, dict):
            obj_in_data = obj_in
        else:
            obj_in_data = obj_in.model_dump(exclude_unset=True)

        db_obj = User(**obj_in_data)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: User,
        obj_in: Union[UserUpdate, Dict[str, Any]]
    ) -> User:
        """
        Actualizar un usuario.
        """
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    async def update_async(
        self,
        db: AsyncSession,
        *,
        db_obj: User,
        obj_in: Union[UserUpdate, Dict[str, Any]]
    ) -> User:
        """
        Actualizar un usuario (async).
        """
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])

        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    def create_from_auth0(self, db: Session, *, auth0_user: Dict) -> User:
        """
        Crear un usuario a partir de datos de Auth0.
        """
        auth0_id = auth0_user.get("sub")
        email = auth0_user.get("email")
        name = auth0_user.get("name") or auth0_user.get("nickname") or ""
        picture = auth0_user.get("picture")
        locale = auth0_user.get("locale")
        
        # Si no hay email, crear uno temporal usando el auth0_id
        if not email and auth0_id:
            email = f"temp_{auth0_id.replace('|', '_')}@example.com"
        
        # Procesar el nombre completo para obtener first_name y last_name
        name_parts = name.split(" ", 1) if name else ["", ""]
        first_name = name_parts[0] if len(name_parts) > 0 else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        # Crear un nuevo usuario con datos de Auth0
        db_obj = User(
            auth0_id=auth0_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            picture=picture,
            locale=locale,
            auth0_metadata=json.dumps(auth0_user),
            # Por defecto, los nuevos usuarios de Auth0 son miembros
            role=UserRole.MEMBER
        )
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    async def create_from_auth0_async(self, db: AsyncSession, *, auth0_user: Dict) -> User:
        """
        Crear un usuario a partir de datos de Auth0 (async).
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
            role=UserRole.MEMBER
        )

        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    def authenticate(self, db: Session, *, email: str, password: str) -> Optional[User]:
        """
        Autenticar un usuario con email y contraseña.
        Este método ya no realiza una autenticación real, ya que la autenticación
        se maneja exclusivamente a través de Auth0. Se mantiene por compatibilidad.
        """
        # La autenticación ahora se realiza a través de Auth0
        # Este método solo devuelve el usuario si existe, ya que la validación
        # de la contraseña se realiza en Auth0
        return self.get_by_email(db, email=email)

    def is_active(self, user: User) -> bool:
        """
        Verificar si un usuario está activo.
        """
        return user.is_active

    def is_superuser(self, user: User) -> bool:
        """
        Verifica si un usuario es superadmin.
        """
        return user.role == UserRole.SUPERADMIN

    def get_all_gym_users(self, db: Session, gym_id: int) -> List[User]:
        """
        Obtiene todos los usuarios asociados a un gimnasio específico.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            
        Returns:
            Lista de usuarios del gimnasio
        """
        query = db.query(User)
        query = query.join(UserGym, User.id == UserGym.user_id)
        query = query.filter(UserGym.gym_id == gym_id)
        query = query.filter(User.is_active == True)  # Solo usuarios activos
        
        # No aplicamos paginación para obtener todos los usuarios
        return query.all()

    async def get_all_gym_users_async(self, db: AsyncSession, gym_id: int) -> List[User]:
        """
        Obtiene todos los usuarios asociados a un gimnasio específico (async).

        Args:
            db: Sesión de base de datos async
            gym_id: ID del gimnasio

        Returns:
            Lista de usuarios del gimnasio
        """
        stmt = select(User)
        stmt = stmt.join(UserGym, User.id == UserGym.user_id)
        stmt = stmt.where(UserGym.gym_id == gym_id)
        stmt = stmt.where(User.is_active == True)

        result = await db.execute(stmt)
        return result.scalars().all()

    # ==========================================
    # Métodos async heredados de BaseRepository
    # ==========================================

    async def get_async(self, db: AsyncSession, id: Any, gym_id: Optional[int] = None) -> Optional[User]:
        """
        Obtener un usuario por ID con filtro opcional de tenant (async).

        Args:
            db: Sesión de base de datos async
            id: ID del usuario a obtener
            gym_id: ID opcional del gimnasio (tenant) para filtrar

        Returns:
            El usuario solicitado o None si no existe
        """
        stmt = select(User).where(User.id == id)

        # Filtrar por gimnasio si se proporciona (User no tiene gym_id directo,
        # pero se puede filtrar via UserGym)
        if gym_id is not None:
            stmt = stmt.join(UserGym, User.id == UserGym.user_id)
            stmt = stmt.where(UserGym.gym_id == gym_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi_async(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        gym_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[User]:
        """
        Obtener múltiples usuarios con filtros opcionales (async).

        Args:
            db: Sesión de base de datos async
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver
            gym_id: ID opcional del gimnasio para filtrar resultados
            filters: Diccionario de filtros adicionales {campo: valor}

        Returns:
            Lista de usuarios que coinciden con los criterios
        """
        stmt = select(User)

        # Filtrar por gimnasio si se proporciona
        if gym_id is not None:
            stmt = stmt.join(UserGym, User.id == UserGym.user_id)
            stmt = stmt.where(UserGym.gym_id == gym_id)

        # Aplicar filtros adicionales si se proporcionan
        if filters:
            for field, value in filters.items():
                if hasattr(User, field):
                    stmt = stmt.where(getattr(User, field) == value)

        stmt = stmt.offset(skip).limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

    async def remove_async(self, db: AsyncSession, *, id: int, gym_id: Optional[int] = None) -> User:
        """
        Eliminar un usuario con verificación opcional de tenant (async).

        Args:
            db: Sesión de base de datos async
            id: ID del usuario a eliminar
            gym_id: ID opcional del gimnasio para verificar pertenencia

        Returns:
            El usuario eliminado

        Raises:
            ValueError: Si el usuario no existe o no pertenece al gimnasio especificado
        """
        user = await self.get_async(db, id=id, gym_id=gym_id)
        if not user:
            if gym_id:
                raise ValueError(f"Usuario con ID {id} no encontrado en el gimnasio {gym_id}")
            else:
                raise ValueError(f"Usuario con ID {id} no encontrado")

        await db.delete(user)
        await db.flush()
        return user

    async def exists_async(self, db: AsyncSession, id: int, gym_id: Optional[int] = None) -> bool:
        """
        Verificar si un usuario existe con verificación opcional de tenant (async).

        Args:
            db: Sesión de base de datos async
            id: ID del usuario a verificar
            gym_id: ID opcional del gimnasio para verificar pertenencia

        Returns:
            True si el usuario existe, False en caso contrario
        """
        stmt = select(User.id).where(User.id == id)

        if gym_id is not None:
            stmt = stmt.join(UserGym, User.id == UserGym.user_id)
            stmt = stmt.where(UserGym.gym_id == gym_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None


user_repository = UserRepository(User) 