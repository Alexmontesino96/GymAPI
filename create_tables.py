from app.db.session import engine
from app.models.event import Event, EventParticipation
import sqlalchemy as sa

# Crear las tablas de eventos si no existen
Event.__table__.create(engine, checkfirst=True)
EventParticipation.__table__.create(engine, checkfirst=True)
print('Tablas creadas correctamente') 