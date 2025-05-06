import json
from typing import Any, Dict, Optional, Union, List
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
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

    def get_by_auth0_id(self, db: Session, *, auth0_id: str) -> Optional[User]:
        """
        Obtener un usuario por ID de Auth0.
        """
        print(f"DEBUG: Inside repo get_by_auth0_id, type(db) = {type(db)}, db = {repr(db)}")
        return db.query(User).filter(User.auth0_id == auth0_id).first()

    def get_by_role(self, db: Session, *, role: UserRole, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Obtener usuarios filtrados por rol.
        """
        return db.query(User).filter(User.role == role).offset(skip).limit(limit).all()

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
        """
        query = db.query(
            User.id, User.first_name, User.last_name, User.picture,
            User.role, User.bio, User.is_active
        )
        query = query.join(UserGym, User.id == UserGym.user_id)
        query = query.filter(UserGym.gym_id == gym_id)
        query = query.filter(User.role.in_(roles)) # Filtrar por lista de roles

        if name:
            # Filtrar por nombre o apellido (insensible a mayúsculas/minúsculas)
            query = query.filter(
                or_(
                    User.first_name.ilike(f"%{name}%"),
                    User.last_name.ilike(f"%{name}%")
                )
            )

        # Aplicar ordenamiento consistente para paginación
        # Ordenar por nombre, apellido e ID para desempate
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
        Obtiene usuarios completos (modelo User) de un gym, filtrados por rol y paginados.
        """
        query = db.query(User)
        query = query.join(UserGym, User.id == UserGym.user_id)
        query = query.filter(UserGym.gym_id == gym_id)
        query = query.filter(User.role.in_(roles)) # Filtrar por lista de roles

        # Aplicar ordenamiento consistente para paginación (importante)
        # Ordenar por nombre, apellido e ID para desempate
        query = query.order_by(User.first_name, User.last_name, User.id)

        # Aplicar paginación directamente en la consulta SQL
        return query.offset(skip).limit(limit).all()

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


user_repository = UserRepository(User) 