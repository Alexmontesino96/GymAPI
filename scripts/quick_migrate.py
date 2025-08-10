#!/usr/bin/env python3
"""
Script rápido para aplicar migraciones usando alembic upgrade head.

Este es un script más simple que simplemente ejecuta alembic upgrade head
con la configuración actual.

Uso:
    python scripts/quick_migrate.py
    
Variables de entorno requeridas:
    DATABASE_URL - URL de conexión a la base de datos
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Verificar que estamos en el directorio correcto
project_root = Path(__file__).parent.parent
os.chdir(project_root)

if not os.path.exists('alembic.ini'):
    print("❌ No se encontró alembic.ini. Asegúrate de ejecutar desde el directorio raíz.")
    sys.exit(1)

# Verificar DATABASE_URL
if not os.getenv('DATABASE_URL'):
    print("❌ Variable de entorno DATABASE_URL no configurada")
    sys.exit(1)

print("🚀 Aplicando migraciones con alembic upgrade head...")

try:
    # Ejecutar alembic upgrade head
    result = subprocess.run(['alembic', 'upgrade', 'head'], 
                          capture_output=True, text=True, check=True)
    
    print("✅ Migraciones aplicadas exitosamente")
    print(result.stdout)
    
    if result.stderr:
        print("Advertencias/Info:")
        print(result.stderr)
        
except subprocess.CalledProcessError as e:
    print(f"❌ Error al aplicar migraciones:")
    print(f"Código de salida: {e.returncode}")
    print(f"stdout: {e.stdout}")
    print(f"stderr: {e.stderr}")
    sys.exit(1)
except FileNotFoundError:
    print("❌ Alembic no está instalado o no está en el PATH")
    sys.exit(1)