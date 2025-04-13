from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic.v1 import validator
from app.models.user import UserRole


# Propiedades compartidas
class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = True
    is_superuser: bool = False
    first_name: Optional[str] = None
    last_name: Optional[str] = None
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
    role: UserRole = UserRole.MEMBER


# Propiedades para recibir a través de API al actualizar
class UserUpdate(UserBase):
    pass


# Propiedades adicionales para perfiles
class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    birth_date: Optional[datetime] = None
    height: Optional[float] = Field(None, ge=0)
    weight: Optional[float] = Field(None, ge=0)

    class Config:
        from_attributes = True


# Propiedades compartidas adicionales
class UserInDBBase(UserBase):
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Propiedades para retornar a través de API
class User(UserInDBBase):
    id: int
    email: EmailStr
    auth0_id: Optional[str] = None
    picture: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Propiedades almacenadas en DB
class UserInDB(UserInDBBase):
    auth0_id: Optional[str] = None


# Esquema para cambiar el rol de un usuario
class UserRoleUpdate(BaseModel):
    role: UserRole


# Esquema para búsqueda avanzada de usuarios
class UserSearchParams(BaseModel):
    name_contains: Optional[str] = Field(None, description="Búsqueda parcial en nombre")
    email_contains: Optional[str] = Field(None, description="Búsqueda parcial en email")
    email_domain: Optional[str] = Field(None, description="Dominio de email específico")
    role: Optional[UserRole] = Field(None, description="Filtrar por rol")
    is_active: Optional[bool] = Field(None, description="Filtrar por estado activo")
    created_after: Optional[datetime] = Field(None, description="Creado después de fecha")
    created_before: Optional[datetime] = Field(None, description="Creado antes de fecha")
    skip: int = Field(0, ge=0, description="Registros a omitir (paginación)")
    limit: int = Field(100, ge=1, le=1000, description="Límite de registros (paginación)")


# Modelo para verificar disponibilidad de email
class EmailAvailabilityCheck(BaseModel):
    email: EmailStr
    
    @field_validator('email')
    @classmethod
    def validate_email_domain(cls, v):
        """
        Valida que el dominio del email no sea un dominio desechable conocido.
        Esta es una validación adicional a la que realiza el servicio.
        
        Args:
            v: Email a validar
            
        Returns:
            str: Email validado
            
        Raises:
            ValueError: Si el dominio es desechable
        """
        if isinstance(v, str):
            domain = v.split('@')[-1].lower()
            
            # Lista común de dominios de email desechables/temporales
            common_disposable_domains = {
                'mailinator.com', 'temp-mail.org', 'guerrillamail.com', 'yopmail.com', 
                'tempmail.com', '10minutemail.com', 'throwawaymail.com'
            }
            
            if domain in common_disposable_domains:
                raise ValueError("Los dominios de email temporales o desechables no están permitidos")
        
        return v


# Esquema para perfiles públicos (sin datos sensibles)
class UserPublicProfile(BaseModel):
    """
    Esquema para listar usuarios sin exponer datos sensibles.
    Contiene solo la información básica necesaria para mostrar en la UI.
    """
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    picture: Optional[str] = None
    role: UserRole
    bio: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True


# Esquema para solicitar cambio de email via flujo Auth0
class Auth0EmailChangeRequest(BaseModel):
    new_email: EmailStr


# Esquema para la sincronización desde Auth0 Action
class UserSyncFromAuth0(BaseModel):
    auth0_id: str = Field(..., description="Auth0 User ID (sub)")
    email: EmailStr = Field(..., description="Email actual del usuario en Auth0")
    # Podríamos añadir email_verified si quisiéramos usarlo
    # email_verified: bool

    class Config:
        from_attributes = True # Opcional, pero buena práctica
