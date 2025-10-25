"""
Schemas para Registro y Gestión de Entrenadores Personales
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, validator
import re


class TrainerRegistrationRequest(BaseModel):
    """Schema para solicitud de registro de entrenador personal"""

    # Información básica del entrenador
    email: EmailStr = Field(
        ...,
        title="Email del entrenador",
        description="Email que se usará para login y contacto"
    )
    first_name: str = Field(
        ...,
        title="Nombre",
        min_length=2,
        max_length=50,
        description="Nombre del entrenador"
    )
    last_name: str = Field(
        ...,
        title="Apellido",
        min_length=2,
        max_length=50,
        description="Apellido del entrenador"
    )
    phone: Optional[str] = Field(
        None,
        title="Teléfono",
        description="Teléfono de contacto (formato: +525512345678)"
    )

    # Información profesional
    specialties: Optional[List[str]] = Field(
        default=["Fitness General"],
        title="Especialidades",
        description="Lista de especialidades del entrenador",
        max_items=10
    )
    certifications: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        title="Certificaciones",
        description="Lista de certificaciones con formato: {'name': 'NASM-CPT', 'year': 2020}"
    )

    # Configuración del workspace
    timezone: str = Field(
        default="America/Mexico_City",
        title="Zona horaria",
        description="Zona horaria del workspace (formato pytz)"
    )
    max_clients: Optional[int] = Field(
        default=30,
        title="Máximo de clientes",
        ge=1,
        le=200,
        description="Límite de clientes simultáneos"
    )

    # Bio y descripción
    bio: Optional[str] = Field(
        None,
        title="Biografía",
        max_length=500,
        description="Descripción del entrenador y su enfoque"
    )

    @validator('phone')
    def validate_phone(cls, v):
        """Validar formato de teléfono"""
        if v is None:
            return v

        # Eliminar espacios y guiones
        phone_clean = v.replace(" ", "").replace("-", "")

        # Validar formato internacional
        if not re.match(r'^\+?[1-9]\d{1,14}$', phone_clean):
            raise ValueError("Formato de teléfono inválido. Use formato internacional: +525512345678")

        return phone_clean

    @validator('specialties')
    def validate_specialties(cls, v):
        """Validar especialidades"""
        if not v or len(v) == 0:
            return ["Fitness General"]

        # Validar longitud de cada especialidad
        for specialty in v:
            if len(specialty) < 2 or len(specialty) > 50:
                raise ValueError(f"Especialidad '{specialty}' debe tener entre 2 y 50 caracteres")

        return v

    @validator('certifications')
    def validate_certifications(cls, v):
        """Validar estructura de certificaciones"""
        if v is None:
            return []

        validated = []
        for cert in v:
            if not isinstance(cert, dict):
                raise ValueError("Cada certificación debe ser un diccionario")

            if 'name' not in cert:
                raise ValueError("Certificación debe incluir 'name'")

            # Validar año si está presente
            if 'year' in cert:
                year = cert['year']
                if not isinstance(year, int) or year < 1990 or year > 2030:
                    raise ValueError(f"Año {year} inválido. Debe estar entre 1990 y 2030")

            validated.append({
                'name': cert['name'],
                'year': cert.get('year'),
                'institution': cert.get('institution'),
                'credential_id': cert.get('credential_id')
            })

        return validated


class WorkspaceInfo(BaseModel):
    """Información del workspace creado"""
    id: int
    name: str
    subdomain: str
    type: str
    email: str
    timezone: str
    specialties: Optional[List[str]] = None
    max_clients: Optional[int] = None


class UserInfo(BaseModel):
    """Información del usuario creado"""
    id: int
    email: str
    name: str
    role: str


class TrainerRegistrationResponse(BaseModel):
    """Respuesta exitosa del registro de entrenador"""

    success: bool = True
    message: str = "Espacio de trabajo creado exitosamente"

    # Información del workspace y usuario
    workspace: WorkspaceInfo
    user: UserInfo

    # Información de configuración
    modules_activated: List[str] = Field(
        ...,
        title="Módulos activados",
        description="Lista de módulos activados en el workspace"
    )
    payment_plans: List[str] = Field(
        default=[],
        title="Planes de pago",
        description="Planes de pago (se crean manualmente por el entrenador)"
    )

    # Stripe onboarding (si está configurado)
    stripe_onboarding_url: Optional[str] = Field(
        None,
        title="URL de Stripe",
        description="URL para completar onboarding de Stripe Connect"
    )

    # Próximos pasos
    next_steps: List[str] = Field(
        ...,
        title="Próximos pasos",
        description="Acciones recomendadas para completar la configuración"
    )

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Espacio de trabajo creado exitosamente",
                "workspace": {
                    "id": 1,
                    "name": "Entrenamiento Personal Juan Pérez",
                    "subdomain": "juan-perez",
                    "type": "personal_trainer",
                    "email": "juan@trainer.com",
                    "timezone": "America/Mexico_City",
                    "specialties": ["CrossFit", "Nutrición"],
                    "max_clients": 30
                },
                "user": {
                    "id": 1,
                    "email": "juan@trainer.com",
                    "name": "Juan Pérez",
                    "role": "TRAINER"
                },
                "modules_activated": [
                    "users", "chat", "health", "nutrition",
                    "billing", "appointments", "progress", "surveys"
                ],
                "payment_plans": [],
                "stripe_onboarding_url": "https://connect.stripe.com/setup/...",
                "next_steps": [
                    "Completar onboarding de Stripe para recibir pagos",
                    "Completar configuración de perfil",
                    "Crear planes de pago personalizados",
                    "Agregar primeros clientes",
                    "Configurar horario de disponibilidad"
                ]
            }
        }


class TrainerRegistrationError(BaseModel):
    """Respuesta de error en el registro"""
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "message": "El email ya está registrado",
                "error_code": "EMAIL_EXISTS",
                "details": {
                    "email": "juan@trainer.com",
                    "existing_workspace_id": 5
                }
            }
        }


class TrainerProfileUpdate(BaseModel):
    """Schema para actualizar perfil del entrenador"""
    first_name: Optional[str] = Field(None, min_length=2, max_length=50)
    last_name: Optional[str] = Field(None, min_length=2, max_length=50)
    phone: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    specialties: Optional[List[str]] = None
    certifications: Optional[List[Dict[str, Any]]] = None
    max_clients: Optional[int] = Field(None, ge=1, le=200)
    photo_url: Optional[str] = None

    @validator('phone')
    def validate_phone(cls, v):
        """Validar formato de teléfono"""
        if v is None:
            return v
        phone_clean = v.replace(" ", "").replace("-", "")
        if not re.match(r'^\+?[1-9]\d{1,14}$', phone_clean):
            raise ValueError("Formato de teléfono inválido")
        return phone_clean