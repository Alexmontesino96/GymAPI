# 🔍 AUDITORÍA: Módulo de Nutrición - Endpoints Implementados vs Faltantes

*Fecha de auditoría: 27 de Diciembre 2024*

## 📊 RESUMEN EJECUTIVO

El módulo de nutrición tiene **funcionalidad avanzada** (IA, notificaciones, planes LIVE) pero **carece de operaciones CRUD básicas** esenciales.

### ⚠️ Estado Actual:
- ✅ **31 endpoints implementados** (funcionalidades complejas)
- ❌ **12 endpoints CRUD básicos faltantes** (operaciones esenciales)
- 🔴 **CRÍTICO:** No se pueden editar ni eliminar comidas, planes o ingredientes

## 📋 ENDPOINTS IMPLEMENTADOS (31 Total)

### 1. PLANES NUTRICIONALES (11 endpoints)
```python
✅ GET    /plans                        # Listar planes con filtros
✅ GET    /plans/{plan_id}               # Obtener plan completo
✅ GET    /plans/hybrid                  # Listar planes modo híbrido
✅ GET    /plans/{plan_id}/analytics     # Analytics del plan
✅ GET    /plans/{plan_id}/status        # Estado del plan
✅ POST   /plans                         # Crear nuevo plan
✅ POST   /plans/{plan_id}/follow        # Seguir un plan
✅ POST   /plans/{plan_id}/archive       # Archivar plan
✅ PUT    /plans/{plan_id}/live-status   # Actualizar estado LIVE
✅ DELETE /plans/{plan_id}/follow        # Dejar de seguir
❌ PUT    /plans/{plan_id}               # FALTA: Actualizar plan
❌ DELETE /plans/{plan_id}               # FALTA: Eliminar plan
```

### 2. DÍAS DEL PLAN (Daily Plans) (2 endpoints)
```python
✅ POST   /plans/{plan_id}/days          # Crear día en plan
✅ POST   /days/{daily_plan_id}/meals    # Agregar comida a día
❌ GET    /days/{daily_plan_id}          # FALTA: Obtener día específico
❌ PUT    /days/{daily_plan_id}          # FALTA: Actualizar día
❌ DELETE /days/{daily_plan_id}          # FALTA: Eliminar día
❌ GET    /plans/{plan_id}/days          # FALTA: Listar días del plan
```

### 3. COMIDAS (Meals) (5 endpoints)
```python
✅ POST   /days/{daily_plan_id}/meals    # Crear comida en día
✅ POST   /meals/{meal_id}/complete      # Marcar completada
✅ POST   /meals/{meal_id}/ingredients   # Agregar ingrediente
✅ POST   /meals/{meal_id}/ingredients/ai-generate  # Generar con IA
✅ POST   /meals/{meal_id}/ingredients/ai-apply     # Aplicar IA
❌ GET    /meals/{meal_id}               # FALTA: Obtener comida
❌ PUT    /meals/{meal_id}               # FALTA: Actualizar comida
❌ DELETE /meals/{meal_id}               # FALTA: Eliminar comida
```

### 4. INGREDIENTES (0 endpoints CRUD)
```python
✅ POST   /meals/{meal_id}/ingredients   # Agregar ingrediente
❌ GET    /ingredients/{ingredient_id}   # FALTA: Obtener ingrediente
❌ PUT    /ingredients/{ingredient_id}   # FALTA: Actualizar ingrediente
❌ DELETE /ingredients/{ingredient_id}   # FALTA: Eliminar ingrediente
```

### 5. DASHBOARD Y VISTAS (3 endpoints)
```python
✅ GET    /today                         # Comidas de hoy
✅ GET    /dashboard                     # Dashboard completo
✅ GET    /analytics                     # Analytics generales
```

### 6. ENUMS Y METADATOS (7 endpoints)
```python
✅ GET    /enums/goals                   # Objetivos nutricionales
✅ GET    /enums/difficulty-levels       # Niveles de dificultad
✅ GET    /enums/budget-levels           # Niveles de presupuesto
✅ GET    /enums/dietary-restrictions    # Restricciones dietéticas
✅ GET    /enums/meal-types              # Tipos de comida
✅ GET    /enums/plan-types              # Tipos de plan
✅ GET    /enums/plan-statuses           # Estados del plan
```

### 7. NOTIFICACIONES (2 endpoints)
```python
✅ GET    /notifications/settings        # Obtener configuración
✅ PUT    /notifications/settings        # Actualizar configuración
```

### 8. TESTING Y UTILIDADES (1 endpoint)
```python
✅ GET    /ai/test-connection            # Test conexión con OpenAI
```

