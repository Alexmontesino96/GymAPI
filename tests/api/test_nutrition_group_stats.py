"""
Tests para Group Completion Stats en planes LIVE.
Valida que las estadísticas grupales se calculen correctamente.
"""

import pytest
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from app.models.nutrition import (
    NutritionPlan, DailyNutritionPlan, Meal, NutritionPlanFollower,
    UserDailyProgress, UserMealCompletion, PlanType, MealType, NutritionGoal
)
from app.models.user import User
from app.models.gym import Gym
from app.schemas.nutrition import GroupCompletionStats


@pytest.fixture
def test_live_plan(db: Session, test_gym: Gym, test_user: User):
    """Crear un plan LIVE de prueba."""
    today = date.today()

    plan = NutritionPlan(
        title="Challenge Detox LIVE",
        description="Plan live para tests",
        goal=NutritionGoal.WEIGHT_LOSS,
        duration_days=21,
        plan_type=PlanType.LIVE,
        live_start_date=today - timedelta(days=5),  # Empezó hace 5 días
        live_end_date=today + timedelta(days=16),   # Termina en 16 días
        is_live_active=True,
        live_participants_count=0,
        target_calories=1500,
        target_protein_g=90.0,
        creator_id=test_user.id,
        gym_id=test_gym.id,
        is_active=True,
        is_public=True
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    # Crear días del plan (solo algunos para test)
    for day_num in range(1, 8):
        daily_plan = DailyNutritionPlan(
            nutrition_plan_id=plan.id,
            day_number=day_num,
            total_calories=1500,
            total_protein_g=90.0,
            is_published=True
        )
        db.add(daily_plan)
        db.commit()
        db.refresh(daily_plan)

        # Agregar comidas al día
        meals_data = [
            (MealType.BREAKFAST, "Batido Verde", 300),
            (MealType.LUNCH, "Ensalada Completa", 450),
            (MealType.DINNER, "Pechuga con Verduras", 550),
            (MealType.MID_MORNING, "Snack de Frutas", 200)
        ]

        for meal_type, name, calories in meals_data:
            meal = Meal(
                daily_plan_id=daily_plan.id,
                meal_type=meal_type,
                name=name,
                calories=calories,
                protein_g=20.0,
                carbs_g=30.0,
                fat_g=10.0
            )
            db.add(meal)

    db.commit()
    return plan


@pytest.fixture
def test_participants(db: Session, test_live_plan: NutritionPlan, test_gym: Gym):
    """Crear varios participantes para el plan live."""
    participants = []

    # Crear 10 usuarios que siguen el plan
    for i in range(10):
        user = User(
            auth0_id=f"auth0|test_participant_{i}",
            email=f"participant{i}@test.com",
            full_name=f"Test Participant {i}",
            gym_id=test_gym.id
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Hacer que sigan el plan
        follower = NutritionPlanFollower(
            user_id=user.id,
            plan_id=test_live_plan.id,
            is_active=True,
            start_date=test_live_plan.live_start_date
        )
        db.add(follower)
        participants.append(user)

    db.commit()
    return participants


def test_live_plan_includes_group_stats(
    client,
    db: Session,
    test_live_plan: NutritionPlan,
    test_participants: list,
    auth_headers
):
    """Verifica que planes LIVE incluyan group_stats en /today."""
    # Hacer que el usuario principal también siga el plan
    from app.services.user import user_service
    current_user = user_service.get_user_by_auth0_id(db, auth0_id="auth0|test_user")

    follower = NutritionPlanFollower(
        user_id=current_user.id,
        plan_id=test_live_plan.id,
        is_active=True,
        start_date=test_live_plan.live_start_date
    )
    db.add(follower)
    db.commit()

    # Llamar al endpoint
    response = client.get("/api/v1/nutrition/today", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    # Verificar que tiene group_stats
    assert 'group_stats' in data
    assert data['group_stats'] is not None

    # Verificar estructura de group_stats
    group_stats = data['group_stats']
    assert 'total_participants' in group_stats
    assert 'active_today' in group_stats
    assert 'completed_day_fully' in group_stats
    assert 'avg_completion_percentage' in group_stats
    assert 'meal_completions' in group_stats
    assert 'current_day' in group_stats
    assert 'plan_id' in group_stats

    # Verificar valores
    assert group_stats['total_participants'] == 11  # 10 + usuario principal
    assert group_stats['plan_id'] == test_live_plan.id
    assert group_stats['current_day'] == 6  # Día 6 (empezó hace 5 días)


def test_template_plan_no_group_stats(
    client,
    db: Session,
    test_gym: Gym,
    test_user: User,
    auth_headers
):
    """Verifica que planes TEMPLATE NO incluyan group_stats."""
    # Crear un plan template
    plan = NutritionPlan(
        title="Plan Template Test",
        description="Plan template para tests",
        goal=NutritionGoal.MUSCLE_GAIN,
        duration_days=30,
        plan_type=PlanType.TEMPLATE,
        target_calories=2000,
        creator_id=test_user.id,
        gym_id=test_gym.id,
        is_active=True
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    # Crear un día con comidas
    daily_plan = DailyNutritionPlan(
        nutrition_plan_id=plan.id,
        day_number=1,
        total_calories=2000,
        is_published=True
    )
    db.add(daily_plan)
    db.commit()
    db.refresh(daily_plan)

    meal = Meal(
        daily_plan_id=daily_plan.id,
        meal_type=MealType.BREAKFAST,
        name="Test Meal",
        calories=500
    )
    db.add(meal)
    db.commit()

    # Usuario sigue el plan
    follower = NutritionPlanFollower(
        user_id=test_user.id,
        plan_id=plan.id,
        is_active=True
    )
    db.add(follower)
    db.commit()

    # Llamar al endpoint
    response = client.get("/api/v1/nutrition/today", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    # Template plans NO deben tener group_stats
    assert data.get('group_stats') is None


def test_group_stats_meal_breakdown(
    client,
    db: Session,
    test_live_plan: NutritionPlan,
    test_participants: list,
    auth_headers
):
    """Verifica breakdown por tipo de comida."""
    # Hacer que algunos usuarios completen comidas
    today = date.today()
    current_day = 6  # Día actual del plan

    # Obtener el daily plan del día actual
    daily_plan = db.query(DailyNutritionPlan).filter(
        DailyNutritionPlan.nutrition_plan_id == test_live_plan.id,
        DailyNutritionPlan.day_number == current_day
    ).first()

    assert daily_plan is not None

    # Obtener meals del día
    meals = db.query(Meal).filter(
        Meal.daily_plan_id == daily_plan.id
    ).all()

    # Hacer que 7/10 usuarios completen breakfast
    breakfast_meal = next((m for m in meals if m.meal_type == MealType.BREAKFAST), None)
    if breakfast_meal:
        for user in test_participants[:7]:
            completion = UserMealCompletion(
                user_id=user.id,
                meal_id=breakfast_meal.id,
                completed_at=datetime.now(),
                satisfaction_rating=5
            )
            db.add(completion)

    # Hacer que 5/10 usuarios completen lunch
    lunch_meal = next((m for m in meals if m.meal_type == MealType.LUNCH), None)
    if lunch_meal:
        for user in test_participants[:5]:
            completion = UserMealCompletion(
                user_id=user.id,
                meal_id=lunch_meal.id,
                completed_at=datetime.now(),
                satisfaction_rating=4
            )
            db.add(completion)

    db.commit()

    # Hacer que el usuario principal siga el plan
    from app.services.user import user_service
    current_user = user_service.get_user_by_auth0_id(db, auth0_id="auth0|test_user")

    follower = NutritionPlanFollower(
        user_id=current_user.id,
        plan_id=test_live_plan.id,
        is_active=True,
        start_date=test_live_plan.live_start_date
    )
    db.add(follower)
    db.commit()

    # Llamar al endpoint
    response = client.get("/api/v1/nutrition/today", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    meal_completions = data['group_stats']['meal_completions']

    assert len(meal_completions) > 0

    for mc in meal_completions:
        assert 'meal_type' in mc
        assert 'completion_rate' in mc
        assert 'total_users_with_meal' in mc
        assert 'users_completed' in mc
        assert 0 <= mc['completion_rate'] <= 100

        # Verificar rates esperados
        if mc['meal_type'] == 'breakfast':
            # 7 de 11 usuarios = ~63.6%
            assert 60 <= mc['completion_rate'] <= 70
        elif mc['meal_type'] == 'lunch':
            # 5 de 11 usuarios = ~45.5%
            assert 40 <= mc['completion_rate'] <= 50


def test_group_stats_multi_tenant_isolation(
    client,
    db: Session,
    test_gym: Gym,
    test_user: User
):
    """CRÍTICO: Verificar que stats no mezclen gimnasios."""
    # Crear segundo gimnasio
    gym2 = Gym(
        name="Gym 2",
        address="Address 2",
        phone="1234567890",
        email="gym2@test.com",
        is_active=True
    )
    db.add(gym2)
    db.commit()
    db.refresh(gym2)

    # Crear plan LIVE en gym2
    today = date.today()
    plan_gym2 = NutritionPlan(
        title="Plan Gym 2",
        goal=NutritionGoal.WEIGHT_LOSS,
        duration_days=14,
        plan_type=PlanType.LIVE,
        live_start_date=today - timedelta(days=3),
        is_live_active=True,
        creator_id=test_user.id,
        gym_id=gym2.id,
        target_calories=1500
    )
    db.add(plan_gym2)
    db.commit()

    # Usuario de gym1 NO debe ver stats del plan de gym2
    # (El endpoint solo devuelve planes del gym del usuario)
    response = client.get(
        "/api/v1/nutrition/today",
        headers={"Authorization": f"Bearer {get_test_token(test_gym.id)}"}
    )

    assert response.status_code == 200
    data = response.json()

    # Si hay group_stats, debe ser de un plan del gym correcto
    if data.get('group_stats'):
        # Verificar que el plan_id corresponde a un plan del gym del usuario
        plan = db.query(NutritionPlan).filter(
            NutritionPlan.id == data['group_stats']['plan_id']
        ).first()
        assert plan.gym_id == test_gym.id


def test_group_stats_with_daily_progress(
    client,
    db: Session,
    test_live_plan: NutritionPlan,
    test_participants: list,
    test_gym: Gym,
    auth_headers
):
    """Verifica cálculo de avg_completion y completed_fully."""
    today = date.today()
    current_day = 6

    # Obtener el daily plan
    daily_plan = db.query(DailyNutritionPlan).filter(
        DailyNutritionPlan.nutrition_plan_id == test_live_plan.id,
        DailyNutritionPlan.day_number == current_day
    ).first()

    # Crear progreso para algunos usuarios
    # 3 usuarios con 100% completado
    for user in test_participants[:3]:
        progress = UserDailyProgress(
            user_id=user.id,
            daily_plan_id=daily_plan.id,
            gym_id=test_gym.id,
            date=today,
            meals_completed=4,
            total_meals=4,
            completion_percentage=100.0
        )
        db.add(progress)

    # 4 usuarios con 50% completado
    for user in test_participants[3:7]:
        progress = UserDailyProgress(
            user_id=user.id,
            daily_plan_id=daily_plan.id,
            gym_id=test_gym.id,
            date=today,
            meals_completed=2,
            total_meals=4,
            completion_percentage=50.0
        )
        db.add(progress)

    # 3 usuarios sin progreso (no reportaron)

    db.commit()

    # Hacer que el usuario principal siga el plan
    from app.services.user import user_service
    current_user = user_service.get_user_by_auth0_id(db, auth0_id="auth0|test_user")

    follower = NutritionPlanFollower(
        user_id=current_user.id,
        plan_id=test_live_plan.id,
        is_active=True,
        start_date=test_live_plan.live_start_date
    )
    db.add(follower)
    db.commit()

    # Llamar al endpoint
    response = client.get("/api/v1/nutrition/today", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    group_stats = data['group_stats']

    # Verificar stats
    assert group_stats['total_participants'] == 11
    assert group_stats['active_today'] == 7  # Solo 7 reportaron progreso
    assert group_stats['completed_day_fully'] == 3  # 3 con 100%

    # Promedio = (3*100 + 4*50 + 0*0) / 7 = 500/7 = ~71.4%
    assert 70 <= group_stats['avg_completion_percentage'] <= 72


def get_test_token(gym_id: int) -> str:
    """Helper para generar token de test."""
    # Esta función debería estar en conftest.py normalmente
    # Aquí es un placeholder
    return "test_token"
