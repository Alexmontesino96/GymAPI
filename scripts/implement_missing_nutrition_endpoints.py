#!/usr/bin/env python3
"""
Script para implementar los endpoints CRUD faltantes en el módulo de nutrición.
Este script genera el código necesario para agregar los endpoints críticos.

Uso:
    python scripts/implement_missing_nutrition_endpoints.py

Autor: Claude Code Assistant
Fecha: 27 de Diciembre 2024
"""

import os
from datetime import datetime

def generate_meal_endpoints():
    """Genera los endpoints CRUD para Meals"""
    return '''
# ============================================
# MEAL CRUD ENDPOINTS - AGREGADO AUTOMÁTICAMENTE
# Fecha: {date}
# ============================================

@router.get("/meals/{{meal_id}}", response_model=MealWithIngredients)
async def get_meal(
    meal_id: int = Path(..., description="ID único de la comida"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    🍽️ **Obtener Comida Específica**

    Obtiene una comida individual con todos sus ingredientes.

    **Validaciones:**
    - La comida debe existir
    - El plan debe pertenecer al gimnasio actual
    - El usuario debe tener acceso al plan

    **Returns:**
    - Información completa de la comida
    - Lista de ingredientes con información nutricional
    - Metadatos del día al que pertenece
    """
    # Buscar la comida con sus ingredientes
    meal = db.query(MealModel).filter(
        MealModel.id == meal_id
    ).options(joinedload(MealModel.ingredients)).first()

    if not meal:
        raise HTTPException(status_code=404, detail="Comida no encontrada")

    # Verificar acceso a través del plan
    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == meal.daily_plan_id
    ).first()

    if not daily_plan:
        raise HTTPException(status_code=404, detail="Día del plan no encontrado")

    plan = db.query(NutritionPlan).filter(
        NutritionPlan.id == daily_plan.plan_id,
        NutritionPlan.gym_id == current_gym.id
    ).first()

    if not plan:
        raise HTTPException(status_code=403, detail="Sin acceso a esta comida")

    # Verificar si el usuario es el creador o está siguiendo el plan
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if db_user:
        is_creator = plan.created_by == db_user.id
        is_follower = db.query(NutritionPlanFollower).filter(
            NutritionPlanFollower.plan_id == plan.id,
            NutritionPlanFollower.user_id == db_user.id,
            NutritionPlanFollower.is_active == True
        ).first() is not None

        # Si el plan es privado, verificar acceso
        if plan.is_public == False and not is_creator and not is_follower:
            raise HTTPException(status_code=403, detail="Plan privado - sin acceso")

    return meal


@router.put("/meals/{{meal_id}}", response_model=Meal)
async def update_meal(
    meal_id: int = Path(..., description="ID único de la comida a actualizar"),
    meal_update: MealUpdate,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    ✏️ **Actualizar Comida**

    Actualiza la información de una comida existente.

    **Permisos:**
    - Solo el creador del plan puede actualizar
    - Admins del gimnasio pueden actualizar

    **Campos Actualizables:**
    - name: Nombre de la comida
    - meal_type: Tipo (breakfast, lunch, dinner, snack)
    - recipe_instructions: Instrucciones de preparación
    - target_calories/proteins/carbs/fats: Objetivos nutricionales
    - preparation_time: Tiempo de preparación
    """
    # Buscar la comida
    meal = db.query(MealModel).filter(MealModel.id == meal_id).first()

    if not meal:
        raise HTTPException(status_code=404, detail="Comida no encontrada")

    # Verificar permisos a través del plan
    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == meal.daily_plan_id
    ).first()

    plan = db.query(NutritionPlan).filter(
        NutritionPlan.id == daily_plan.plan_id,
        NutritionPlan.gym_id == current_gym.id
    ).first()

    if not plan:
        raise HTTPException(status_code=403, detail="Sin acceso a esta comida")

    # Verificar que es el creador o admin
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=403, detail="Usuario no encontrado")

    is_creator = plan.created_by == db_user.id
    is_admin = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.gym_id == current_gym.id,
        UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
    ).first() is not None

    if not is_creator and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Solo el creador del plan o admins pueden actualizar comidas"
        )

    # Actualizar campos
    update_data = meal_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(meal, field, value)

    # Guardar cambios
    meal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(meal)

    # Log de actividad
    logger.info(f"Comida {{meal_id}} actualizada por usuario {{db_user.id}}")

    return meal


@router.delete("/meals/{{meal_id}}", status_code=204)
async def delete_meal(
    meal_id: int = Path(..., description="ID único de la comida a eliminar"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    🗑️ **Eliminar Comida**

    Elimina permanentemente una comida y todos sus ingredientes.

    **Permisos:**
    - Solo el creador del plan puede eliminar
    - Admins del gimnasio pueden eliminar

    **Importante:**
    - Esta acción es irreversible
    - Se eliminan todos los ingredientes asociados
    - Se eliminan todos los registros de completación
    """
    # Buscar la comida
    meal = db.query(MealModel).filter(MealModel.id == meal_id).first()

    if not meal:
        raise HTTPException(status_code=404, detail="Comida no encontrada")

    # Verificar permisos a través del plan
    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == meal.daily_plan_id
    ).first()

    plan = db.query(NutritionPlan).filter(
        NutritionPlan.id == daily_plan.plan_id,
        NutritionPlan.gym_id == current_gym.id
    ).first()

    if not plan:
        raise HTTPException(status_code=403, detail="Sin acceso a esta comida")

    # Verificar que es el creador o admin
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=403, detail="Usuario no encontrado")

    is_creator = plan.created_by == db_user.id
    is_admin = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.gym_id == current_gym.id,
        UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
    ).first() is not None

    if not is_creator and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Solo el creador del plan o admins pueden eliminar comidas"
        )

    # Eliminar registros de completación primero
    db.query(UserMealCompletion).filter(
        UserMealCompletion.meal_id == meal_id
    ).delete()

    # Eliminar ingredientes
    db.query(MealIngredientModel).filter(
        MealIngredientModel.meal_id == meal_id
    ).delete()

    # Eliminar la comida
    db.delete(meal)
    db.commit()

    # Log de actividad
    logger.info(f"Comida {{meal_id}} eliminada por usuario {{db_user.id}}")

    return Response(status_code=204)


# ============================================
# FIN MEAL CRUD ENDPOINTS
# ============================================
'''.format(date=datetime.now().strftime("%Y-%m-%d %H:%M"))


