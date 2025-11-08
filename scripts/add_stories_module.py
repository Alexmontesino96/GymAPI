#!/usr/bin/env python
"""
Script para agregar el módulo de historias al sistema y activarlo para gimnasios.
"""

import sys
import os
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.module import Module
from app.models.gym_module import GymModule
from app.models.gym import Gym

# Import story models to ensure relationships are properly initialized
from app.models.story import Story, StoryView, StoryReaction, StoryReport, StoryHighlight, StoryHighlightItem


def add_stories_module():
    """
    Agrega el módulo de historias si no existe y lo activa para todos los gimnasios.
    """
    db = SessionLocal()
    try:
        # Verificar si el módulo ya existe
        existing_module = db.execute(
            select(Module).where(Module.code == "stories")
        )
        stories_module = existing_module.scalar_one_or_none()

        if not stories_module:
            # Crear el módulo de historias
            stories_module = Module(
                code="stories",
                name="Historias",
                description="Sistema de historias estilo Instagram para compartir momentos del gimnasio. Las historias expiran después de 24 horas y permiten interacciones como vistas y reacciones.",
                is_premium=False  # Puede cambiar según el modelo de negocio
            )
            db.add(stories_module)
            db.commit()
            print(f"✅ Módulo 'stories' creado exitosamente")
        else:
            print(f"ℹ️  Módulo 'stories' ya existe")

        # Obtener todos los gimnasios activos
        gyms_result = db.execute(
            select(Gym).where(Gym.is_active == True)
        )
        gyms = gyms_result.scalars().all()

        activated_count = 0
        already_active_count = 0

        for gym in gyms:
            # Verificar si el gimnasio ya tiene el módulo activado
            existing_gym_module = db.execute(
                select(GymModule).where(
                    GymModule.gym_id == gym.id,
                    GymModule.module_id == stories_module.id
                )
            )
            gym_module = existing_gym_module.scalar_one_or_none()

            if not gym_module:
                # Activar el módulo para este gimnasio
                gym_module = GymModule(
                    gym_id=gym.id,
                    module_id=stories_module.id,
                    active=True,
                    activated_at=datetime.utcnow()
                )
                db.add(gym_module)
                activated_count += 1
                print(f"  ✅ Módulo activado para gimnasio: {gym.name} (ID: {gym.id})")
            elif not gym_module.active:
                # Reactivar si estaba desactivado
                gym_module.active = True
                gym_module.activated_at = datetime.utcnow()
                gym_module.deactivated_at = None
                activated_count += 1
                print(f"  ✅ Módulo reactivado para gimnasio: {gym.name} (ID: {gym.id})")
            else:
                already_active_count += 1
                print(f"  ℹ️  Módulo ya activo para gimnasio: {gym.name} (ID: {gym.id})")

        db.commit()

        print(f"\n📊 Resumen:")
        print(f"  - Total gimnasios: {len(gyms)}")
        print(f"  - Módulos activados: {activated_count}")
        print(f"  - Ya activos: {already_active_count}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def check_module_status():
    """
    Verifica el estado del módulo de historias.
    """
    db = SessionLocal()
    try:
        # Verificar si el módulo existe
        module_result = db.execute(
            select(Module).where(Module.code == "stories")
        )
        module = module_result.scalar_one_or_none()

        if module:
            print(f"\n📦 Módulo de Historias:")
            print(f"  ID: {module.id}")
            print(f"  Código: {module.code}")
            print(f"  Nombre: {module.name}")
            print(f"  Premium: {'Sí' if module.is_premium else 'No'}")

            # Contar gimnasios con el módulo activo
            active_count_result = db.execute(
                select(GymModule).where(
                    GymModule.module_id == module.id,
                    GymModule.active == True
                )
            )
            active_gyms = active_count_result.scalars().all()

            print(f"  Gimnasios activos: {len(active_gyms)}")
        else:
            print("\n❌ El módulo de historias no existe")
    finally:
        db.close()


def main():
    """
    Función principal del script.
    """
    print("=" * 50)
    print("CONFIGURACIÓN DEL MÓDULO DE HISTORIAS")
    print("=" * 50)

    # Agregar/activar el módulo
    add_stories_module()

    # Verificar estado
    check_module_status()

    print("\n✅ Script completado exitosamente")


if __name__ == "__main__":
    main()