
# ============================================
# INGREDIENT ENDPOINTS - AGREGADO AUTOMÁTICAMENTE
# Fecha: 2025-12-27 23:52
# ============================================

@router.put("/ingredients/{ingredient_id}", response_model=MealIngredient)
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


@router.delete("/ingredients/{ingredient_id}", status_code=204)
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

    logger.info(f"Ingrediente {ingredient_id} eliminado por usuario {db_user.id}")

    return Response(status_code=204)


# ============================================
# FIN INGREDIENT ENDPOINTS
# ============================================
