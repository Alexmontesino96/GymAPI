from fastapi import APIRouter

# Import routers from modules
from app.api.v1.endpoints import users, gyms, trainer_member, chat, events, worker
from app.api.v1.endpoints.notification import router as notification_router

# Import modular packages directly
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.schedule import router as schedule_router
from app.api.v1.endpoints.modules import router as modules_router

api_router = APIRouter()

# Authentication module
api_router.include_router(auth_router, prefix="/auth")

# Users module
api_router.include_router(users.router, prefix="/users")

# Events module
api_router.include_router(events.router, prefix="/events", tags=["events"])

# Schedule module (timetables and classes)
api_router.include_router(schedule_router, prefix="/schedule") 

# Trainer-member relationships module
api_router.include_router(trainer_member.router, prefix="/relationships", tags=["relationships"])

# Chat module
api_router.include_router(chat.router, prefix="/chat", tags=["chat"]) 

# Gyms module (tenants)
api_router.include_router(gyms.router, prefix="/gyms", tags=["gyms"]) 

# Notifications module
api_router.include_router(notification_router, prefix="/notifications", tags=["notifications"])

# Worker module (new)
api_router.include_router(worker.router, tags=["worker"]) 

# Modules module
api_router.include_router(modules_router, prefix="/modules", tags=["modules"])