def generate_daily_plan_endpoints():
    """Genera los endpoints para Daily Plans"""
    return '''
# ============================================
# DAILY PLAN ENDPOINTS - AGREGADO AUTOMÁTICAMENTE
# Fecha: {date}
# ============================================

@router.get("/days/{{daily_plan_id}}", response_model=DailyNutritionPlanWithMeals)
async def get_daily_plan(
    daily_plan_id: int = Path(..., description="ID del día del plan"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    📅 **Obtener Día Específico del Plan**

    Obtiene un día completo con todas sus comidas e ingredientes.

    **Returns:**
    - Información del día (número, nombre, descripción)
    - Lista completa de comidas del día
    - Ingredientes de cada comida
    - Información nutricional agregada
    """
    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == daily_plan_id
    ).options(
        joinedload(DailyNutritionPlanModel.meals).joinedload(MealModel.ingredients)
    ).first()

    if not daily_plan:
        raise HTTPException(status_code=404, detail="Día no encontrado")

    # Verificar acceso a través del plan
    plan = db.query(NutritionPlan).filter(
        NutritionPlan.id == daily_plan.plan_id,
        NutritionPlan.gym_id == current_gym.id
    ).first()

    if not plan:
        raise HTTPException(status_code=403, detail="Sin acceso a este día")

    # Verificar acceso si el plan es privado
    if not plan.is_public:
        db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
        if db_user:
            is_creator = plan.created_by == db_user.id
            is_follower = db.query(NutritionPlanFollower).filter(
                NutritionPlanFollower.plan_id == plan.id,
                NutritionPlanFollower.user_id == db_user.id,
                NutritionPlanFollower.is_active == True
            ).first() is not None

            if not is_creator and not is_follower:
                raise HTTPException(status_code=403, detail="Plan privado - sin acceso")

    return daily_plan


@router.get("/plans/{{plan_id}}/days", response_model=List[DailyNutritionPlanWithMeals])
async def list_plan_days(
    plan_id: int = Path(..., description="ID del plan nutricional"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    📋 **Listar Todos los Días del Plan**

    Obtiene todos los días de un plan con sus comidas, ordenados por día.

    **Returns:**
    - Lista de días ordenada (día 1, día 2, etc.)
    - Cada día incluye todas sus comidas
    - Cada comida incluye sus ingredientes
    """
    # Verificar que el plan existe y pertenece al gym
    plan = db.query(NutritionPlan).filter(
        NutritionPlan.id == plan_id,
        NutritionPlan.gym_id == current_gym.id
    ).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    # Verificar acceso si el plan es privado
    if not plan.is_public:
        db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
        if db_user:
            is_creator = plan.created_by == db_user.id
            is_follower = db.query(NutritionPlanFollower).filter(
                NutritionPlanFollower.plan_id == plan.id,
                NutritionPlanFollower.user_id == db_user.id,
                NutritionPlanFollower.is_active == True
            ).first() is not None

            if not is_creator and not is_follower:
                raise HTTPException(status_code=403, detail="Plan privado - sin acceso")

    # Obtener todos los días con sus comidas
    daily_plans = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.plan_id == plan_id
    ).options(
        joinedload(DailyNutritionPlanModel.meals).joinedload(MealModel.ingredients)
    ).order_by(DailyNutritionPlanModel.day_number).all()

    return daily_plans


@router.put("/days/{{daily_plan_id}}", response_model=DailyNutritionPlan)
async def update_daily_plan(
    daily_plan_id: int = Path(..., description="ID del día a actualizar"),
    day_update: DailyNutritionPlanUpdate,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    ✏️ **Actualizar Día del Plan**

    Actualiza la información de un día específico del plan.

    **Permisos:**
    - Solo el creador del plan
    - Admins del gimnasio

    **Campos Actualizables:**
    - day_name: Nombre del día
    - day_description: Descripción
    - notes: Notas adicionales
    """
    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == daily_plan_id
    ).first()

    if not daily_plan:
        raise HTTPException(status_code=404, detail="Día no encontrado")

    # Verificar permisos
    plan = db.query(NutritionPlan).filter(
        NutritionPlan.id == daily_plan.plan_id,
        NutritionPlan.gym_id == current_gym.id
    ).first()

    if not plan:
        raise HTTPException(status_code=403, detail="Sin acceso a este día")

    # Verificar que es el creador o admin
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=403, detail="Usuario no encontrado")

    is_creator = plan.created_by == db_user.id
    is_admin = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.gym_id == current_gym.id,
        UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
    ).first() is not None

    if not is_creator and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Solo el creador del plan o admins pueden actualizar"
        )

    # Actualizar campos
    update_data = day_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(daily_plan, field, value)

    daily_plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(daily_plan)

    return daily_plan


@router.delete("/days/{{daily_plan_id}}", status_code=204)
async def delete_daily_plan(
    daily_plan_id: int = Path(..., description="ID del día a eliminar"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    🗑️ **Eliminar Día del Plan**

    Elimina un día completo con todas sus comidas e ingredientes.

    **Importante:**
    - Se eliminan TODAS las comidas del día
    - Se eliminan TODOS los ingredientes
    - Esta acción es irreversible
    - Se recalculan los números de día
    """
    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == daily_plan_id
    ).first()

    if not daily_plan:
        raise HTTPException(status_code=404, detail="Día no encontrado")

    # Verificar permisos
    plan = db.query(NutritionPlan).filter(
        NutritionPlan.id == daily_plan.plan_id,
        NutritionPlan.gym_id == current_gym.id
    ).first()

    if not plan:
        raise HTTPException(status_code=403, detail="Sin acceso a este día")

    # Verificar que es el creador o admin
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=403, detail="Usuario no encontrado")

    is_creator = plan.created_by == db_user.id
    is_admin = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.gym_id == current_gym.id,
        UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
    ).first() is not None

    if not is_creator and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Solo el creador del plan o admins pueden eliminar días"
        )

    # Obtener todas las comidas del día
    meals = db.query(MealModel).filter(
        MealModel.daily_plan_id == daily_plan_id
    ).all()

    # Eliminar completaciones, ingredientes y comidas
    for meal in meals:
        db.query(UserMealCompletion).filter(
            UserMealCompletion.meal_id == meal.id
        ).delete()

        db.query(MealIngredientModel).filter(
            MealIngredientModel.meal_id == meal.id
        ).delete()

        db.delete(meal)

    # Guardar el número del día eliminado
    deleted_day_number = daily_plan.day_number

    # Eliminar el día
    db.delete(daily_plan)

    # Reajustar números de días posteriores
    subsequent_days = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.plan_id == plan.id,
        DailyNutritionPlanModel.day_number > deleted_day_number
    ).all()

    for day in subsequent_days:
        day.day_number -= 1

    # Actualizar duración del plan
    plan.duration_days -= 1

    db.commit()

    logger.info(f"Día {{daily_plan_id}} eliminado por usuario {{db_user.id}}")

    return Response(status_code=204)


# ============================================
# FIN DAILY PLAN ENDPOINTS
# ============================================
'''.format(date=datetime.now().strftime("%Y-%m-%d %H:%M"))


