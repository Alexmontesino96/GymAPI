from sqlalchemy import create_engine, text

def main():
    # URL directa de Supabase
    DB_URL = "postgresql://postgres:Mezjo9-gezrox-guggop@db.ueijlkythlkqadxymzqd.supabase.co:5432/postgres"
    
    try:
        # Crear conexión a la base de datos
        engine = create_engine(DB_URL)
        
        # Conectar y ejecutar consulta
        with engine.connect() as conn:
            try:
                # Verificar estructura de la tabla
                print("Columnas en la tabla class_session:")
                columns_result = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'class_session' ORDER BY ordinal_position"))
                for row in columns_result:
                    print(f"  - {row[0]}: {row[1]}")
                
                print("\nConsultando datos con la columna override_capacity:")
                data_result = conn.execute(text("SELECT id, class_id, trainer_id, override_capacity FROM class_session LIMIT 3"))
                rows = data_result.fetchall()
                if rows:
                    for row in rows:
                        print(f"  ID: {row[0]}, class_id: {row[1]}, trainer_id: {row[2]}, override_capacity: {row[3]}")
                else:
                    print("  No hay datos en la tabla class_session")
                    
            except Exception as e:
                print(f"Error al consultar la columna: {e}")
    except Exception as e:
        print(f"Error de conexión: {e}")

if __name__ == "__main__":
    main() 