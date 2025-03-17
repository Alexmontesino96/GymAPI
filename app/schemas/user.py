from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


# Propiedades compartidas
class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = True
    is_superuser: bool = False
    full_name: Optional[str] = None
    picture: Optional[str] = None
    role: Optional[UserRole] = None
    phone_number: Optional[str] = None
    birth_date: Optional[datetime] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    bio: Optional[str] = None
    goals: Optional[str] = None
    health_conditions: Optional[str] = None


# Propiedades para recibir a través de API al crear usuario
class UserCreate(UserBase):
    email: EmailStr
    password: Optional[str] = None
    role: UserRole = UserRole.MEMBER


# Propiedades para recibir a través de API al actualizar
class UserUpdate(UserBase):
    password: Optional[str] = None


# Propiedades adicionales para perfiles
class UserProfileUpdate(BaseModel):
    phone_number: Optional[str] = None
    birth_date: Optional[datetime] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    bio: Optional[str] = None
    goals: Optional[str] = None
    health_conditions: Optional[str] = None


# Propiedades compartidas adicionales
class UserInDBBase(UserBase):
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Propiedades para retornar a través de API
class User(UserInDBBase):
    pass


# Propiedades almacenadas en DB
class UserInDB(UserInDBBase):
    hashed_password: Optional[str] = None
    auth0_id: Optional[str] = None


# Esquema para cambiar el rol de un usuario
class UserRoleUpdate(BaseModel):
    role: UserRole 