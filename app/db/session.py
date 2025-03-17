from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Crear motor de base de datos
engine = create_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    echo=False,
    pool_pre_ping=True,  # Verifica la conexión antes de usarla
)

# Crear clase de sesión
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Dependencia para obtener la sesión de DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 