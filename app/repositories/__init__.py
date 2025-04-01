# Inicializador del paquete repositories 
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