#!/usr/bin/env python
"""
Script para crear un nuevo gimnasio (workspace tipo 'gym')

Uso:
    python scripts/create_gym.py --name "CrossFit Downtown" --subdomain "crossfit-downtown" --owner-email "admin@crossfit.com"
"""

import sys
import os
import argparse
from sqlalchemy.orm import Session

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.gym import Gym, GymType
from app.models.user import User
from app.models.user_gym import UserGym, GymRoleType
from app.services.auth0_service import auth0_service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_gym(
    name: str,
    subdomain: str,
    owner_email: str,
    owner_first_name: str,
    owner_last_name: str,
    owner_password: str = None,
    address: str = None,
    phone: str = None,
    timezone: str = "America/Mexico_City",
    db: Session = None
):
    """
    Crea un nuevo gimnasio con su owner.

    Args:
        name: Nombre del gimnasio
        subdomain: Subdominio único (ej: 'crossfit-downtown')
        owner_email: Email del propietario
        owner_first_name: Nombre del propietario
        owner_last_name: Apellido del propietario
        owner_password: Password para Auth0 (opcional, se genera automático)
        address: Dirección física (opcional)
        phone: Teléfono de contacto (opcional)
        timezone: Zona horaria (default: America/Mexico_City)
        db: Sesión de base de datos (opcional)
    """
    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        print("="*70)
        print("🏢 CREANDO NUEVO GIMNASIO")
        print("="*70)
        print()

        # 1. Verificar que el subdomain no exista
        print(f"1️⃣  Verificando disponibilidad del subdomain '{subdomain}'...")
        existing_gym = db.query(Gym).filter(Gym.subdomain == subdomain).first()
        if existing_gym:
            raise ValueError(f"El subdomain '{subdomain}' ya está en uso")
        print("   ✅ Subdomain disponible")

        # 2. Verificar si el usuario ya existe
        print(f"\n2️⃣  Verificando usuario '{owner_email}'...")
        existing_user = db.query(User).filter(User.email == owner_email).first()

        if existing_user:
            print(f"   ℹ️  Usuario ya existe (ID: {existing_user.id})")
            user = existing_user
        else:
            print("   ⚠️  Usuario no existe, creando nuevo usuario...")

            # 3. Crear usuario en Auth0 (si no existe)
            print(f"\n3️⃣  Creando usuario en Auth0...")
            try:
                auth0_user = auth0_service.create_user(
                    email=owner_email,
                    password=owner_password,
                    first_name=owner_first_name,
                    last_name=owner_last_name
                )
                auth0_id = auth0_user['user_id']
                print(f"   ✅ Usuario creado en Auth0: {auth0_id}")
            except Exception as e:
                logger.error(f"Error creando usuario en Auth0: {e}")
                print(f"   ⚠️  No se pudo crear en Auth0, continuando sin auth0_id")
                auth0_id = None

            # 4. Crear usuario en la BD local
            print(f"\n4️⃣  Creando usuario en base de datos...")
            user = User(
                email=owner_email,
                first_name=owner_first_name,
                last_name=owner_last_name,
                auth0_id=auth0_id,
                is_active=True
            )
            db.add(user)
            db.flush()  # Para obtener el ID
            print(f"   ✅ Usuario creado (ID: {user.id})")

        # 5. Crear el gimnasio
        print(f"\n5️⃣  Creando gimnasio '{name}'...")
        gym = Gym(
            name=name,
            subdomain=subdomain,
            type=GymType.gym,
            address=address,
            phone=phone,
            email=owner_email,
            timezone=timezone,
            is_active=True
        )
        db.add(gym)
        db.flush()
        print(f"   ✅ Gimnasio creado (ID: {gym.id})")

        # 6. Asociar usuario como OWNER del gimnasio
        print(f"\n6️⃣  Asociando usuario como OWNER del gimnasio...")
        user_gym = UserGym(
            user_id=user.id,
            gym_id=gym.id,
            role=GymRoleType.OWNER
        )
        db.add(user_gym)
        db.commit()
        print("   ✅ Asociación creada")

        # 7. Resumen
        print("\n" + "="*70)
        print("✅ GIMNASIO CREADO EXITOSAMENTE")
        print("="*70)
        print()
        print("📊 Resumen:")
        print(f"   • Gimnasio ID: {gym.id}")
        print(f"   • Nombre: {gym.name}")
        print(f"   • Subdomain: {gym.subdomain}")
        print(f"   • Tipo: {gym.type.value}")
        print(f"   • URL: https://{gym.subdomain}.gymapi.com")
        print(f"   • Timezone: {gym.timezone}")
        print()
        print(f"👤 Owner:")
        print(f"   • User ID: {user.id}")
        print(f"   • Email: {user.email}")
        print(f"   • Nombre: {user.first_name} {user.last_name}")
        print(f"   • Auth0 ID: {user.auth0_id or 'No creado'}")
        print(f"   • Rol: OWNER")
        print()
        print("🚀 Próximos pasos:")
        print("   1. El owner debe verificar su email en Auth0")
        print("   2. Configurar módulos activos para el gimnasio")
        print("   3. Agregar staff (trainers, admins)")
        print("   4. Agregar miembros")
        print()

        return {
            "gym_id": gym.id,
            "user_id": user.id,
            "subdomain": gym.subdomain,
            "success": True
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error creando gimnasio: {e}", exc_info=True)
        print("\n" + "="*70)
        print("❌ ERROR CREANDO GIMNASIO")
        print("="*70)
        print(f"\n{str(e)}\n")
        return {"success": False, "error": str(e)}

    finally:
        if should_close_db:
            db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Crear un nuevo gimnasio (workspace tipo 'gym')"
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Nombre del gimnasio (ej: 'CrossFit Downtown')"
    )
    parser.add_argument(
        "--subdomain",
        required=True,
        help="Subdomain único (ej: 'crossfit-downtown')"
    )
    parser.add_argument(
        "--owner-email",
        required=True,
        help="Email del propietario"
    )
    parser.add_argument(
        "--owner-first-name",
        required=True,
        help="Nombre del propietario"
    )
    parser.add_argument(
        "--owner-last-name",
        required=True,
        help="Apellido del propietario"
    )
    parser.add_argument(
        "--owner-password",
        help="Password para Auth0 (opcional, se genera automático si no se proporciona)"
    )
    parser.add_argument(
        "--address",
        help="Dirección física del gimnasio"
    )
    parser.add_argument(
        "--phone",
        help="Teléfono de contacto"
    )
    parser.add_argument(
        "--timezone",
        default="America/Mexico_City",
        help="Zona horaria (default: America/Mexico_City)"
    )

    args = parser.parse_args()

    result = create_gym(
        name=args.name,
        subdomain=args.subdomain,
        owner_email=args.owner_email,
        owner_first_name=args.owner_first_name,
        owner_last_name=args.owner_last_name,
        owner_password=args.owner_password,
        address=args.address,
        phone=args.phone,
        timezone=args.timezone
    )

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
