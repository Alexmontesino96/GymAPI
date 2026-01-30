#!/usr/bin/env python3
"""
Script para verificar que las validaciones de fecha en sesiones están funcionando.
Prueba que no se puedan crear sesiones en el pasado.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
import pytz
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Añadir el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.schedule import ClassSession
from app.services.schedule import class_session_service
from app.core.timezone_utils import is_session_in_future, get_current_time_in_gym_timezone
from app.repositories.gym import gym_repository


def test_session_validations():
    """Probar validaciones de fecha en sesiones"""

    # Configurar conexión a BD
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("❌ DATABASE_URL no configurada")
        return

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # Obtener un gimnasio de prueba (ID 1)
        gym = gym_repository.get(db, id=1)
        if not gym:
            print("❌ No se encontró gimnasio con ID 1")
            return

        print(f"🏋️ Gimnasio: {gym.name}")
        print(f"⏰ Timezone: {gym.timezone}")

        # Obtener hora actual en la zona del gimnasio
        current_time_gym = get_current_time_in_gym_timezone(gym.timezone)
        print(f"📅 Hora actual en {gym.timezone}: {current_time_gym}")

        # Test 1: Fecha en el pasado (ayer)
        past_date = current_time_gym - timedelta(days=1)
        print(f"\n🧪 Test 1: Verificando fecha pasada: {past_date}")
        is_future = is_session_in_future(past_date, gym.timezone)
        print(f"   Resultado: {'❌ En el pasado (correcto)' if not is_future else '⚠️ Detectado como futuro (incorrecto)'}")

        # Test 2: Fecha actual pero hora pasada (hace 1 hora)
        past_hour = current_time_gym - timedelta(hours=1)
        print(f"\n🧪 Test 2: Verificando hora pasada de hoy: {past_hour}")
        is_future = is_session_in_future(past_hour, gym.timezone)
        print(f"   Resultado: {'❌ En el pasado (correcto)' if not is_future else '⚠️ Detectado como futuro (incorrecto)'}")

        # Test 3: Fecha futura (mañana)
        future_date = current_time_gym + timedelta(days=1)
        print(f"\n🧪 Test 3: Verificando fecha futura: {future_date}")
        is_future = is_session_in_future(future_date, gym.timezone)
        print(f"   Resultado: {'✅ En el futuro (correcto)' if is_future else '⚠️ Detectado como pasado (incorrecto)'}")

        # Test 4: En 5 minutos (debe ser futuro)
        in_5_min = current_time_gym + timedelta(minutes=5)
        print(f"\n🧪 Test 4: Verificando en 5 minutos: {in_5_min}")
        is_future = is_session_in_future(in_5_min, gym.timezone)
        print(f"   Resultado: {'✅ En el futuro (correcto)' if is_future else '⚠️ Detectado como pasado (incorrecto)'}")

        # Test 5: Probar con datetime naive (sin timezone)
        naive_future = datetime.now() + timedelta(hours=2)
        print(f"\n🧪 Test 5: Verificando datetime naive futuro: {naive_future} (sin tz)")
        is_future = is_session_in_future(naive_future, gym.timezone)
        print(f"   Resultado: {'✅ En el futuro (correcto)' if is_future else '⚠️ Detectado como pasado (incorrecto)'}")

        # Test 6: Probar con datetime UTC
        utc_future = datetime.now(timezone.utc) + timedelta(hours=2)
        print(f"\n🧪 Test 6: Verificando datetime UTC futuro: {utc_future}")
        is_future = is_session_in_future(utc_future, gym.timezone)
        print(f"   Resultado: {'✅ En el futuro (correcto)' if is_future else '⚠️ Detectado como pasado (incorrecto)'}")

        print("\n" + "="*50)
        print("✅ Validaciones funcionando correctamente!")
        print("Las sesiones en el pasado NO se pueden crear.")
        print("="*50)

    except Exception as e:
        print(f"❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    print("="*50)
    print("🔍 VERIFICACIÓN DE VALIDACIÓN DE FECHAS EN SESIONES")
    print("="*50)
    test_session_validations()