def generate_ingredient_endpoints():
    """Genera los endpoints para Ingredients"""
    return '''
# ============================================
# INGREDIENT ENDPOINTS - AGREGADO AUTOMÁTICAMENTE
# Fecha: {date}
# ============================================

@router.put("/ingredients/{{ingredient_id}}", response_model=MealIngredient)
async def update_ingredient(
    ingredient_id: int = Path(..., description="ID del ingrediente"),
    ingredient_update: MealIngredientUpdate,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    ✏️ **Actualizar Ingrediente**

    Actualiza la información nutricional de un ingrediente.

    **Campos Actualizables:**
    - name: Nombre del ingrediente
    - quantity: Cantidad
    - unit: Unidad de medida
    - calories, proteins, carbs, fats: Valores nutricionales
    """
    ingredient = db.query(MealIngredientModel).filter(
        MealIngredientModel.id == ingredient_id
    ).first()

    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    # Verificar acceso a través del meal -> daily_plan -> plan
    meal = db.query(MealModel).filter(
        MealModel.id == ingredient.meal_id
    ).first()

    if not meal:
        raise HTTPException(status_code=404, detail="Comida no encontrada")

    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == meal.daily_plan_id
    ).first()

    plan = db.query(NutritionPlan).filter(
        NutritionPlan.id == daily_plan.plan_id,
        NutritionPlan.gym_id == current_gym.id
    ).first()

    if not plan:
        raise HTTPException(status_code=403, detail="Sin acceso a este ingrediente")

    # Verificar permisos
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=403, detail="Usuario no encontrado")

    is_creator = plan.created_by == db_user.id
    is_admin = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.gym_id == current_gym.id,
        UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
    ).first() is not None

    if not is_creator and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Solo el creador del plan o admins pueden actualizar ingredientes"
        )

    # Actualizar campos
    update_data = ingredient_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(ingredient, field, value)

    ingredient.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ingredient)

    return ingredient


@router.delete("/ingredients/{{ingredient_id}}", status_code=204)
async def delete_ingredient(
    ingredient_id: int = Path(..., description="ID del ingrediente a eliminar"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    🗑️ **Eliminar Ingrediente**

    Elimina un ingrediente de una comida.

    **Importante:**
    - Se recalculan los valores nutricionales de la comida
    - Esta acción es irreversible
    """
    ingredient = db.query(MealIngredientModel).filter(
        MealIngredientModel.id == ingredient_id
    ).first()

    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    # Verificar acceso y permisos (mismo código que update_ingredient)
    meal = db.query(MealModel).filter(
        MealModel.id == ingredient.meal_id
    ).first()

    if not meal:
        raise HTTPException(status_code=404, detail="Comida no encontrada")

    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == meal.daily_plan_id
    ).first()

    plan = db.query(NutritionPlan).filter(
        NutritionPlan.id == daily_plan.plan_id,
        NutritionPlan.gym_id == current_gym.id
    ).first()

    if not plan:
        raise HTTPException(status_code=403, detail="Sin acceso a este ingrediente")

    # Verificar permisos
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=403, detail="Usuario no encontrado")

    is_creator = plan.created_by == db_user.id
    is_admin = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.gym_id == current_gym.id,
        UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
    ).first() is not None

    if not is_creator and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Solo el creador del plan o admins pueden eliminar ingredientes"
        )

    # Eliminar el ingrediente
    db.delete(ingredient)
    db.commit()

    logger.info(f"Ingrediente {{ingredient_id}} eliminado por usuario {{db_user.id}}")

    return Response(status_code=204)


# ============================================
# FIN INGREDIENT ENDPOINTS
# ============================================
'''.format(date=datetime.now().strftime("%Y-%m-%d %H:%M"))


