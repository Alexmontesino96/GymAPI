
# ============================================
# DAILY PLAN ENDPOINTS - AGREGADO AUTOMÁTICAMENTE
# Fecha: 2025-12-27 23:52
# ============================================

@router.get("/days/{daily_plan_id}", response_model=DailyNutritionPlanWithMeals)
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


@router.get("/plans/{plan_id}/days", response_model=List[DailyNutritionPlanWithMeals])
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


@router.put("/days/{daily_plan_id}", response_model=DailyNutritionPlan)
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


@router.delete("/days/{daily_plan_id}", status_code=204)
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

    logger.info(f"Día {daily_plan_id} eliminado por usuario {db_user.id}")

    return Response(status_code=204)


# ============================================
# FIN DAILY PLAN ENDPOINTS
# ============================================
