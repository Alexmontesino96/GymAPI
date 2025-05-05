from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

# Schemas para módulos
class ModuleBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    is_premium: bool = False

class ModuleCreate(ModuleBase):
    pass

class ModuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_premium: Optional[bool] = None

class Module(ModuleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

# Schemas para la relación gym-module
class GymModuleBase(BaseModel):
    module_id: int
    active: bool = True

class GymModuleCreate(GymModuleBase):
    gym_id: int

class GymModuleUpdate(BaseModel):
    active: Optional[bool] = None

class GymModule(GymModuleBase):
    gym_id: int
    activated_at: datetime
    deactivated_at: Optional[datetime] = None
    module: Module

    class Config:
        orm_mode = True

# Schema para devolver al frontend
class ModuleStatus(BaseModel):
    code: str
    name: str
    active: bool
    is_premium: bool

class GymModuleList(BaseModel):
    modules: List[ModuleStatus]
