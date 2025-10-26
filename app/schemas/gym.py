from typing import Optional, List, Dict, Any
from datetime import datetime, time
from pydantic import BaseModel, EmailStr, HttpUrl, Field, validator, field_serializer
from enum import Enum
from app.models.user_gym import GymRoleType # Importar Enum
import pytz

class GymType(str, Enum):
    """Tipos de gimnasio soportados"""
    gym = "gym"
    personal_trainer = "personal_trainer"

class GymBase(BaseModel):
    """Esquema base para gimnasios (tenants)"""
    name: str = Field(..., title="Nombre del gimnasio", max_length=255)
    subdomain: str = Field(..., title="Subdominio único para el gimnasio", max_length=100, pattern="^[a-z0-9-]+$")
    logo_url: Optional[HttpUrl] = Field(None, title="URL del logo del gimnasio")
    address: Optional[str] = Field(None, title="Dirección física del gimnasio", max_length=255)
    phone: Optional[str] = Field(None, title="Número de teléfono", max_length=20)
    email: Optional[EmailStr] = Field(None, title="Email de contacto del gimnasio")
    description: Optional[str] = Field(None, title="Descripción del gimnasio", max_length=500)
    timezone: str = Field('UTC', title="Zona horaria del gimnasio", max_length=50, description="Timezone en formato pytz (ej: 'America/Mexico_City')")

    # Nuevos campos para soporte de entrenadores
    type: GymType = Field(GymType.gym, title="Tipo de gimnasio", description="gym para gimnasio tradicional, personal_trainer para entrenador individual")
    trainer_specialties: Optional[List[str]] = Field(None, title="Especialidades del entrenador", description="Solo para type=personal_trainer")
    trainer_certifications: Optional[List[Dict[str, Any]]] = Field(None, title="Certificaciones del entrenador", description="Lista de certificaciones con nombre y año")
    max_clients: Optional[int] = Field(None, title="Máximo de clientes", description="Límite de clientes simultáneos para entrenadores")
    
    @validator('subdomain')
    def validate_subdomain(cls, v):
        if not v or len(v) < 3:
            raise ValueError("El subdominio debe tener al menos 3 caracteres")
        return v
    
    @validator('timezone')
    def validate_timezone(cls, v):
        if v not in pytz.all_timezones:
            raise ValueError(f"Zona horaria inválida: {v}. Debe ser una zona horaria válida de pytz.")
        return v

    @field_serializer('logo_url')
    def serialize_logo_url(self, logo_url: Optional[HttpUrl]) -> Optional[str]:
        """Convierte HttpUrl a string para compatibilidad con PostgreSQL"""
        return str(logo_url) if logo_url else None

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
    timezone: Optional[str] = Field(None, title="Zona horaria del gimnasio", max_length=50, description="Timezone en formato pytz (ej: 'America/Mexico_City')")
    is_active: Optional[bool] = Field(None, title="Estado del gimnasio")
    
    @validator('timezone')
    def validate_timezone(cls, v):
        if v is not None and v not in pytz.all_timezones:
            raise ValueError(f"Zona horaria inválida: {v}. Debe ser una zona horaria válida de pytz.")
        return v

    @field_serializer('logo_url')
    def serialize_logo_url(self, logo_url: Optional[HttpUrl]) -> Optional[str]:
        """Convierte HttpUrl a string para compatibilidad con PostgreSQL"""
        return str(logo_url) if logo_url else None

class GymStatusUpdate(BaseModel):
    """Esquema para actualizar solo el estado de un gimnasio"""
    is_active: bool = Field(..., title="Estado del gimnasio")

class Gym(GymBase):
    """Esquema completo de gimnasio para respuestas"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Propiedades helper computadas
    @property
    def is_personal_trainer(self) -> bool:
        """Verifica si es un espacio de entrenador personal"""
        return self.type == GymType.personal_trainer

    @property
    def is_traditional_gym(self) -> bool:
        """Verifica si es un gimnasio tradicional"""
        return self.type == GymType.gym

    @property
    def display_name(self) -> str:
        """Retorna nombre formateado según el tipo"""
        if self.is_personal_trainer and self.name.startswith("Entrenamiento Personal "):
            return self.name.replace("Entrenamiento Personal ", "")
        return self.name

    @property
    def entity_type_label(self) -> str:
        """Label contextual para UI"""
        return "Espacio de Trabajo" if self.is_personal_trainer else "Gimnasio"

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
class GymPublicSchema(BaseModel):
    """Esquema público de gimnasio para respuestas públicas"""
    id: int
    name: str
    subdomain: str
    logo_url: Optional[HttpUrl] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    description: Optional[str] = None
    timezone: str  # Incluir timezone en respuestas públicas
    is_active: bool

    @field_serializer('logo_url')
    def serialize_logo_url(self, logo_url: Optional[HttpUrl]) -> Optional[str]:
        """Convierte HttpUrl a string para compatibilidad con PostgreSQL"""
        return str(logo_url) if logo_url else None

    class Config:
        from_attributes = True


# === Esquemas para Discovery Público Detallado ===

class GymHoursPublic(BaseModel):
    """Horarios públicos del gimnasio para discovery"""
    day_of_week: int = Field(..., ge=0, le=6, description="Día de la semana (0=Lunes, 6=Domingo)")
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: bool = False

    class Config:
        from_attributes = True


class MembershipPlanPublic(BaseModel):
    """Plan de membresía público para discovery"""
    id: int
    name: str
    description: Optional[str] = None
    price_cents: int
    currency: str
    billing_interval: str
    duration_days: int
    max_billing_cycles: Optional[int] = None
    features: Optional[str] = None
    max_bookings_per_month: Optional[int] = None
    
    # Campo calculado para facilitar el frontend
    price_amount: Optional[float] = None
    
    class Config:
        from_attributes = True


class GymModulePublic(BaseModel):
    """Módulos públicos del gimnasio para discovery"""
    module_name: str
    is_enabled: bool
    
    class Config:
        from_attributes = True


class GymDetailedPublicSchema(BaseModel):
    """Esquema público detallado de gimnasio para discovery completo"""
    # Información básica del gimnasio
    id: int
    name: str
    subdomain: str
    logo_url: Optional[HttpUrl] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    description: Optional[str] = None
    timezone: str
    is_active: bool

    # Información detallada adicional
    gym_hours: List[GymHoursPublic] = []
    membership_plans: List[MembershipPlanPublic] = []
    modules: List[GymModulePublic] = []

    @field_serializer('logo_url')
    def serialize_logo_url(self, logo_url: Optional[HttpUrl]) -> Optional[str]:
        """Convierte HttpUrl a string para compatibilidad con PostgreSQL"""
        return str(logo_url) if logo_url else None

    class Config:
        from_attributes = True