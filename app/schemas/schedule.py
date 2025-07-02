from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator, model_validator, conint
from datetime import datetime, time, date
from enum import Enum

from app.models.schedule import (
    DayOfWeek, 
    ClassDifficultyLevel, 
    ClassCategory,
    ClassSessionStatus,
    ClassParticipationStatus
)

# GymHours schemas
class GymHoursBase(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: bool = False

    @model_validator(mode='after')
    def check_times_when_not_closed(self):
        # Cuando el gimnasio está cerrado, no deberían enviarse horarios
        if self.is_closed:
            if self.open_time is not None or self.close_time is not None:
                raise ValueError(
                    'Cuando is_closed es True no se debe especificar open_time ni close_time'
                )
        else:
            # El gimnasio está abierto, validar que existan horarios coherentes
            if self.open_time is None:
                raise ValueError('open_time es obligatorio cuando is_closed es False')
            if self.close_time is None:
                raise ValueError('close_time es obligatorio cuando is_closed es False')
            if self.close_time <= self.open_time:
                raise ValueError('close_time debe ser posterior a open_time cuando no está cerrado')
        return self


class GymHoursCreate(GymHoursBase):
    gym_id: int


class GymHoursUpdate(BaseModel):
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: Optional[bool] = None

    @model_validator(mode='after')
    def check_updated_times(self):
        if self.open_time and self.close_time and self.close_time <= self.open_time:
            raise ValueError('close_time must be after open_time')
        return self


class GymHours(GymHoursBase):
    id: int
    gym_id: int

    model_config = {"from_attributes": True}


# GymSpecialHours schemas
class GymSpecialHoursBase(BaseModel):
    date: date
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: bool = False
    description: Optional[str] = Field(None, max_length=255)

    @model_validator(mode='after')
    def check_special_times_when_not_closed(self):
        # Validación para días especiales
        if self.is_closed:
            # Si está marcado como cerrado, no debe haber horarios
            if self.open_time is not None or self.close_time is not None:
                raise ValueError('Cuando is_closed es True no se debe especificar open_time ni close_time')
        else:
            # Si el día no está cerrado, los horarios son obligatorios y deben ser coherentes
            if self.open_time is None:
                raise ValueError('open_time es obligatorio cuando is_closed es False')
            if self.close_time is None:
                raise ValueError('close_time es obligatorio cuando is_closed es False')
            if self.close_time <= self.open_time:
                raise ValueError('close_time debe ser posterior a open_time cuando no está cerrado')
        return self

    @validator('open_time', 'close_time', pre=True)
    def parse_time_string(cls, value):
        """Validar y convertir strings de tiempo en formato HH:MM a objetos time"""
        if value is None:
            return None
        
        # Si ya es un objeto time, simplemente devolverlo
        if isinstance(value, time):
            return value
            
        # Si es una cadena, intentar convertirla desde formato HH:MM
        if isinstance(value, str):
            try:
                hour, minute = map(int, value.split(':'))
                return time(hour=hour, minute=minute)
            except (ValueError, TypeError):
                raise ValueError('El formato de tiempo debe ser HH:MM (ejemplo: 09:30)')
                
        return value


class GymSpecialHoursCreate(GymSpecialHoursBase):
    # El gym_id se obtiene automáticamente del header X-Gym-ID
    # y se asigna en el endpoint
    pass


class GymSpecialHoursUpdate(BaseModel):
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: Optional[bool] = None
    description: Optional[str] = Field(None, max_length=255)

    @model_validator(mode='after')
    def check_updated_special_times(self):
        if self.open_time and self.close_time and self.close_time <= self.open_time:
            raise ValueError('close_time must be after open_time')
        return self
        
    @validator('open_time', 'close_time', pre=True)
    def parse_time_string(cls, value):
        """Validar y convertir strings de tiempo en formato HH:MM a objetos time"""
        if value is None:
            return None
        
        # Si ya es un objeto time, simplemente devolverlo
        if isinstance(value, time):
            return value
            
        # Si es una cadena, intentar convertirla desde formato HH:MM
        if isinstance(value, str):
            try:
                hour, minute = map(int, value.split(':'))
                return time(hour=hour, minute=minute)
            except (ValueError, TypeError):
                raise ValueError('El formato de tiempo debe ser HH:MM (ejemplo: 09:30)')
                
        return value


class GymSpecialHours(GymSpecialHoursBase):
    id: int
    gym_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None

    model_config = {"from_attributes": True}


# Class Category Custom schemas
class ClassCategoryCustomBase(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    is_active: bool = True


class ClassCategoryCustomCreate(ClassCategoryCustomBase):
    pass


class ClassCategoryCustomUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None


class ClassCategoryCustom(ClassCategoryCustomBase):
    id: int
    gym_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None

    model_config = {"from_attributes": True}


# Class schemas
class ClassBaseInput(BaseModel):
    """Modelo base para entrada de datos de clase (sin gym_id)"""
    name: str
    description: Optional[str] = None
    duration: int = Field(..., gt=0)  # Duración en minutos
    max_capacity: int = Field(..., gt=0)
    difficulty_level: ClassDifficultyLevel
    category_id: Optional[int] = None
    category_enum: Optional[ClassCategory] = None
    category: Optional[ClassCategory] = None  # Campo adicional para compatibilidad
    is_active: bool = True

    @validator('category', pre=True, always=False)
    def set_category_enum(cls, v, values):
        """Si se proporciona 'category', usarlo como 'category_enum'"""
        if v is not None and 'category_enum' not in values:
            values['category_enum'] = v
        return None  # No guardar este campo
    
    @validator('category_enum', pre=True)
    def normalize_category_enum(cls, v):
        """Normaliza el valor del enum a minúsculas para permitir enviar valores en mayúsculas"""
        if v is not None and isinstance(v, str):
            # Convertir a minúsculas para que 'YOGA' se convierta a 'yoga'
            v_lower = v.lower()
            # Verificar si el valor en minúsculas es válido para el enum
            try:
                return ClassCategory(v_lower)
            except ValueError:
                # Si no es un valor válido, se dejará que la validación de Pydantic genere el error
                pass
        return v
    
    @validator('category_id', 'category_enum')
    def validate_category(cls, v, values, **kwargs):
        # Versión actualizada que no confía en field.name
        field_name = kwargs.get('field', {})
        if hasattr(field_name, 'name'):
            field_name = field_name.name
        else:
            # Si no podemos acceder a field.name, inferimos el nombre basándonos en el valor
            # Si v es un Int o None y estamos en un validador aplicado a category_id/category_enum, 
            # entonces podemos inferir qué campo estamos validando
            if isinstance(v, int) or (v is None and 'category_enum' in values):
                field_name = 'category_id'
            else:
                field_name = 'category_enum'
                
        other_field = 'category_enum' if field_name == 'category_id' else 'category_id'
        
        # Si ambos son None, usar OTHER como valor predeterminado para category_enum
        if (field_name == 'category_enum' and v is None and 
            'category_id' in values and values['category_id'] is None):
            return ClassCategory.OTHER
        
        return v


class ClassBase(ClassBaseInput):
    """Modelo base con gym_id para la base de datos y respuestas"""
    gym_id: int  # Se mantiene para las respuestas


class ClassCreate(ClassBaseInput):
    """Modelo para crear clases (sin gym_id requerido)"""
    pass


class ClassUpdate(BaseModel):
    """Modelo para actualizar clases (campos opcionales)"""
    name: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = Field(None, gt=0)
    max_capacity: Optional[int] = Field(None, gt=0)
    difficulty_level: Optional[ClassDifficultyLevel] = None
    category_id: Optional[int] = None
    category_enum: Optional[ClassCategory] = None
    category: Optional[ClassCategory] = None  # Campo adicional para compatibilidad
    is_active: Optional[bool] = None
    # No incluir gym_id en update para evitar cambios de gimnasio

    @validator('category', pre=True, always=False)
    def set_category_enum(cls, v, values):
        """Si se proporciona 'category', usarlo como 'category_enum'"""
        if v is not None and 'category_enum' not in values:
            values['category_enum'] = v
        return None  # No guardar este campo
        
    @validator('category_enum', pre=True)
    def normalize_category_enum(cls, v):
        """Normaliza el valor del enum a minúsculas para permitir enviar valores en mayúsculas"""
        if v is not None and isinstance(v, str):
            # Convertir a minúsculas para que 'YOGA' se convierta a 'yoga'
            v_lower = v.lower()
            # Verificar si el valor en minúsculas es válido para el enum
            try:
                return ClassCategory(v_lower)
            except ValueError:
                # Si no es un valor válido, se dejará que la validación de Pydantic genere el error
                pass
        return v


class Class(ClassBase):
    """Modelo completo con todos los campos para respuestas"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    custom_category: Optional[ClassCategoryCustom] = None

    model_config = {"from_attributes": True}


class ClassWithSessions(Class):
    sessions: List["ClassSession"] = []


# ClassSession schemas
class ClassSessionBase(BaseModel):
    class_id: int
    trainer_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    room: Optional[str] = None
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None
    status: ClassSessionStatus = ClassSessionStatus.SCHEDULED
    override_capacity: Optional[int] = Field(None, gt=0, description="Capacidad específica para esta sesión, si es diferente a la de la clase")
    notes: Optional[str] = None

    @validator('end_time', pre=True)
    def default_end_time(cls, end_time):
        """Mantiene end_time opcional; el servicio lo calculará si falta."""
        return end_time


class ClassSessionCreate(ClassSessionBase):
    gym_id: Optional[int] = None


class ClassSessionUpdate(BaseModel):
    class_id: Optional[int] = None
    trainer_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    room: Optional[str] = None
    is_recurring: Optional[bool] = None
    recurrence_pattern: Optional[str] = None
    status: Optional[ClassSessionStatus] = None
    current_participants: Optional[int] = None
    notes: Optional[str] = None
    override_capacity: Optional[int] = Field(None, gt=0, description="Capacidad específica para esta sesión, si es diferente a la de la clase")


class ClassSession(ClassSessionBase):
    id: int
    gym_id: int  # Mantener en el modelo de respuesta
    current_participants: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    override_capacity: Optional[int] = None

    model_config = {"from_attributes": True}


class ClassSessionWithParticipations(ClassSession):
    participations: List["ClassParticipation"] = []
    class_details: Optional[Class] = None


# ClassParticipation schemas
class ClassParticipationBase(BaseModel):
    session_id: int
    member_id: int
    status: ClassParticipationStatus = ClassParticipationStatus.REGISTERED


class ClassParticipationCreate(ClassParticipationBase):
    pass


class ClassParticipationUpdate(BaseModel):
    status: Optional[ClassParticipationStatus] = None
    attendance_time: Optional[datetime] = None
    cancellation_time: Optional[datetime] = None
    cancellation_reason: Optional[str] = None


class ClassParticipation(ClassParticipationBase):
    id: int
    gym_id: int  # Mantener en el modelo de respuesta
    registration_time: datetime
    attendance_time: Optional[datetime] = None
    cancellation_time: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# Update forward references
ClassWithSessions.model_rebuild()
ClassSessionWithParticipations.model_rebuild()

# --- Añadido para historial de asistencia ---
class ParticipationWithSessionInfo(BaseModel):
    id: int
    session_id: int
    member_id: int
    status: ClassParticipationStatus  # Usar Enum para mejor tipo
    registration_time: datetime
    attendance_time: Optional[datetime] = None
    cancellation_time: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    session_info: ClassSession  # Usar el esquema ClassSession existente
    class_info: Class  # Usar el esquema Class existente

    model_config = {"from_attributes": True}

# Helper function to format participation with session info
# Nota: Esta función debería residir lógicamente en el servicio o endpoint,
# no en el archivo de esquemas, pero la mantenemos aquí por ahora si la necesitas.
def format_participation_with_session_info(participation, session, gym_class):
    return ParticipationWithSessionInfo(
        id=participation.id,
        session_id=participation.session_id,
        member_id=participation.member_id,
        status=participation.status,
        registration_time=participation.registration_time,
        attendance_time=participation.attendance_time,
        cancellation_time=participation.cancellation_time,
        cancellation_reason=participation.cancellation_reason,
        session_info=ClassSession.model_validate(session.__dict__), # Convertir modelo DB a Pydantic
        class_info=Class.model_validate(gym_class.__dict__) # Convertir modelo DB a Pydantic
    )

# ApplyDefaultsRequest
class ApplyDefaultsRequest(BaseModel):
    start_date: date
    end_date: date
    overwrite_existing: bool = Field(False, description="Si es True, sobrescribe las excepciones manuales existentes en el rango.")

    @model_validator(mode='after')
    def check_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self

# DailyScheduleResponse
class DailyScheduleResponse(BaseModel):
    date: date
    day_of_week: int
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: bool
    is_special: bool = Field(..., description="Indica si el horario proviene de GymSpecialHours (True) o de la plantilla GymHours (False)")
    description: Optional[str] = Field(None, description="Descripción si es un día especial")
    source_id: Optional[int] = Field(None, description="ID del registro GymSpecialHours o GymHours de donde se obtuvo el horario")

# --- NUEVO esquema para listar sesiones con su clase ---
class SessionWithClass(BaseModel):
    session: ClassSession
    class_info: Class

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "session": {
                        "id": 813,
                        "class_id": 143,
                        "trainer_id": 8,
                        "start_time": "2025-07-04T14:00:00Z",
                        "end_time": "2025-07-04T15:00:00Z",
                        "status": "scheduled",
                        "gym_id": 4,
                        "current_participants": 0
                    },
                    "class_info": {
                        "id": 143,
                        "name": "Striking",
                        "description": "Striking Precision",
                        "duration": 60,
                        "max_capacity": 20,
                        "difficulty_level": "intermediate",
                        "gym_id": 4
                    }
                }
            ]
        }
    } 