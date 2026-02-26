"""
Servicio de limpieza y archivado automático para planes nutricionales.

FASE 3: Archivado Automático Robusto
- Background job ejecutado diariamente a las 2 AM
- Archiva planes LIVE terminados automáticamente
- Crea copias ARCHIVED reutilizables
"""

from datetime import datetime, timedelta
from typing import List
import logging

from sqlalchemy.orm import Session

from app.models.nutrition import (
    NutritionPlan, DailyNutritionPlan, Meal, MealIngredient,
    PlanType
)

logger = logging.getLogger(__name__)


class NutritionCleanupService:
    """Servicio para limpieza y archivado automático de planes nutricionales."""

    @staticmethod
    def archive_finished_live_plans(db: Session) -> int:
        """
        Archivar planes LIVE que ya terminaron.

        Se ejecuta diariamente a las 2 AM via APScheduler.

        Flujo:
        1. Buscar planes LIVE con is_live_active=True y fecha de fin pasada
        2. Marcar como inactivos (is_live_active=False)
        3. Si tienen seguidores, crear versión ARCHIVED reutilizable
        4. Copiar daily_plans y meals a la versión archivada

        Args:
            db: SQLAlchemy Session

        Returns:
            Número de planes archivados exitosamente
        """
        today = datetime.now()

        # Buscar planes LIVE terminados pero no archivados
        finished_plans = db.query(NutritionPlan).filter(
            NutritionPlan.plan_type == PlanType.LIVE,
            NutritionPlan.is_live_active == True,
            NutritionPlan.live_start_date.isnot(None),
            NutritionPlan.is_recurring == False  # No archivar recurrentes automáticamente
        ).all()

        archived_count = 0

        for plan in finished_plans:
            # Calcular fecha de fin
            end_date = plan.live_start_date + timedelta(days=plan.duration_days)

            # Verificar si el plan terminó
            if today < end_date:
                continue  # Plan aún corriendo

            # Marcar como inactivo
            plan.is_live_active = False
            plan.live_end_date = end_date
            plan.updated_at = datetime.utcnow()

            # Contar participantes activos
            participants_count = len([f for f in plan.followers if f.is_active]) if hasattr(plan, 'followers') else 0

            # Solo crear versión archivada si tuvo participantes
            if participants_count > 0:
                try:
                    archived_plan = NutritionPlan(
                        title=f"{plan.title} (Archivado {end_date.strftime('%Y-%m-%d')})",
                        description=plan.description,
                        goal=plan.goal,
                        difficulty_level=plan.difficulty_level,
                        budget_level=plan.budget_level,
                        dietary_restrictions=plan.dietary_restrictions,
                        duration_days=plan.duration_days,
                        is_recurring=False,
                        target_calories=plan.target_calories,
                        target_protein_g=plan.target_protein_g,
                        target_carbs_g=plan.target_carbs_g,
                        target_fat_g=plan.target_fat_g,
                        is_public=True,  # Archivados siempre públicos
                        tags=plan.tags,
                        plan_type=PlanType.ARCHIVED,
                        creator_id=plan.creator_id,
                        gym_id=plan.gym_id,
                        is_active=True,
                        original_live_plan_id=plan.id,
                        archived_at=datetime.utcnow(),
                        original_participants_count=participants_count
                    )

                    db.add(archived_plan)
                    db.flush()  # Get archived_plan.id

                    # Copiar daily_plans con sus meals e ingredients
                    for daily_plan in plan.daily_plans:
                        archived_daily = DailyNutritionPlan(
                            nutrition_plan_id=archived_plan.id,
                            day_number=daily_plan.day_number,
                            planned_date=None,  # Archived plans no tienen fechas fijas
                            total_calories=daily_plan.total_calories,
                            total_protein_g=daily_plan.total_protein_g,
                            total_carbs_g=daily_plan.total_carbs_g,
                            total_fat_g=daily_plan.total_fat_g,
                            notes=daily_plan.notes,
                            is_published=True  # Archivados siempre publicados
                        )
                        db.add(archived_daily)
                        db.flush()  # Get archived_daily.id

                        # Copiar meals
                        for meal in daily_plan.meals:
                            archived_meal = Meal(
                                daily_plan_id=archived_daily.id,
                                name=meal.name,
                                meal_type=meal.meal_type,
                                description=meal.description,
                                calories=meal.calories,
                                protein_g=meal.protein_g,
                                carbs_g=meal.carbs_g,
                                fat_g=meal.fat_g,
                                fiber_g=meal.fiber_g,
                                order_in_day=meal.order_in_day,
                                cooking_instructions=meal.cooking_instructions,
                                preparation_time_minutes=meal.preparation_time_minutes,
                                image_url=meal.image_url,
                                video_url=meal.video_url
                            )
                            db.add(archived_meal)
                            db.flush()  # Get archived_meal.id

                            # Copiar ingredients
                            for ingredient in meal.ingredients:
                                archived_ingredient = MealIngredient(
                                    meal_id=archived_meal.id,
                                    name=ingredient.name,
                                    quantity=ingredient.quantity,
                                    unit=ingredient.unit,
                                    alternatives=ingredient.alternatives,
                                    is_optional=ingredient.is_optional,
                                    calories_per_serving=ingredient.calories_per_serving,
                                    protein_per_serving=ingredient.protein_per_serving,
                                    carbs_per_serving=ingredient.carbs_per_serving,
                                    fat_per_serving=ingredient.fat_per_serving
                                )
                                db.add(archived_ingredient)

                    logger.info(f"Created archived version of plan {plan.id} with {len(plan.daily_plans)} days")
                    archived_count += 1

                except Exception as e:
                    logger.error(f"Error creating archived version of plan {plan.id}: {e}")
                    # Continuar con otros planes aunque uno falle
                    continue
            else:
                logger.info(f"Plan {plan.id} finished but had no participants, not creating archived version")

        # Commit todos los cambios
        try:
            db.commit()
            logger.info(f"✅ Auto-archived {archived_count} finished LIVE plans")
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Error committing archived plans: {e}")
            raise

        return archived_count

    @staticmethod
    def cleanup_old_archived_plans(db: Session, days_to_keep: int = 365) -> int:
        """
        Eliminar planes ARCHIVED muy antiguos (opcional).

        Args:
            db: SQLAlchemy Session
            days_to_keep: Número de días a mantener (default: 365 = 1 año)

        Returns:
            Número de planes eliminados
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        old_plans = db.query(NutritionPlan).filter(
            NutritionPlan.plan_type == PlanType.ARCHIVED,
            NutritionPlan.archived_at < cutoff_date
        ).all()

        deleted_count = 0
        for plan in old_plans:
            try:
                # Soft delete
                plan.is_active = False
                plan.updated_at = datetime.utcnow()
                deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting old archived plan {plan.id}: {e}")
                continue

        db.commit()
        logger.info(f"Cleaned up {deleted_count} old archived plans (older than {days_to_keep} days)")

        return deleted_count
