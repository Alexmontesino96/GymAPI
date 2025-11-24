"""
Script simple para actualizar alembic_version al merge más reciente.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.DATABASE_URL)

print("Actualizando alembic_version a fd54000bbbcb (merge head)...")

with engine.connect() as conn:
    conn.execute(text("DELETE FROM alembic_version"))
    conn.execute(text("INSERT INTO alembic_version VALUES ('fd54000bbbcb')"))
    conn.commit()
    print("✓ Actualizado exitosamente")
