from fastapi import APIRouter

# Import routers from modules
from app.api.v1.endpoints import users, gyms, trainer_member, chat, events, worker, attendance, memberships, payment_pages
from app.api.v1.endpoints.notification import router as notification_router
from app.api.v1.endpoints.webhooks.stream_webhooks import router as stream_webhooks_router
from app.api.v1.endpoints.nutrition import router as nutrition_router
from app.api.v1.endpoints.stripe_connect import router as stripe_connect_router
from app.api.v1.endpoints.user_dashboard import router as user_dashboard_router
from app.api.v1.endpoints.surveys import router as surveys_router
from app.api.v1.endpoints.context import router as context_router
from app.api.v1.endpoints.stories import router as stories_router

# Import modular packages directly
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.schedule import router as schedule_router
from app.api.v1.endpoints.modules import router as modules_router

api_router = APIRouter()

# Authentication module
api_router.include_router(auth_router, prefix="/auth")

# Users module
api_router.include_router(users.router, prefix="/users")

# User Dashboard module  
api_router.include_router(user_dashboard_router, prefix="/users", tags=["user-dashboard"])

# Events module
api_router.include_router(events.router, prefix="/events", tags=["events"])

# Schedule module (timetables and classes)
api_router.include_router(schedule_router, prefix="/schedule")

# Gyms module
api_router.include_router(gyms.router, prefix="/gyms", tags=["gyms"])

# Trainer-Member relationships module
api_router.include_router(trainer_member.router, prefix="/relationships", tags=["relationships"])

# Chat module
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])

# Worker endpoints
api_router.include_router(worker.router,tags=["worker"])

# Notifications module
api_router.include_router(notification_router, prefix="/notifications", tags=["notifications"])

# Modules configuration
api_router.include_router(modules_router, prefix="/modules", tags=["modules"])

# Stream webhooks
api_router.include_router(stream_webhooks_router, prefix="/webhooks", tags=["webhooks"])

# Attendance module
api_router.include_router(attendance.router, prefix="/attendance", tags=["attendance"])

# Memberships module
api_router.include_router(memberships.router, prefix="/memberships", tags=["memberships"])

# Payment pages (success/cancel)
api_router.include_router(payment_pages.router, tags=["payment-pages"])

# Nutrition module
api_router.include_router(nutrition_router, prefix="/nutrition", tags=["nutrition"])

# Stripe Connect module
api_router.include_router(stripe_connect_router, prefix="/stripe-connect", tags=["stripe-connect"])

# Surveys module
api_router.include_router(surveys_router, prefix="/surveys", tags=["surveys"])

# Context module (workspace info for adaptive UI)
api_router.include_router(context_router, prefix="/context", tags=["context"])

# Stories module
api_router.include_router(stories_router, prefix="/stories", tags=["stories"])
