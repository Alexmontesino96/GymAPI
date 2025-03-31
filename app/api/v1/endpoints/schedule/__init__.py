"""
Schedule Module - API Endpoints

This module organizes the different components of the gym scheduling system:
- Gym operating hours (regular and special days)
- Class definitions and categories
- Class sessions and scheduling
- Member participation and attendance tracking

The endpoints are organized in a modular structure with separate files
for each functional area, improving maintainability and separation of concerns.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.schedule.gym_hours import router as gym_hours_router
from app.api.v1.endpoints.schedule.special_days import router as special_days_router
from app.api.v1.endpoints.schedule.classes import router as classes_router
from app.api.v1.endpoints.schedule.sessions import router as sessions_router
from app.api.v1.endpoints.schedule.participation import router as participation_router

router = APIRouter()

# Include routes from submodules with appropriate tags for API documentation
router.include_router(gym_hours_router, prefix="", tags=["gym-hours"])
router.include_router(special_days_router, prefix="", tags=["special-days"])
router.include_router(classes_router, prefix="", tags=["classes"])
router.include_router(sessions_router, prefix="", tags=["sessions"])
router.include_router(participation_router, prefix="", tags=["participation"]) 