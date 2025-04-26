from app.db.session import engine
from app.db.base_class import Base
from app.models.gym import Gym
from app.models.user import User
from app.models.event import Event, EventParticipation
from app.models.chat import ChatRoom, ChatMember
import sqlalchemy as sa
from sqlalchemy import inspect

# Verificar si las tablas existen
inspector = inspect(engine)
existing_tables = inspector.get_table_names()

# Crear las tablas en el orden correcto respetando las dependencias
if 'gyms' not in existing_tables:
    print("Creando tabla gyms...")
    Gym.__table__.create(engine, checkfirst=True)

if 'user' not in existing_tables:
    print("Creando tabla user...")
    User.__table__.create(engine, checkfirst=True)

if 'events' not in existing_tables:
    print("Creando tabla events...")
    Event.__table__.create(engine, checkfirst=True)

if 'event_participations' not in existing_tables:
    print("Creando tabla event_participations...")
    EventParticipation.__table__.create(engine, checkfirst=True)

if 'chat_rooms' not in existing_tables:
    print("Creando tabla chat_rooms...")
    ChatRoom.__table__.create(engine, checkfirst=True)

if 'chat_members' not in existing_tables:
    print("Creando tabla chat_members...")
    ChatMember.__table__.create(engine, checkfirst=True)

print('Proceso de creación de tablas completado') 