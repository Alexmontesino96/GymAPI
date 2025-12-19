from fastapi import APIRouter

from app.api.v1.endpoints.auth.login import router as login_router
from app.api.v1.endpoints.auth.tokens import router as tokens_router
from app.api.v1.endpoints.auth.user_info import router as user_info_router
from app.api.v1.endpoints.auth.admin import router as admin_router
from app.api.v1.endpoints.auth.trainer_registration import router as trainer_registration_router
from app.api.v1.endpoints.auth.gym_owner_registration import router as gym_owner_registration_router

# Main router for the entire auth module
router = APIRouter()

# Include routes from submodules with appropriate tags for API documentation
router.include_router(login_router, prefix="", tags=["auth-login"])
router.include_router(tokens_router, prefix="", tags=["auth-tokens"])
router.include_router(user_info_router, prefix="", tags=["auth-user"])
router.include_router(admin_router, prefix="", tags=["auth-admin"])
router.include_router(trainer_registration_router, prefix="", tags=["auth-registration"])
router.include_router(gym_owner_registration_router, prefix="", tags=["auth-registration"]) 