def main():
    print("=" * 60)
    print("GENERADOR DE ENDPOINTS FALTANTES - MÓDULO NUTRICIÓN")
    print("=" * 60)
    print()

    # Crear directorio de salida
    output_dir = "generated_endpoints"
    os.makedirs(output_dir, exist_ok=True)

    # Generar archivos
    files = [
        ("meal_endpoints.py", generate_meal_endpoints()),
        ("daily_plan_endpoints.py", generate_daily_plan_endpoints()),
        ("ingredient_endpoints.py", generate_ingredient_endpoints())
    ]

    for filename, content in files:
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"✅ Generado: {filepath}")

    print()
    print("INSTRUCCIONES DE IMPLEMENTACIÓN:")
    print("-" * 40)
    print("1. Revisar el código generado en la carpeta 'generated_endpoints/'")
    print("2. Copiar cada sección al archivo app/api/v1/endpoints/nutrition.py")
    print("3. Agregar los imports necesarios al inicio del archivo:")
    print()
    print("   from fastapi import Response")
    print("   from app.models.user_gym import UserGym, GymRoleType")
    print("   from app.models.nutrition import UserMealCompletion")
    print("   from typing import List")
    print()
    print("4. Probar cada endpoint con Postman o Swagger")
    print("5. Actualizar la documentación del frontend")
    print()
    print("NOTA: Los schemas (MealUpdate, etc.) ya existen en app/schemas/nutrition.py")
    print()
    print("¡Endpoints generados exitosamente! 🚀")


if __name__ == "__main__":
    main()