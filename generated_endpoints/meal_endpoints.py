
# ============================================
# MEAL CRUD ENDPOINTS - AGREGADO AUTOMÁTICAMENTE
# Fecha: 2025-12-27 23:52
# ============================================

@router.get("/meals/{meal_id}", response_model=MealWithIngredients)
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


@router.put("/meals/{meal_id}", response_model=Meal)
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
    logger.info(f"Comida {meal_id} actualizada por usuario {db_user.id}")

    return meal


@router.delete("/meals/{meal_id}", status_code=204)
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
    logger.info(f"Comida {meal_id} eliminada por usuario {db_user.id}")

    return Response(status_code=204)


# ============================================
# FIN MEAL CRUD ENDPOINTS
# ============================================