## ❌ ENDPOINTS CRÍTICOS FALTANTES (12 Total)

### 🔴 PRIORIDAD ALTA - Operaciones básicas de Meals (3)
```python
# Sin estos, el frontend no puede:
# - Ver detalles de una comida individual
# - Editar información de comidas
# - Eliminar comidas incorrectas

GET    /api/v1/nutrition/meals/{meal_id}
PUT    /api/v1/nutrition/meals/{meal_id}
DELETE /api/v1/nutrition/meals/{meal_id}
```

### 🟠 PRIORIDAD MEDIA - Gestión de Daily Plans (4)
```python
# Sin estos, el frontend no puede:
# - Ver un día específico del plan
# - Editar información de un día
# - Eliminar días
# - Listar todos los días de un plan

GET    /api/v1/nutrition/days/{daily_plan_id}
PUT    /api/v1/nutrition/days/{daily_plan_id}
DELETE /api/v1/nutrition/days/{daily_plan_id}
GET    /api/v1/nutrition/plans/{plan_id}/days
```

### 🟡 PRIORIDAD NORMAL - Gestión de Plans e Ingredients (5)
```python
# Gestión completa de planes
PUT    /api/v1/nutrition/plans/{plan_id}      # Actualizar plan
DELETE /api/v1/nutrition/plans/{plan_id}      # Eliminar plan

# Gestión de ingredientes
GET    /api/v1/nutrition/ingredients/{ingredient_id}
PUT    /api/v1/nutrition/ingredients/{ingredient_id}
DELETE /api/v1/nutrition/ingredients/{ingredient_id}
```

## 🔧 IMPLEMENTACIÓN SUGERIDA

### 1. MEALS - Endpoints Faltantes (CRÍTICO)

```python
@router.get("/meals/{meal_id}", response_model=MealWithIngredients)
async def get_meal(
    meal_id: int = Path(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """Obtener una comida específica con sus ingredientes"""
    meal = db.query(MealModel).filter(
        MealModel.id == meal_id
    ).options(joinedload(MealModel.ingredients)).first()

    if not meal:
        raise HTTPException(status_code=404, detail="Comida no encontrada")

    # Verificar acceso a través del plan
    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == meal.daily_plan_id
    ).first()

    plan = db.query(NutritionPlan).filter(
        NutritionPlan.id == daily_plan.plan_id,
        NutritionPlan.gym_id == current_gym.id
    ).first()

    if not plan:
        raise HTTPException(status_code=403, detail="Sin acceso a esta comida")

    return meal


@router.put("/meals/{meal_id}", response_model=Meal)
async def update_meal(
    meal_id: int = Path(...),
    meal_update: MealUpdate,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """Actualizar información de una comida"""
    meal = db.query(MealModel).filter(MealModel.id == meal_id).first()

    if not meal:
        raise HTTPException(status_code=404, detail="Comida no encontrada")

    # Verificar permisos (solo creador del plan o admin)
    # ... verificación de permisos ...

    # Actualizar campos
    for field, value in meal_update.dict(exclude_unset=True).items():
        setattr(meal, field, value)

    db.commit()
    db.refresh(meal)
    return meal


@router.delete("/meals/{meal_id}", status_code=204)
async def delete_meal(
    meal_id: int = Path(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """Eliminar una comida y sus ingredientes"""
    meal = db.query(MealModel).filter(MealModel.id == meal_id).first()

    if not meal:
        raise HTTPException(status_code=404, detail="Comida no encontrada")

    # Verificar permisos
    # ... verificación ...

    # Eliminar ingredientes primero (cascada)
    db.query(MealIngredientModel).filter(
        MealIngredientModel.meal_id == meal_id
    ).delete()

    # Eliminar comida
    db.delete(meal)
    db.commit()

    return Response(status_code=204)
```

### 2. DAILY PLANS - Endpoints Faltantes

```python
@router.get("/days/{daily_plan_id}", response_model=DailyNutritionPlanWithMeals)
async def get_daily_plan(
    daily_plan_id: int = Path(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """Obtener un día específico con sus comidas"""
    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == daily_plan_id
    ).options(
        joinedload(DailyNutritionPlanModel.meals).joinedload(MealModel.ingredients)
    ).first()

    if not daily_plan:
        raise HTTPException(status_code=404, detail="Día no encontrado")

    # Verificar acceso
    plan = db.query(NutritionPlan).filter(
        NutritionPlan.id == daily_plan.plan_id,
        NutritionPlan.gym_id == current_gym.id
    ).first()

    if not plan:
        raise HTTPException(status_code=403, detail="Sin acceso a este día")

    return daily_plan


@router.get("/plans/{plan_id}/days", response_model=List[DailyNutritionPlanWithMeals])
async def list_plan_days(
    plan_id: int = Path(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """Listar todos los días de un plan con sus comidas"""
    # Verificar que el plan existe y pertenece al gym
    plan = db.query(NutritionPlan).filter(
        NutritionPlan.id == plan_id,
        NutritionPlan.gym_id == current_gym.id
    ).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    daily_plans = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.plan_id == plan_id
    ).options(
        joinedload(DailyNutritionPlanModel.meals).joinedload(MealModel.ingredients)
    ).order_by(DailyNutritionPlanModel.day_number).all()

    return daily_plans
```

