# Importar todos los modelos para que Alembic los detecte
from app.db.base_class import Base  # noqa
from app.models.user import User  # noqa
from app.models.gym import Gym  # noqa
from app.models.user_gym import UserGym  # noqa
from app.models.trainer_member import TrainerMemberRelationship  # noqa
from app.models.event import Event, EventParticipation  # noqa
from app.models.chat import ChatRoom, ChatMember  # noqa
from app.models.schedule import (
    GymHours, 
    GymSpecialHours, 
    ClassCategoryCustom,
    Class, 
    ClassSession, 
    ClassParticipation
)  # noqa
from app.models.notification import DeviceToken  # noqa
# Importar aquí otros modelos que se vayan creando 