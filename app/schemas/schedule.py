from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime, time
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
    day_of_week: int
    open_time: time
    close_time: time
    is_closed: bool = False

    @validator('day_of_week')
    def validate_day_of_week(cls, v):
        if v < 0 or v > 6:
            raise ValueError('day_of_week must be between 0 and 6')
        return v

    @validator('close_time')
    def validate_close_time(cls, close_time, values):
        open_time = values.get('open_time')
        if open_time and close_time and close_time <= open_time:
            raise ValueError('close_time must be after open_time')
        return close_time


class GymHoursCreate(GymHoursBase):
    pass


class GymHoursUpdate(BaseModel):
    day_of_week: Optional[int] = None
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: Optional[bool] = None


class GymHours(GymHoursBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# GymSpecialHours schemas
class GymSpecialHoursBase(BaseModel):
    date: datetime
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: bool = False
    description: Optional[str] = None

    @validator('close_time')
    def validate_close_time(cls, close_time, values):
        open_time = values.get('open_time')
        if open_time and close_time and close_time <= open_time:
            raise ValueError('close_time must be after open_time')
        return close_time


class GymSpecialHoursCreate(GymSpecialHoursBase):
    pass


class GymSpecialHoursUpdate(BaseModel):
    date: Optional[datetime] = None
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: Optional[bool] = None
    description: Optional[str] = None


class GymSpecialHours(GymSpecialHoursBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None

    class Config:
        from_attributes = True


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
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None

    class Config:
        from_attributes = True


# Class schemas
class ClassBase(BaseModel):
    name: str
    description: Optional[str] = None
    duration: int = Field(..., gt=0)  # Duración en minutos
    max_capacity: int = Field(..., gt=0)
    difficulty_level: ClassDifficultyLevel
    category_id: Optional[int] = None
    category_enum: Optional[ClassCategory] = None
    is_active: bool = True

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


class ClassCreate(ClassBase):
    pass


class ClassUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = Field(None, gt=0)
    max_capacity: Optional[int] = Field(None, gt=0)
    difficulty_level: Optional[ClassDifficultyLevel] = None
    category_id: Optional[int] = None
    category_enum: Optional[ClassCategory] = None
    is_active: Optional[bool] = None


class Class(ClassBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    custom_category: Optional[ClassCategoryCustom] = None

    class Config:
        from_attributes = True


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
    notes: Optional[str] = None
    gym_id: Optional[int] = None  # Hacemos este campo opcional para que pueda ser asignado automáticamente

    @validator('end_time', always=True)
    def set_end_time(cls, end_time, values):
        if end_time:
            return end_time
        
        # Si no se proporciona end_time, calcularlo a partir de start_time y la duración
        # Nota: se necesitaría información adicional desde el modelo Class
        return values.get('start_time')  # Este valor se actualizará en el servicio


class ClassSessionCreate(ClassSessionBase):
    pass


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


class ClassSession(ClassSessionBase):
    id: int
    current_participants: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None

    class Config:
        from_attributes = True


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
    registration_time: datetime
    attendance_time: Optional[datetime] = None
    cancellation_time: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Update forward references
ClassWithSessions.update_forward_refs()
ClassSessionWithParticipations.update_forward_refs() 