### 3. INGREDIENTS - Endpoints Faltantes

```python
@router.delete("/ingredients/{ingredient_id}", status_code=204)
async def delete_ingredient(
    ingredient_id: int = Path(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """Eliminar un ingrediente de una comida"""
    ingredient = db.query(MealIngredientModel).filter(
        MealIngredientModel.id == ingredient_id
    ).first()

    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    # Verificar permisos a través del meal -> daily_plan -> plan
    # ...

    db.delete(ingredient)
    db.commit()

    return Response(status_code=204)


@router.put("/ingredients/{ingredient_id}", response_model=MealIngredient)
async def update_ingredient(
    ingredient_id: int = Path(...),
    ingredient_update: MealIngredientUpdate,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """Actualizar un ingrediente"""
    ingredient = db.query(MealIngredientModel).filter(
        MealIngredientModel.id == ingredient_id
    ).first()

    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    # Verificar permisos
    # ...

    # Actualizar campos
    for field, value in ingredient_update.dict(exclude_unset=True).items():
        setattr(ingredient, field, value)

    db.commit()
    db.refresh(ingredient)
    return ingredient
```

## 📈 IMPACTO EN EL FRONTEND

### Sin estos endpoints, el frontend:
1. **No puede** mostrar/editar detalles de comidas individuales
2. **Debe** obtener el plan completo para ver una sola comida (ineficiente)
3. **No puede** permitir a usuarios corregir errores en comidas
4. **No puede** eliminar comidas/ingredientes incorrectos
5. **Debe** implementar workarounds complejos y cacheo agresivo

## ✅ BUENAS NOTICIAS: Schemas Ya Existen

Los schemas necesarios para implementar los endpoints faltantes **YA ESTÁN CREADOS** en `app/schemas/nutrition.py`:

```python
✅ class NutritionPlanUpdate(BaseModel)    # Línea 77
✅ class DailyNutritionPlanUpdate(BaseModel) # Línea 154
✅ class MealUpdate(BaseModel)              # Línea 209
✅ class MealIngredientUpdate(BaseModel)    # Línea 268
```

Esto significa que **la implementación será más rápida** porque:
- Los modelos de datos ya están definidos
- La validación ya está configurada
- Solo falta agregar los endpoints en `nutrition.py`

## 🎯 PLAN DE ACCIÓN RECOMENDADO

### Fase 1: CRÍTICO (1-2 días)
Implementar los 3 endpoints de Meals:
- `GET /meals/{id}`
- `PUT /meals/{id}`
- `DELETE /meals/{id}`

### Fase 2: IMPORTANTE (2-3 días)
Implementar los 4 endpoints de Daily Plans:
- `GET /days/{id}`
- `GET /plans/{id}/days`
- `PUT /days/{id}`
- `DELETE /days/{id}`

### Fase 3: COMPLEMENTARIO (1-2 días)
Implementar gestión de ingredientes y planes:
- `PUT /ingredients/{id}`
- `DELETE /ingredients/{id}`
- `PUT /plans/{id}`
- `DELETE /plans/{id}`

## 🔍 OBSERVACIONES ADICIONALES

### Funcionalidades Avanzadas Implementadas:
- ✅ Sistema de IA con OpenAI
- ✅ Planes LIVE sincronizados
- ✅ Sistema de notificaciones
- ✅ Analytics y métricas
- ✅ Sistema de archivado

### Funcionalidades Básicas Faltantes:
- ❌ CRUD completo de entidades principales
- ❌ Operaciones de actualización
- ❌ Operaciones de eliminación
- ❌ Endpoints de detalle individual

### Recomendación:
El módulo tiene características muy avanzadas pero carece de operaciones básicas esenciales. Se recomienda **priorizar la implementación de los endpoints CRUD básicos** antes de agregar más funcionalidades avanzadas.

---

*Auditoría realizada por: Claude Code Assistant*
*Fecha: 27 de Diciembre 2024*