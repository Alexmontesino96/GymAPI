#!/usr/bin/env python
"""
Script para corregir los totales diarios de los planes nutricionales.

Este script recalcula los totales (calorías, proteínas, carbos, grasas)
de cada DailyNutritionPlan sumando los valores de sus comidas.

Útil para corregir planes creados antes del fix que no calculaban estos totales.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, selectinload
from app.models.nutrition import NutritionPlan, DailyNutritionPlan, Meal
from app.core.config import get_settings
import logging
from datetime import datetime
from typing import Tuple

# Obtener configuración
settings = get_settings()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'fix_nutrition_totals_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def calculate_daily_totals(meals: list) -> Tuple[float, float, float, float]:
    """
    Calcula los totales nutricionales de un día sumando las comidas.

    Returns:
        Tuple de (calorías, proteína_g, carbos_g, grasa_g)
    """
    total_calories = 0.0
    total_protein = 0.0
    total_carbs = 0.0
    total_fat = 0.0

    for meal in meals:
        total_calories += meal.calories or 0
        total_protein += meal.protein_g or 0
        total_carbs += meal.carbs_g or 0
        total_fat += meal.fat_g or 0

    return total_calories, total_protein, total_carbs, total_fat


def fix_nutrition_daily_totals(dry_run: bool = False):
    """
    Corrige los totales diarios de todos los planes nutricionales.

    Args:
        dry_run: Si es True, solo muestra lo que haría sin modificar la BD
    """
    # Crear conexión a la base de datos
    engine = create_engine(settings.DATABASE_URL)

    with Session(engine) as session:
        logger.info("🔍 Iniciando corrección de totales diarios...")

        # Obtener todos los planes nutricionales con sus días y comidas
        plans = session.execute(
            select(NutritionPlan)
            .options(
                selectinload(NutritionPlan.daily_plans)
                .selectinload(DailyNutritionPlan.meals)
            )
        ).scalars().all()

        logger.info(f"📊 Encontrados {len(plans)} planes nutricionales")

        total_plans = 0
        total_days_fixed = 0
        total_days_already_ok = 0

        for plan in plans:
            plan_has_changes = False
            logger.info(f"\n{'='*60}")
            logger.info(f"📋 Plan ID: {plan.id} - '{plan.title}'")
            logger.info(f"   Creador: {plan.creator_id}, Gimnasio: {plan.gym_id}")
            logger.info(f"   Días en el plan: {len(plan.daily_plans)}")

            for daily_plan in plan.daily_plans:
                # Calcular los totales reales sumando las comidas
                real_calories, real_protein, real_carbs, real_fat = calculate_daily_totals(daily_plan.meals)

                # Comparar con los valores actuales
                current_calories = daily_plan.total_calories or 0
                current_protein = daily_plan.total_protein_g or 0
                current_carbs = daily_plan.total_carbs_g or 0
                current_fat = daily_plan.total_fat_g or 0

                # Verificar si hay diferencias significativas (más de 0.1 para evitar problemas de flotantes)
                needs_update = (
                    abs(current_calories - real_calories) > 0.1 or
                    abs(current_protein - real_protein) > 0.1 or
                    abs(current_carbs - real_carbs) > 0.1 or
                    abs(current_fat - real_fat) > 0.1
                )

                if needs_update:
                    logger.info(f"   📅 Día {daily_plan.day_number}: NECESITA CORRECCIÓN")
                    logger.info(f"      Comidas en el día: {len(daily_plan.meals)}")

                    # Mostrar detalles de cada comida
                    for meal in daily_plan.meals:
                        logger.debug(f"        - {meal.name}: {meal.calories} cal, "
                                   f"P:{meal.protein_g}g, C:{meal.carbs_g}g, F:{meal.fat_g}g")

                    logger.info(f"      Totales actuales  -> Cal: {current_calories:.1f}, "
                              f"P: {current_protein:.1f}g, C: {current_carbs:.1f}g, F: {current_fat:.1f}g")
                    logger.info(f"      Totales correctos -> Cal: {real_calories:.1f}, "
                              f"P: {real_protein:.1f}g, C: {real_carbs:.1f}g, F: {real_fat:.1f}g")

                    if not dry_run:
                        # Actualizar los totales
                        daily_plan.total_calories = real_calories
                        daily_plan.total_protein_g = real_protein
                        daily_plan.total_carbs_g = real_carbs
                        daily_plan.total_fat_g = real_fat
                        logger.info(f"      ✅ Totales actualizados")
                    else:
                        logger.info(f"      ⚠️  DRY RUN - No se actualizó")

                    total_days_fixed += 1
                    plan_has_changes = True
                else:
                    logger.debug(f"   📅 Día {daily_plan.day_number}: Ya tiene totales correctos")
                    total_days_already_ok += 1

            if plan_has_changes:
                total_plans += 1

        # Hacer commit si no es dry run
        if not dry_run and total_days_fixed > 0:
            session.commit()
            logger.info(f"\n✅ Cambios guardados en la base de datos")

        # Resumen final
        logger.info(f"\n{'='*60}")
        logger.info("📊 RESUMEN DE LA CORRECCIÓN:")
        logger.info(f"   Total de planes procesados: {len(plans)}")
        logger.info(f"   Planes con correcciones: {total_plans}")
        logger.info(f"   Días corregidos: {total_days_fixed}")
        logger.info(f"   Días ya correctos: {total_days_already_ok}")

        if dry_run:
            logger.info("\n⚠️  MODO DRY RUN - No se realizaron cambios en la BD")
            logger.info("    Para aplicar los cambios, ejecuta sin --dry-run")


def main():
    """Función principal del script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Corrige los totales diarios de los planes nutricionales"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ejecutar en modo simulación sin modificar la BD"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Mostrar información detallada de debug"
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        logger.info("🚀 Iniciando script de corrección de totales nutricionales")
        logger.info(f"   Modo: {'DRY RUN' if args.dry_run else 'APLICAR CAMBIOS'}")
        logger.info(f"   Debug: {'Activado' if args.debug else 'Desactivado'}")

        fix_nutrition_daily_totals(dry_run=args.dry_run)

        logger.info("\n✨ Script completado exitosamente")

    except Exception as e:
        logger.error(f"\n❌ Error ejecutando el script: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()