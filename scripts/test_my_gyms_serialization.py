#!/usr/bin/env python
"""Script para verificar la serialización del endpoint /my"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.services.gym import gym_service
from app.models.user import User
from app.schemas.gym import UserGymMembershipSchema
import json

db = SessionLocal()

try:
    # Obtener usuario (asumiendo que existe usuario con email específico)
    user = db.query(User).filter(User.email == "alexmontesino96@icloud.com").first()

    if not user:
        print("❌ Usuario no encontrado")
        sys.exit(1)

    print("=" * 70)
    print("TEST SERIALIZACIÓN /gyms/my")
    print("=" * 70)
    print(f"\n👤 Usuario: {user.email} (ID: {user.id})")

    # Obtener gimnasios usando el servicio
    print(f"\n🔍 Obteniendo gimnasios con gym_service.get_user_gyms()...")
    user_gyms = gym_service.get_user_gyms(db, user_id=user.id)

    print(f"\n📊 Resultado del servicio (raw dict):")
    for idx, gym_dict in enumerate(user_gyms):
        print(f"\n  Gym {idx + 1}:")
        print(f"    ID: {gym_dict['id']}")
        print(f"    Name: {gym_dict['name']}")
        print(f"    Type (raw): {gym_dict.get('type')}")
        print(f"    Type (type): {type(gym_dict.get('type'))}")
        print(f"    Type (repr): {repr(gym_dict.get('type'))}")

    # Intentar serializar con Pydantic
    print(f"\n📦 Serializando con UserGymMembershipSchema...")
    try:
        serialized = [UserGymMembershipSchema.model_validate(gym) for gym in user_gyms]

        print(f"\n✅ Serialización exitosa!")
        for idx, gym_schema in enumerate(serialized):
            print(f"\n  Gym {idx + 1} (serializado):")
            print(f"    ID: {gym_schema.id}")
            print(f"    Name: {gym_schema.name}")
            print(f"    Type: {gym_schema.type}")
            print(f"    Type (value): {gym_schema.type.value if hasattr(gym_schema.type, 'value') else 'NO VALUE'}")

        # Dump to JSON (lo que FastAPI enviará)
        print(f"\n📤 JSON que devolvería FastAPI:")
        json_output = [gym.model_dump() for gym in serialized]
        print(json.dumps(json_output, indent=2, default=str)[:500] + "...")

    except Exception as e:
        print(f"\n❌ Error al serializar: {e}")
        import traceback
        traceback.print_exc()

finally:
    db.close()
