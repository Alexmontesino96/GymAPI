# Inicializador del paquete repositories
from app.repositories.base import BaseRepository  # Legacy sync
from app.repositories.async_base import AsyncBaseRepository  # Nuevo async

# Legacy sync repositories (FASE 5: será eliminado)
from app.repositories.user import user_repository
from app.repositories.trainer_member import trainer_member_repository
from app.repositories.event import event_repository, event_participation_repository
from app.repositories.chat import chat_repository
from app.repositories.schedule import (
    gym_hours_repository,
    gym_special_hours_repository,
    class_repository,
    class_session_repository,
    class_participation_repository
)

# FASE 2: Async repositories
from app.repositories.async_user import async_user_repository
from app.repositories.async_gym import async_gym_repository

__all__ = [
    # Base repositories
    "BaseRepository",  # Legacy sync (será eliminado en FASE 5)
    "AsyncBaseRepository",  # Nuevo async
    # Legacy sync repository instances (FASE 5: será eliminado)
    "user_repository",
    "trainer_member_repository",
    "event_repository",
    "event_participation_repository",
    "chat_repository",
    "gym_hours_repository",
    "gym_special_hours_repository",
    "class_repository",
    "class_session_repository",
    "class_participation_repository",
    # FASE 2: Async repository instances
    "async_user_repository",
    "async_gym_repository",
] 