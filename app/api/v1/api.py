from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, trainer_member, events, chat

api_router = APIRouter()

# Incluir rutas específicas
api_router.include_router(auth.router, prefix="/auth", tags=["autenticación"])
api_router.include_router(users.router, prefix="/users", tags=["usuarios"])
api_router.include_router(trainer_member.router, prefix="/trainer-member", tags=["relaciones entrenador-miembro"])
api_router.include_router(events.router, prefix="/events", tags=["eventos"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"]) 