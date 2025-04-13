"""
Common imports and dependencies for the schedule module.

This module centralizes shared imports and dependencies used across
all schedule-related endpoints, including authentication, database access,
models, services, and schemas. Importing from this module helps maintain
consistency and reduces duplication across the schedule API endpoints.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, Security, status
from sqlalchemy.orm import Session

from app.core.auth0_fastapi import auth, get_current_user, Auth0User
from app.core.tenant import get_current_gym, verify_gym_access, verify_trainer_role, verify_admin_role
from app.db.session import get_db
from app.models.gym import Gym
from app.models.schedule import (
    DayOfWeek,
    ClassDifficultyLevel,
    ClassCategory,
    ClassSessionStatus,
    ClassParticipationStatus
)
from app.services.schedule import (
    gym_hours_service,
    gym_special_hours_service,
    class_service,
    class_session_service,
    class_participation_service
)
from app.services.user import user_service
from app.schemas.schedule import (
    GymHours, GymHoursCreate, GymHoursUpdate,
    GymSpecialHours, GymSpecialHoursCreate, GymSpecialHoursUpdate,
    ClassBaseInput, ClassBase, Class, ClassCreate, ClassUpdate, ClassWithSessions,
    ClassSession, ClassSessionCreate, ClassSessionUpdate, ClassSessionWithParticipations,
    ClassParticipation, ClassParticipationCreate, ClassParticipationUpdate
)
from app.repositories.schedule import (
    class_repository,
    class_session_repository,
    class_participation_repository
) 