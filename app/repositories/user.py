import json
from typing import Any, Dict, Optional, Union, List
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from passlib.context import CryptContext
from fastapi.encoders import jsonable_encoder

from app.models.user import User, UserRole
from app.repositories.base import BaseRepository
from app.schemas.user import UserCreate, UserUpdate

# Contexto para encriptar contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """
    Obtener el hash de una contraseña
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verificar que una contraseña coincida con el hash
    """
    return pwd_context.verify(plain_password, hashed_password)


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
        return db.query(User).filter(User.auth0_id == auth0_id).first()

    def get_by_role(self, db: Session, *, role: UserRole, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Obtener usuarios filtrados por rol.
        """
        return db.query(User).filter(User.role == role).offset(skip).limit(limit).all()
        
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
        skip: int = 0, 
        limit: int = 100
    ) -> List[User]:
        """
        Búsqueda avanzada de usuarios con múltiples criterios.
        
        Args:
            db: Sesión de base de datos
            name: Búsqueda parcial por nombre
            email: Búsqueda parcial por email
            role: Filtrar por rol específico
            is_active: Filtrar por usuarios activos/inactivos
            created_before: Usuarios creados antes de esta fecha
            created_after: Usuarios creados después de esta fecha
            skip: Número de registros a saltar (paginación)
            limit: Número máximo de registros a devolver
            
        Returns:
            List[User]: Lista de usuarios que coinciden con los criterios
        """
        query = db.query(User)
        
        # Aplicar filtros si están presentes
        if name:
            query = query.filter(User.full_name.ilike(f"%{name}%"))
            
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

    def create(self, db: Session, *, obj_in: UserCreate) -> User:
        """
        Crear un usuario.
        """
        if isinstance(obj_in, dict):
            obj_in_data = obj_in
        else:
            obj_in_data = obj_in.model_dump(exclude_unset=True)
        if "password" in obj_in_data and obj_in_data["password"]:
            hashed_password = pwd_context.hash(obj_in_data["password"])
            del obj_in_data["password"]
            obj_in_data["hashed_password"] = hashed_password
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
        if "password" in update_data and update_data["password"]:
            hashed_password = pwd_context.hash(update_data["password"])
            del update_data["password"]
            update_data["hashed_password"] = hashed_password
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
        
        # Crear un nuevo usuario con datos de Auth0
        db_obj = User(
            auth0_id=auth0_id,
            email=email,
            full_name=name,
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
        """
        user = self.get_by_email(db, email=email)
        if not user:
            return None
        if not user.hashed_password:
            return None
        if not pwd_context.verify(password, user.hashed_password):
            return None
        return user

    def is_active(self, user: User) -> bool:
        """
        Verificar si un usuario está activo.
        """
        return user.is_active

    def is_superuser(self, user: User) -> bool:
        """
        Verificar si un usuario es superusuario.
        """
        return user.is_superuser


user_repository = UserRepository(User) 