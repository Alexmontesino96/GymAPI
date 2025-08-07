from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from app.models.schedule import ClassParticipationStatus


class ParticipationStatusBase(BaseModel):
    """Schema ultra-ligero para estado de participación del usuario"""
    session_id: int = Field(..., description="ID de la sesión")
    status: ClassParticipationStatus = Field(..., description="Estado de la participación")
    registration_time: datetime = Field(..., description="Tiempo de registro en formato ISO 8601")
    attendance_time: Optional[datetime] = Field(None, description="Tiempo de asistencia (si asistió)")
    cancellation_time: Optional[datetime] = Field(None, description="Tiempo de cancelación (si canceló)")

    model_config = {"from_attributes": True}


class ParticipationStatusResponse(BaseModel):
    """Respuesta del endpoint de estados de participación"""
    participations: List[ParticipationStatusBase] = Field(
        ..., 
        description="Lista de participaciones del usuario"
    )
    total_count: int = Field(..., description="Número total de participaciones encontradas")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "participations": [
                        {
                            "session_id": 123,
                            "status": "registered",
                            "registration_time": "2025-01-15T10:30:00Z",
                            "attendance_time": None,
                            "cancellation_time": None
                        },
                        {
                            "session_id": 124,
                            "status": "attended",
                            "registration_time": "2025-01-14T09:15:00Z",
                            "attendance_time": "2025-01-14T14:00:00Z",
                            "cancellation_time": None
                        }
                    ],
                    "total_count": 2
                }
            ]
        }
    }