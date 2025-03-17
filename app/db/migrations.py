from sqlalchemy import create_engine, Table, MetaData, Column, Enum, text, inspect, TIMESTAMP
from app.core.config import settings
from app.models.user import UserRole

def run_migrations():
    """Ejecuta las migraciones pendientes en la base de datos."""
    # Conexión a la base de datos usando str explícitamente
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
    metadata = MetaData()
    
    # Verificar si la tabla user existe
    with engine.connect() as conn:
        inspector = inspect(engine)
        if 'user' in inspector.get_table_names():
            columns = inspector.get_columns('user')
            column_names = [column["name"] for column in columns]
            
            # Columnas adicionales que podrían faltar
            missing_columns = {
                'role': "VARCHAR(10) DEFAULT 'member'",
                'phone_number': "VARCHAR(20)",
                'birth_date': "TIMESTAMP WITH TIME ZONE",
                'height': "FLOAT",
                'weight': "FLOAT",
                'bio': "TEXT",
                'goals': "TEXT",
                'health_conditions': "TEXT"
            }
            
            # Añadir columnas faltantes
            for column_name, column_type in missing_columns.items():
                if column_name not in column_names:
                    print(f"Añadiendo columna '{column_name}' a la tabla 'user'...")
                    conn.execute(text(
                        f"ALTER TABLE \"user\" ADD COLUMN {column_name} {column_type}"
                    ))
                    conn.commit()
                    print(f"Columna '{column_name}' añadida correctamente.")
                else:
                    print(f"La columna '{column_name}' ya existe en la tabla 'user'.")
        else:
            print("La tabla 'user' no existe en la base de datos.")

if __name__ == "__main__":
    run_migrations() 