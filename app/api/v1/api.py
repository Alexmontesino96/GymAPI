from fastapi import APIRouter

from app.api.v1.endpoints import users, trainer_member, events, chat
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.schedule import router as schedule_router

api_router = APIRouter()

# Incluir rutas específicas
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(trainer_member.router, prefix="/trainer-member", tags=["trainer-member"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(schedule_router, prefix="/schedule", tags=["schedule"]) 