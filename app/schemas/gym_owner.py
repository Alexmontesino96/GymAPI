"""
Schemas para Registro de Dueños de Gimnasio

Este módulo contiene los schemas Pydantic para el registro de dueños de gimnasios,
incluyendo validaciones de contraseña, email y teléfono.
"""

import re
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, validator
import pytz


class GymOwnerRegistrationRequest(BaseModel):
    """Schema para solicitud de registro de dueño de gimnasio"""

    # Información del dueño
    email: EmailStr = Field(
        ...,
        title="Email del dueño",
        description="Email para login y notificaciones"
    )
    password: str = Field(
        ...,
        title="Contraseña",
        min_length=8,
        max_length=128,
        description="Contraseña con al menos 8 caracteres, 1 mayúscula, 1 minúscula, 1 número"
    )
    first_name: str = Field(..., min_length=2, max_length=50, title="Nombre")
    last_name: str = Field(..., min_length=2, max_length=50, title="Apellido")
    phone: Optional[str] = Field(None, description="Formato internacional: +525512345678")

    # Información del gimnasio
    gym_name: str = Field(
        ...,
        min_length=3,
        max_length=255,
        title="Nombre del gimnasio",
        description="Nombre comercial del gimnasio"
    )
    gym_address: Optional[str] = Field(None, max_length=255, title="Dirección del gimnasio")
    gym_phone: Optional[str] = Field(None, title="Teléfono del gimnasio")
    gym_email: Optional[EmailStr] = Field(None, title="Email de contacto del gimnasio")
    timezone: str = Field(
        default="America/Mexico_City",
        title="Zona horaria",
        description="Zona horaria del gimnasio en formato pytz"
    )

    @validator('password')
    def validate_password_strength(cls, v):
        """Validar complejidad de contraseña"""
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        if not re.search(r'[A-Z]', v):
            raise ValueError("La contraseña debe contener al menos una mayúscula")
        if not re.search(r'[a-z]', v):
            raise ValueError("La contraseña debe contener al menos una minúscula")
        if not re.search(r'\d', v):
            raise ValueError("La contraseña debe contener al menos un número")
        return v

    @validator('phone', 'gym_phone')
    def validate_phone(cls, v):
        """Validar formato de teléfono internacional"""
        if v is None:
            return v
        # Eliminar espacios y guiones para validación
        phone_clean = v.replace(" ", "").replace("-", "")
        # Formato internacional: +[código país][número]
        if not re.match(r'^\+?[1-9]\d{1,14}$', phone_clean):
            raise ValueError("Formato de teléfono inválido. Use formato internacional (ej: +525512345678)")
        return phone_clean

    @validator('timezone')
    def validate_timezone(cls, v):
        """Validar que la zona horaria sea válida"""
        if v not in pytz.all_timezones:
            raise ValueError(f"Zona horaria inválida: {v}. Use un timezone válido de pytz")
        return v

    class Config:
        schema_extra = {
            "example": {
                "email": "owner@gimnasio.com",
                "password": "SecurePass123",
                "first_name": "Juan",
                "last_name": "Pérez",
                "phone": "+525512345678",
                "gym_name": "Fitness Pro México",
                "gym_address": "Av. Reforma 123, CDMX",
                "gym_phone": "+525587654321",
                "gym_email": "contacto@fitnesspro.com",
                "timezone": "America/Mexico_City"
            }
        }


class GymInfo(BaseModel):
    """Información del gimnasio creado"""
    id: int
    name: str
    subdomain: str
    type: str
    timezone: str
    is_active: bool


class UserInfo(BaseModel):
    """Información del usuario creado"""
    id: int
    email: str
    name: str
    role: str


class GymOwnerRegistrationResponse(BaseModel):
    """Respuesta exitosa del registro"""
    success: bool = True
    message: str = "Gimnasio y usuario creados exitosamente"

    gym: GymInfo
    user: UserInfo

    modules_activated: List[str] = Field(
        ...,
        description="Lista de módulos activados automáticamente"
    )
    stripe_setup_required: bool = Field(
        True,
        description="Indica si se requiere configurar Stripe Connect"
    )

    next_steps: List[str] = Field(
        ...,
        description="Próximos pasos recomendados después del registro"
    )

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Gimnasio y usuario creados exitosamente",
                "gym": {
                    "id": 42,
                    "name": "Fitness Pro México",
                    "subdomain": "fitness-pro-mexico",
                    "type": "gym",
                    "timezone": "America/Mexico_City",
                    "is_active": True
                },
                "user": {
                    "id": 123,
                    "email": "owner@gimnasio.com",
                    "name": "Juan Pérez",
                    "role": "ADMIN"
                },
                "modules_activated": [
                    "users",
                    "schedule",
                    "events",
                    "chat",
                    "billing",
                    "health",
                    "nutrition",
                    "surveys",
                    "equipment"
                ],
                "stripe_setup_required": True,
                "next_steps": [
                    "Verificar email haciendo clic en el enlace enviado",
                    "Configurar Stripe Connect para pagos",
                    "Configurar horarios del gimnasio",
                    "Crear clases y horarios",
                    "Agregar primeros miembros"
                ]
            }
        }


class GymOwnerRegistrationError(BaseModel):
    """Schema para errores en el registro"""
    success: bool = False
    message: str
    error_code: str
    details: dict = {}

    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "message": "El email owner@gimnasio.com ya está registrado",
                "error_code": "EMAIL_EXISTS",
                "details": {
                    "email": "owner@gimnasio.com",
                    "gym_name": "Fitness Pro México"
                }
            }
        }
