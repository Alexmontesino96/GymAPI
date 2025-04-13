"""
Schedule Module - API Endpoints

This module organizes the different components of the gym scheduling system:
- Gym operating hours (regular weekly template and special day exceptions)
- Class definitions and categories
- Class sessions and scheduling
- Member participation and attendance tracking

The schedule system is divided into two main components:
1. Regular Hours (/gym-hours/regular): The weekly template defining standard operating hours 
   for each day of the week (Monday through Sunday)
2. Special Days (/gym-hours/special-days): Exceptions to the regular schedule for specific 
   dates like holidays, special events, or temporary changes

The gym-hours module also provides functionality to:
- Apply regular hours to a date range (/gym-hours/apply-defaults)
- Get effective hours for a specific date (/gym-hours/date/{date})
- Get schedules for a date range (/gym-hours/date-range)

The endpoints are organized in a modular structure with separate files
for each functional area, improving maintainability and separation of concerns.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.schedule import (
    classes,
    sessions,
    gym_hours,
    special_days,
    categories,
    participation
)

router = APIRouter()

# Rutas para clases y sesiones
router.include_router(classes.router, prefix="/classes", tags=["classes"])
router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
router.include_router(participation.router, prefix="/participation", tags=["participation"])

# Rutas para horarios del gimnasio
router.include_router(gym_hours.router, prefix="/gym-hours", tags=["gym-hours"])
router.include_router(special_days.router, prefix="/special-days", tags=["special-days"])

# Rutas para categorías de clases
router.include_router(categories.router, prefix="/categories", tags=["categories"]) 