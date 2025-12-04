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
from app.repositories.async_event import async_event_repository
from app.repositories.async_event_participation import async_event_participation_repository
from app.repositories.async_trainer_member import async_trainer_member_repository
from app.repositories.async_chat import async_chat_repository
from app.repositories.async_schedule import (
    async_gym_hours_repository,
    async_gym_special_hours_repository,
    async_class_category_repository,
    async_class_repository,
    async_class_session_repository,
    async_class_participation_repository
)
from app.repositories.async_notification import async_notification_repository
from app.repositories.async_post import async_post_repository
from app.repositories.async_survey import async_survey_repository
from app.repositories.async_feed_ranking import async_feed_ranking_repository

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
    "async_event_repository",
    "async_event_participation_repository",
    "async_trainer_member_repository",
    "async_chat_repository",
    "async_gym_hours_repository",
    "async_gym_special_hours_repository",
    "async_class_category_repository",
    "async_class_repository",
    "async_class_session_repository",
    "async_class_participation_repository",
    "async_notification_repository",
    "async_post_repository",
    "async_survey_repository",
    "async_feed_ranking_repository",
] 