from fastapi import APIRouter

# Importar los routers desde los módulos
from app.api.v1.endpoints import users, gyms, trainer_member, chat, events, worker
from app.api.v1.endpoints.notification import router as notification_router

# Importar los paquetes modulares directamente
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.schedule import router as schedule_router

api_router = APIRouter()

# Módulo de autenticación
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# Módulo de usuarios
api_router.include_router(users.router, prefix="/users", tags=["users"])

# Módulo de eventos
api_router.include_router(events.router, prefix="/events", tags=["events"])

# Módulo de programación (horarios y clases)
api_router.include_router(schedule_router, prefix="/schedule", tags=["schedule"]) 

# Módulo de relaciones entrenador-miembro
api_router.include_router(trainer_member.router, prefix="/relationships", tags=["relationships"])

# Módulo de chat
api_router.include_router(chat.router, prefix="/chat", tags=["chat"]) 

# Módulo de gimnasios (tenants)
api_router.include_router(gyms.router, prefix="/gyms", tags=["gyms"]) 

# Módulo de notificaciones
api_router.include_router(notification_router, prefix="/notifications", tags=["notifications"])

# Módulo de worker (nuevo)
api_router.include_router(worker.router, tags=["worker"]) 