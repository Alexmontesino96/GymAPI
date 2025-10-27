#!/usr/bin/env python
"""Script para verificar los tipos de gimnasios en BD vs lo que devuelve el schema"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.gym import Gym
from app.schemas.gym import UserGymMembershipSchema

db = SessionLocal()

try:
    # Obtener gimnasio ID 5
    gym = db.query(Gym).filter(Gym.id == 5).first()

    if gym:
        print("=" * 70)
        print("GIMNASIO ID 5 - DEBUG")
        print("=" * 70)
        print(f"\n📊 Datos del modelo ORM (Gym):")
        print(f"   ID: {gym.id}")
        print(f"   Nombre: {gym.name}")
        print(f"   Subdomain: {gym.subdomain}")
        print(f"   Type (raw): {gym.type}")
        print(f"   Type (repr): {repr(gym.type)}")
        print(f"   Type (type): {type(gym.type)}")
        print(f"   Type (value): {gym.type.value if hasattr(gym.type, 'value') else 'NO VALUE ATTR'}")
        print(f"   Type (name): {gym.type.name if hasattr(gym.type, 'name') else 'NO NAME ATTR'}")

        print(f"\n🔍 Verificación desde BD directa:")
        from sqlalchemy import text
        result = db.execute(text("SELECT type FROM gyms WHERE id = 5")).fetchone()
        print(f"   Type desde SQL: {result[0] if result else 'NO RESULT'}")

        # Intentar crear un schema
        print(f"\n📦 Serialización con Schema:")
        try:
            from pydantic import EmailStr
            from app.models.user_gym import GymRoleType
            from app.schemas.gym import Gym as GymSchema

            # Crear schema directo
            gym_schema = GymSchema.model_validate(gym)
            print(f"   GymSchema.type: {gym_schema.type}")
            print(f"   GymSchema.type (value): {gym_schema.type.value if hasattr(gym_schema.type, 'value') else 'NO VALUE'}")

            # Dump a dict
            gym_dict = gym_schema.model_dump()
            print(f"   model_dump()['type']: {gym_dict.get('type')}")

            # Dump a JSON
            gym_json = gym_schema.model_dump_json()
            print(f"   model_dump_json(): {gym_json[:200]}...")

        except Exception as e:
            print(f"   ERROR: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ No se encontró gimnasio con ID 5")

finally:
    db.close()
