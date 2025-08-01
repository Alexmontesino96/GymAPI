#!/usr/bin/env python3
"""
Script para crear un backup de las tablas principales de la base de datos.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import json

# Agregar el directorio raíz al PATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from app.core.config import get_settings
settings = get_settings()
from app.db.session import SessionLocal
from sqlalchemy import text
import json


def backup_table_data(db, table_name, backup_dir):
    """Backup de datos de una tabla específica usando SQL directo."""
    try:
        logger.info(f"Respaldando tabla {table_name}...")
        
        # Ejecutar consulta SQL directa
        result = db.execute(text(f"SELECT * FROM public.{table_name}"))
        
        # Obtener nombres de columnas
        columns = result.keys()
        
        # Convertir a lista de diccionarios
        data = []
        for row in result:
            record_dict = {}
            for i, column in enumerate(columns):
                value = row[i]
                # Convertir datetime a string
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                # Convertir otros tipos no serializables
                elif value is not None and not isinstance(value, (str, int, float, bool, list, dict)):
                    value = str(value)
                record_dict[column] = value
            data.append(record_dict)
        
        # Guardar en archivo JSON
        filename = backup_dir / f"{table_name}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Tabla {table_name}: {len(data)} registros respaldados")
        return len(data)
        
    except Exception as e:
        logger.error(f"❌ Error respaldando tabla {table_name}: {e}")
        return 0


def main():
    """Función principal del script."""
    try:
        # Crear directorio de backup con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path(f"backups/backup_{timestamp}")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"=== Iniciando backup de base de datos ===")
        logger.info(f"Directorio de backup: {backup_dir}")
        
        db = SessionLocal()
        
        # Tablas a respaldar (las más importantes para la migración)
        tables_to_backup = [
            ("user", "usuarios"),
            ("user_gyms", "relaciones usuario-gimnasio"),
            ("gyms", "gimnasios"),
            ("chat_rooms", "salas de chat"),
            ("chat_members", "miembros de chat"),
            ("events", "eventos")
        ]
        
        total_records = 0
        
        for table_name, description in tables_to_backup:
            records = backup_table_data(db, table_name, backup_dir)
            total_records += records
        
        # Crear archivo de información del backup
        info_file = backup_dir / "backup_info.json"
        info_data = {
            "timestamp": timestamp,
            "total_records": total_records,
            "database_url": settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else "local",
            "tables_backed_up": [table_name for table_name, _ in tables_to_backup]
        }
        
        with open(info_file, 'w') as f:
            json.dump(info_data, f, indent=2)
        
        logger.info(f"\n✅ Backup completado exitosamente!")
        logger.info(f"Total de registros respaldados: {total_records}")
        logger.info(f"Backup guardado en: {backup_dir}")
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"Error fatal durante el backup: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)