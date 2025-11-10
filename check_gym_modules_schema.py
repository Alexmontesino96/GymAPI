"""
Script para verificar la estructura de la tabla gym_modules.
"""

from sqlalchemy import create_engine, text, inspect
from app.core.config import get_settings

def main():
    settings = get_settings()
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

    with engine.connect() as connection:
        # Obtener columnas de gym_modules
        inspector = inspect(engine)
        columns = inspector.get_columns('gym_modules')

        print("Estructura de la tabla gym_modules:")
        print("=" * 60)
        for col in columns:
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            default = f"DEFAULT {col.get('default', 'N/A')}" if col.get('default') else ""
            print(f"{col['name']:20} {str(col['type']):20} {nullable:10} {default}")

        print()
        print("Nombres de columnas:", [col['name'] for col in columns])

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
