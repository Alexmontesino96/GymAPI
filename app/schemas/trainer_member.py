from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from app.models.trainer_member import RelationshipStatus


# Base para relaciones
class TrainerMemberRelationshipBase(BaseModel):
    trainer_id: int
    member_id: int
    status: RelationshipStatus = RelationshipStatus.PENDING
    notes: Optional[str] = None


# Para crear relaciones
class TrainerMemberRelationshipCreate(TrainerMemberRelationshipBase):
    pass


# Para actualizar relaciones
class TrainerMemberRelationshipUpdate(BaseModel):
    status: Optional[RelationshipStatus] = None
    notes: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


# Para respuestas de API
class TrainerMemberRelationship(TrainerMemberRelationshipBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_by: Optional[int] = None

    class Config:
        from_attributes = True


# Para listar entrenadores o miembros asignados
class UserWithRelationship(BaseModel):
    id: int
    full_name: str
    email: str
    picture: Optional[str] = None
    relationship_id: int
    relationship_status: RelationshipStatus
    relationship_start_date: Optional[datetime] = None

    class Config:
        from_attributes = True 