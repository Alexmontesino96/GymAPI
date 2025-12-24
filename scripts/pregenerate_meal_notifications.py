#!/usr/bin/env python
"""
Script para pre-generar notificaciones de todos los meals existentes.

Este script genera y cachea notificaciones para todos los meals activos en el sistema,
reduciendo el costo de generación durante la operación normal.

Uso:
    python scripts/pregenerate_meal_notifications.py

    Opciones:
    --gym-id: Pre-generar solo para un gym específico
    --dry-run: Mostrar qué se haría sin ejecutar
    --force: Regenerar incluso si ya existe en cache
"""

import sys
import argparse
import asyncio
from pathlib import Path
from sqlalchemy import and_

# Agregar el directorio raíz al path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from app.db.session import SessionLocal
from app.models.nutrition import Meal, NutritionPlan, DailyNutritionPlan
from app.services.meal_notification_cache import get_meal_notification_cache
from app.db.redis_client import get_redis_client


def print_section(title: str):
    """Imprime sección con formato."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def check_cache_exists(meal_id: int, gym_tone: str = "motivational") -> bool:
    """Verifica si ya existe notificación en cache para un meal."""
    try:
        redis_client = await get_redis_client()
        if not redis_client:
            return False

        cache_key = f"meal:{meal_id}:notification:{gym_tone}"
        exists = await redis_client.exists(cache_key)
        return bool(exists)
    except Exception:
        return False


async def pregenerate_all_meals(
    gym_id: int = None,
    dry_run: bool = False,
    force: bool = False
):
    """
    Pre-genera notificaciones para todos los meals activos.

    Args:
        gym_id: Solo pre-generar para un gym específico
        dry_run: Mostrar qué se haría sin ejecutar
        force: Regenerar incluso si ya existe en cache
    """
    db = SessionLocal()
    try:
        print_section("PRE-GENERACIÓN DE NOTIFICACIONES DE MEALS")

        # Obtener meals activos
        query = db.query(Meal).join(
            DailyNutritionPlan,
            Meal.daily_plan_id == DailyNutritionPlan.id
        ).join(
            NutritionPlan,
            DailyNutritionPlan.nutrition_plan_id == NutritionPlan.id
        ).filter(
            NutritionPlan.is_active == True
        )

        if gym_id:
            query = query.filter(NutritionPlan.gym_id == gym_id)

        meals = query.all()
        total_meals = len(meals)

        print(f"\n📊 Estadísticas:")
        print(f"  Total meals a procesar: {total_meals}")
        if gym_id:
            print(f"  Filtrado por gym_id: {gym_id}")
        print(f"  Modo: {'DRY RUN (simulación)' if dry_run else 'EJECUCIÓN REAL'}")
        print(f"  Forzar regeneración: {'SÍ' if force else 'NO'}")

        if dry_run:
            print("\n⚠️  DRY RUN MODE - No se ejecutarán cambios reales")

        if total_meals == 0:
            print("\n❌ No se encontraron meals para procesar")
            return

        # Obtener servicio de cache
        meal_cache_service = get_meal_notification_cache()

        # Estadísticas
        stats = {
            "processed": 0,
            "generated": 0,
            "cached": 0,
            "errors": 0
        }

        print("\n🔄 Procesando meals...")
        print("-" * 80)

        for idx, meal in enumerate(meals, 1):
            try:
                # Obtener plan nutricional
                daily_plan = db.query(DailyNutritionPlan).filter(
                    DailyNutritionPlan.id == meal.daily_plan_id
                ).first()

                plan = db.query(NutritionPlan).filter(
                    NutritionPlan.id == daily_plan.nutrition_plan_id
                ).first() if daily_plan else None

                # Verificar si ya existe en cache
                exists_in_cache = await check_cache_exists(meal.id)

                if exists_in_cache and not force:
                    print(f"[{idx}/{total_meals}] ⏭️  Meal {meal.id} ({meal.name}): YA EN CACHE - skip")
                    stats["cached"] += 1
                    stats["processed"] += 1
                    continue

                if dry_run:
                    print(f"[{idx}/{total_meals}] 🔍 Meal {meal.id} ({meal.name}): SE GENERARÍA")
                    stats["processed"] += 1
                    continue

                # Generar notificación
                notification = await meal_cache_service.get_or_generate_notification(
                    meal_id=meal.id,
                    meal=meal,
                    plan=plan,
                    gym_tone="motivational"
                )

                print(f"[{idx}/{total_meals}] ✅ Meal {meal.id} ({meal.name}):")
                print(f"    Title: {notification['title']}")
                print(f"    Message: {notification['message'][:60]}...")

                stats["generated"] += 1
                stats["processed"] += 1

            except Exception as e:
                print(f"[{idx}/{total_meals}] ❌ Error en meal {meal.id}: {str(e)}")
                stats["errors"] += 1
                stats["processed"] += 1

        # Mostrar resultados finales
        print_section("RESUMEN")

        print(f"\n📊 Resultados:")
        print(f"  Meals procesados: {stats['processed']}/{total_meals}")
        print(f"  Nuevas generadas: {stats['generated']}")
        print(f"  Ya en cache: {stats['cached']}")
        print(f"  Errores: {stats['errors']}")

        if not dry_run and stats['generated'] > 0:
            # Estimar costo
            cost_per_generation = 0.0001  # $0.0001 por generación
            total_cost = stats['generated'] * cost_per_generation

            print(f"\n💰 Costo estimado:")
            print(f"  Generaciones: {stats['generated']}")
            print(f"  Costo total: ${total_cost:.4f}")

        print("\n✅ Pre-generación completada exitosamente")

    except Exception as e:
        print(f"\n❌ Error durante la pre-generación: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        db.close()


async def pregenerate_single_meal(meal_id: int, force: bool = False):
    """
    Pre-genera notificación para un meal específico.

    Args:
        meal_id: ID del meal
        force: Regenerar incluso si ya existe en cache
    """
    db = SessionLocal()
    try:
        print_section(f"PRE-GENERACIÓN PARA MEAL {meal_id}")

        # Obtener meal
        meal = db.query(Meal).filter(Meal.id == meal_id).first()

        if not meal:
            print(f"\n❌ Meal {meal_id} no encontrado")
            return

        # Obtener plan
        daily_plan = db.query(DailyNutritionPlan).filter(
            DailyNutritionPlan.id == meal.daily_plan_id
        ).first()

        plan = db.query(NutritionPlan).filter(
            NutritionPlan.id == daily_plan.nutrition_plan_id
        ).first() if daily_plan else None

        # Verificar cache
        exists_in_cache = await check_cache_exists(meal.id)

        if exists_in_cache and not force:
            print(f"\n⚠️  Meal {meal_id} ya existe en cache")
            print("   Usa --force para regenerar")
            return

        # Generar
        meal_cache_service = get_meal_notification_cache()

        notification = await meal_cache_service.get_or_generate_notification(
            meal_id=meal.id,
            meal=meal,
            plan=plan,
            gym_tone="motivational"
        )

        print(f"\n✅ Notificación generada para meal {meal_id}:")
        print(f"  Nombre: {meal.name}")
        print(f"  Tipo: {meal.meal_type}")
        print(f"  Title: {notification['title']}")
        print(f"  Message: {notification['message']}")
        print(f"  Emoji: {notification['emoji']}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        db.close()


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="Pre-genera notificaciones para meals existentes"
    )

    parser.add_argument(
        "--gym-id",
        type=int,
        help="Solo pre-generar para un gym específico"
    )

    parser.add_argument(
        "--meal-id",
        type=int,
        help="Pre-generar solo para un meal específico"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular sin ejecutar cambios reales"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerar incluso si ya existe en cache"
    )

    args = parser.parse_args()

    # Ejecutar
    if args.meal_id:
        asyncio.run(pregenerate_single_meal(args.meal_id, args.force))
    else:
        asyncio.run(pregenerate_all_meals(args.gym_id, args.dry_run, args.force))


if __name__ == "__main__":
    main()
