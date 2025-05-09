from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, HttpUrl, Field, validator
from app.models.user_gym import GymRoleType # Importar Enum

class GymBase(BaseModel):
    """Esquema base para gimnasios (tenants)"""
    name: str = Field(..., title="Nombre del gimnasio", max_length=255)
    subdomain: str = Field(..., title="Subdominio único para el gimnasio", max_length=100, pattern="^[a-z0-9-]+$")
    logo_url: Optional[HttpUrl] = Field(None, title="URL del logo del gimnasio")
    address: Optional[str] = Field(None, title="Dirección física del gimnasio", max_length=255)
    phone: Optional[str] = Field(None, title="Número de teléfono", max_length=20)
    email: Optional[EmailStr] = Field(None, title="Email de contacto del gimnasio")
    description: Optional[str] = Field(None, title="Descripción del gimnasio", max_length=500)
    
    @validator('subdomain')
    def validate_subdomain(cls, v):
        if not v or len(v) < 3:
            raise ValueError("El subdominio debe tener al menos 3 caracteres")
        return v

class GymCreate(GymBase):
    """Esquema para crear un nuevo gimnasio"""
    is_active: bool = Field(True, title="Estado del gimnasio")

class GymUpdate(BaseModel):
    """Esquema para actualizar un gimnasio existente"""
    name: Optional[str] = Field(None, title="Nombre del gimnasio", max_length=255)
    logo_url: Optional[HttpUrl] = Field(None, title="URL del logo del gimnasio")
    address: Optional[str] = Field(None, title="Dirección física del gimnasio", max_length=255)
    phone: Optional[str] = Field(None, title="Número de teléfono", max_length=20)
    email: Optional[EmailStr] = Field(None, title="Email de contacto del gimnasio")
    description: Optional[str] = Field(None, title="Descripción del gimnasio", max_length=500)
    is_active: Optional[bool] = Field(None, title="Estado del gimnasio")

class GymStatusUpdate(BaseModel):
    """Esquema para actualizar solo el estado de un gimnasio"""
    is_active: bool = Field(..., title="Estado del gimnasio")

class Gym(GymBase):
    """Esquema completo de gimnasio para respuestas"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class GymSchema(Gym):
    """Alias para Gym, manteniendo compatibilidad si se usa en otro sitio"""
    pass

# Nuevo esquema para la respuesta de /gyms/my
class UserGymMembershipSchema(GymSchema): # Hereda de GymSchema (que hereda de Gym)
    """Representa la pertenencia de un usuario a un gimnasio, incluyendo su rol"""
    user_email: EmailStr = Field(..., title="Email del usuario")
    user_role_in_gym: GymRoleType = Field(..., title="Rol del usuario en este gimnasio")

class GymWithStats(Gym):
    """Gimnasio con estadísticas básicas"""
    members_count: int = Field(0, title="Número de miembros")
    trainers_count: int = Field(0, title="Número de entrenadores")
    admins_count: int = Field(0, title="Número de administradores")
    events_count: int = Field(0, title="Número de eventos")
    classes_count: int = Field(0, title="Número de clases programadas")

class UserGymRoleUpdate(BaseModel):
    """Esquema para actualizar el rol de un usuario dentro de un gimnasio"""
    role: GymRoleType = Field(..., title="Nuevo rol del usuario en el gimnasio")

class UserGymSchema(BaseModel):
    """Esquema para representar la relación entre usuario y gimnasio."""
    id: int
    user_id: int
    gym_id: int
    role: GymRoleType
    created_at: datetime

    class Config:
        from_attributes = True # Permite crear desde el modelo ORM 

# Esquema público para respuestas de gimnasios accesibles públicamente
class GymPublicSchema(GymBase):
    """Esquema público de gimnasio para respuestas públicas"""
    id: int
    is_active: bool

    class Config:
        from_attributes = True