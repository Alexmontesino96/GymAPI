# Importar todos los modelos para que Alembic los detecte
from app.db.base_class import Base  # noqa
from app.models.user import User  # noqa
from app.models.trainer_member import TrainerMemberRelationship  # noqa
from app.models.event import Event, EventParticipation  # noqa
# Importar aquí otros modelos que se vayan creando 