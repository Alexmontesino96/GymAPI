#!/usr/bin/env python
"""
Script para crear los módulos esenciales del sistema.
"""

import sys
import os

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar solo lo necesario para evitar errores de dependencias
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings

# Crear engine y session directamente sin async
settings = get_settings()
engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def setup_essential_modules():
    """
    Crea todos los módulos esenciales si no existen.
    """
    db = SessionLocal()

    # Definir todos los módulos esenciales
    essential_modules = [
        {
            "code": "users",
            "name": "Gestión de Usuarios",
            "description": "Gestión de miembros, entrenadores y usuarios del gimnasio",
            "is_premium": False
        },
        {
            "code": "schedule",
            "name": "Clases y Horarios",
            "description": "Sistema de clases grupales y gestión de horarios",
            "is_premium": False
        },
        {
            "code": "events",
            "name": "Eventos del Gimnasio",
            "description": "Creación y gestión de eventos especiales",
            "is_premium": False
        },
        {
            "code": "chat",
            "name": "Mensajería",
            "description": "Sistema de chat en tiempo real con Stream",
            "is_premium": False
        },
        {
            "code": "billing",
            "name": "Pagos y Facturación",
            "description": "Gestión de pagos, suscripciones y facturación con Stripe",
            "is_premium": False
        },
        {
            "code": "health",
            "name": "Tracking de Salud",
            "description": "Seguimiento de medidas corporales y métricas de salud",
            "is_premium": False
        },
        {
            "code": "nutrition",
            "name": "Planes Nutricionales",
            "description": "Análisis nutricional con IA y planes de alimentación",
            "is_premium": True
        },
        {
            "code": "surveys",
            "name": "Encuestas y Feedback",
            "description": "Sistema de encuestas para recopilar feedback de miembros",
            "is_premium": False
        },
        {
            "code": "equipment",
            "name": "Gestión de Equipos",
            "description": "Control de equipamiento y mantenimiento",
            "is_premium": False
        },
        {
            "code": "appointments",
            "name": "Agenda de Citas",
            "description": "Sistema de agendamiento para entrenadores personales",
            "is_premium": False
        },
        {
            "code": "progress",
            "name": "Progreso de Clientes",
            "description": "Tracking de progreso y logros de clientes",
            "is_premium": False
        },
        {
            "code": "classes",
            "name": "Clases Grupales",
            "description": "Gestión de clases grupales y capacidad",
            "is_premium": False
        },
        {
            "code": "stories",
            "name": "Historias",
            "description": "Historias estilo Instagram (24h)",
            "is_premium": False
        },
        {
            "code": "posts",
            "name": "Publicaciones",
            "description": "Feed social del gimnasio",
            "is_premium": False
        },
        {
            "code": "attendance",
            "name": "Asistencia",
            "description": "Control de asistencia de miembros",
            "is_premium": False
        }
    ]

    try:
        created_count = 0
        existing_count = 0

        for module_data in essential_modules:
            # Verificar si el módulo ya existe usando SQL directo
            result = db.execute(
                text("SELECT id FROM modules WHERE code = :code"),
                {"code": module_data["code"]}
            )
            existing = result.fetchone()

            if not existing:
                # Crear el módulo con SQL directo
                db.execute(
                    text("""
                        INSERT INTO modules (code, name, description, is_premium, created_at, updated_at)
                        VALUES (:code, :name, :description, :is_premium, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """),
                    module_data
                )
                created_count += 1
                print(f"✅ Módulo '{module_data['code']}' creado")
            else:
                existing_count += 1
                print(f"ℹ️  Módulo '{module_data['code']}' ya existe")

        db.commit()

        print(f"\n📊 Resumen:")
        print(f"  - Módulos creados: {created_count}")
        print(f"  - Ya existentes: {existing_count}")
        print(f"  - Total: {len(essential_modules)}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def list_all_modules():
    """
    Lista todos los módulos existentes.
    """
    db = SessionLocal()
    try:
        result = db.execute(
            text("SELECT code, name, is_premium FROM modules ORDER BY code")
        )
        modules = result.fetchall()

        print(f"\n📦 Módulos en el sistema ({len(modules)}):")
        print("-" * 80)
        print(f"{'Código':<20} {'Nombre':<30} {'Premium':<10}")
        print("-" * 80)

        for module in modules:
            premium = "Sí" if module[2] else "No"
            print(f"{module[0]:<20} {module[1]:<30} {premium:<10}")

    finally:
        db.close()


def main():
    """
    Función principal del script.
    """
    print("=" * 80)
    print("CONFIGURACIÓN DE MÓDULOS ESENCIALES")
    print("=" * 80)

    # Crear módulos faltantes
    setup_essential_modules()

    # Listar todos los módulos
    list_all_modules()

    print("\n✅ Script completado exitosamente")


if __name__ == "__main__":
    main()
