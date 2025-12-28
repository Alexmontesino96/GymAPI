#!/usr/bin/env python
"""
Script para habilitar el módulo activity_feed para un gimnasio específico.

Uso:
    python scripts/enable_activity_feed_module.py --gym-id 4
    python scripts/enable_activity_feed_module.py --all  # Habilitar para todos los gimnasios
"""

import argparse
import sys
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.module import Module
from app.models.gym import Gym
from app.models.gym_module import GymModule


def enable_activity_feed_for_gym(db, gym_id: int):
    """
    Habilita el módulo activity_feed para un gimnasio específico.
    """
    try:
        # Verificar que el gimnasio existe
        gym = db.query(Gym).filter_by(id=gym_id).first()
        if not gym:
            print(f"❌ Gimnasio con ID {gym_id} no existe")
            return False

        # Obtener el módulo activity_feed
        module = db.query(Module).filter_by(code='activity_feed').first()

        if not module:
            print("❌ Módulo 'activity_feed' no existe en la base de datos")
            print("   Creando módulo...")

            # Crear el módulo si no existe
            module = Module(
                code='activity_feed',
                name='Activity Feed',
                description='Feed de actividades anónimo con estadísticas en tiempo real',
                is_premium=False,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(module)
            db.flush()
            print(f"✅ Módulo 'activity_feed' creado con ID {module.id}")

        # Verificar si ya existe la relación
        gym_module = db.query(GymModule).filter_by(
            gym_id=gym_id,
            module_id=module.id
        ).first()

        if gym_module:
            if gym_module.is_active:
                print(f"ℹ️  Módulo ya está activo para gimnasio {gym_id} ({gym.name})")
                return True
            else:
                # Activar el módulo
                gym_module.is_active = True
                gym_module.updated_at = datetime.utcnow()
                print(f"✅ Módulo activado para gimnasio {gym_id} ({gym.name})")
        else:
            # Crear la relación
            gym_module = GymModule(
                gym_id=gym_id,
                module_id=module.id,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(gym_module)
            print(f"✅ Módulo habilitado para gimnasio {gym_id} ({gym.name})")

        db.commit()
        return True

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        db.rollback()
        return False


def enable_for_all_gyms(db):
    """
    Habilita el módulo activity_feed para todos los gimnasios.
    """
    gyms = db.query(Gym).filter_by(is_active=True).all()
    success_count = 0

    print(f"\n📊 Habilitando activity_feed para {len(gyms)} gimnasios...")
    print("-" * 50)

    for gym in gyms:
        if enable_activity_feed_for_gym(db, gym.id):
            success_count += 1

    print("-" * 50)
    print(f"\n✅ Completado: {success_count}/{len(gyms)} gimnasios actualizados")


def verify_module_status(db, gym_id: int = None):
    """
    Verifica el estado del módulo activity_feed.
    """
    print("\n📊 Estado del módulo activity_feed:")
    print("-" * 50)

    module = db.query(Module).filter_by(code='activity_feed').first()

    if not module:
        print("❌ El módulo 'activity_feed' no existe")
        return

    print(f"✅ Módulo encontrado:")
    print(f"   ID: {module.id}")
    print(f"   Nombre: {module.name}")
    print(f"   Premium: {'Sí' if module.is_premium else 'No'}")
    print(f"   Activo: {'Sí' if module.is_active else 'No'}")

    if gym_id:
        # Verificar para un gimnasio específico
        gym_module = db.query(GymModule).filter_by(
            gym_id=gym_id,
            module_id=module.id
        ).first()

        gym = db.query(Gym).filter_by(id=gym_id).first()
        gym_name = gym.name if gym else 'Desconocido'

        print(f"\n🏢 Estado para gimnasio {gym_id} ({gym_name}):")
        if gym_module:
            print(f"   Estado: {'ACTIVO ✅' if gym_module.is_active else 'INACTIVO ❌'}")
            print(f"   Creado: {gym_module.created_at}")
            print(f"   Actualizado: {gym_module.updated_at}")
        else:
            print("   Estado: NO CONFIGURADO ⚠️")
    else:
        # Mostrar estado para todos los gimnasios
        gym_modules = db.query(GymModule).filter_by(module_id=module.id).all()

        print(f"\n📊 Gimnasios con el módulo:")
        active_count = 0
        for gm in gym_modules:
            gym = db.query(Gym).filter_by(id=gm.gym_id).first()
            status = "✅" if gm.is_active else "❌"
            print(f"   Gym {gm.gym_id} ({gym.name if gym else 'Unknown'}): {status}")
            if gm.is_active:
                active_count += 1

        print(f"\nTotal: {active_count}/{len(gym_modules)} activos")


def main():
    parser = argparse.ArgumentParser(
        description='Habilitar módulo activity_feed para gimnasios'
    )
    parser.add_argument(
        '--gym-id',
        type=int,
        help='ID del gimnasio para habilitar el módulo'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Habilitar para todos los gimnasios'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Solo verificar el estado actual'
    )

    args = parser.parse_args()

    # Crear sesión de base de datos
    db = SessionLocal()

    try:
        if args.verify:
            # Solo verificar estado
            verify_module_status(db, args.gym_id)

        elif args.all:
            # Habilitar para todos
            enable_for_all_gyms(db)
            verify_module_status(db)

        elif args.gym_id:
            # Habilitar para un gimnasio específico
            enable_activity_feed_for_gym(db, args.gym_id)
            verify_module_status(db, args.gym_id)

        else:
            # Sin argumentos, mostrar ayuda
            parser.print_help()
            print("\nEjemplos de uso:")
            print("  python scripts/enable_activity_feed_module.py --gym-id 4")
            print("  python scripts/enable_activity_feed_module.py --all")
            print("  python scripts/enable_activity_feed_module.py --verify --gym-id 4")

    finally:
        db.close()


if __name__ == "__main__":
    main()