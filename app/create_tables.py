from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.db.session import engine
from app.models.user import User
from app.models.trainer_member import TrainerMemberRelationship
from app.models.event import Event, EventParticipation


def create_tables():
    """Crear todas las tablas en la base de datos si no existen"""
    Base.metadata.create_all(bind=engine)
    print("Tablas creadas exitosamente.")


if __name__ == "__main__":
    create_tables() 