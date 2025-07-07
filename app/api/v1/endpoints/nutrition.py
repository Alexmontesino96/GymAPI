"""
Endpoints para el sistema de planes nutricionales.
"""

from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Header
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth0_fastapi import get_current_user, Auth0User
from app.core.tenant import verify_gym_access
from app.models.user import User
from app.models.gym import Gym
from app.schemas.nutrition import (
    NutritionPlan, NutritionPlanCreate, NutritionPlanUpdate, NutritionPlanFilters,
    NutritionPlanListResponse, NutritionPlanWithDetails, NutritionPlanListResponseHybrid,
    DailyNutritionPlan, DailyNutritionPlanCreate, DailyNutritionPlanWithMeals,
    Meal, MealCreate, MealWithIngredients, MealIngredient, MealIngredientCreate,
    NutritionPlanFollower, NutritionPlanFollowerCreate,
    UserMealCompletion, UserMealCompletionCreate,
    TodayMealPlan, UserNutritionDashboard, NutritionAnalytics, NutritionDashboardHybrid,
    NutritionGoal, DifficultyLevel, BudgetLevel, DietaryRestriction, MealType, PlanType, PlanStatus,
    ArchivePlanRequest, LivePlanStatusUpdate
)
from app.services.nutrition import NutritionService, NotFoundError, ValidationError, PermissionError
from app.services.user import user_service

router = APIRouter()


@router.get("/plans", response_model=NutritionPlanListResponse)
def list_nutrition_plans(
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Número de página para paginación"),
    per_page: int = Query(20, ge=1, le=100, description="Elementos por página (máximo 100)"),
    goal: Optional[NutritionGoal] = Query(None, description="Filtrar por objetivo nutricional (loss, gain, bulk, cut, maintain)"),
    difficulty_level: Optional[DifficultyLevel] = Query(None, description="Filtrar por nivel de dificultad (beginner, intermediate, advanced)"),
    budget_level: Optional[BudgetLevel] = Query(None, description="Filtrar por nivel de presupuesto (low, medium, high)"),
    dietary_restrictions: Optional[DietaryRestriction] = Query(None, description="Filtrar por restricciones dietéticas (vegetarian, vegan, gluten_free, etc.)"),
    search_query: Optional[str] = Query(None, description="Buscar por título o descripción del plan"),
    creator_id: Optional[int] = Query(None, description="Filtrar por ID del creador del plan"),
    plan_type: Optional[PlanType] = Query(None, description="Filtrar por tipo: template (individual), live (grupal), archived (histórico)"),
    status: Optional[PlanStatus] = Query(None, description="Filtrar por estado: not_started, running, finished"),
    is_live_active: Optional[bool] = Query(None, description="Solo planes live que están actualmente activos"),
):
    """
    📋 **Listar Planes Nutricionales con Filtros Avanzados**
    
    **Descripción:**
    Obtiene una lista paginada de planes nutricionales del gimnasio con múltiples filtros.
    Incluye soporte completo para el sistema híbrido (template, live, archived).
    
    **Casos de Uso:**
    - 📱 Pantalla principal de planes disponibles
    - 🔍 Búsqueda y filtrado de planes por características
    - 👥 Ver planes creados por entrenadores específicos
    - 🎯 Encontrar planes según objetivos personales
    - ⚡ Mostrar solo planes live activos para unirse
    
    **Filtros Disponibles:**
    - **Tipo de Plan:** template (individual), live (sincronizado), archived (histórico)
    - **Estado:** not_started (no iniciado), running (activo), finished (terminado)
    - **Objetivo:** loss (pérdida), gain (ganancia), bulk (volumen), cut (definición)
    - **Dificultad:** beginner, intermediate, advanced
    - **Presupuesto:** low, medium, high
    - **Restricciones:** vegetarian, vegan, gluten_free, dairy_free, etc.
    
    **Permisos:**
    - ✅ Cualquier miembro del gimnasio puede ver planes públicos
    - ✅ Creadores pueden ver sus propios planes privados
    - ✅ Seguidores pueden ver planes privados que siguen
    
    **Paginación:**
    - Página por defecto: 1
    - Elementos por página: 20 (máximo 100)
    - Metadatos incluidos: has_next, has_prev, total
    
    **Ejemplo de Respuesta:**
    ```json
    {
      "plans": [
        {
          "id": 1,
          "title": "Plan de Pérdida de Peso - 30 días",
          "plan_type": "template",
          "status": "running",
          "current_day": 15,
          "total_followers": 87
        }
      ],
      "total": 150,
      "page": 1,
      "per_page": 20,
      "has_next": true,
      "has_prev": false
    }
    ```
    """
    service = NutritionService(db)
    
    # Crear filtros
    filters = NutritionPlanFilters(
        goal=goal,
        difficulty_level=difficulty_level,
        budget_level=budget_level,
        dietary_restrictions=dietary_restrictions,
        search_query=search_query,
        creator_id=creator_id,
        plan_type=plan_type,
        status=status,
        is_live_active=is_live_active
    )
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    plans, total = service.list_nutrition_plans(
        gym_id=current_gym.id,
        filters=filters,
        page=page,
        per_page=per_page,
        user_id=db_user.id
    )
    
    return NutritionPlanListResponse(
        plans=plans,
        total=total,
        page=page,
        per_page=per_page,
        has_next=(page * per_page) < total,
        has_prev=page > 1
    )


@router.post("/plans", response_model=NutritionPlan)
def create_nutrition_plan(
    plan_data: NutritionPlanCreate,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    ➕ **Crear Nuevo Plan Nutricional**
    
    **Descripción:**
    Crea un plan nutricional vacío que luego se puede llenar con días y comidas.
    Soporte completo para los 3 tipos del sistema híbrido.
    
    **Tipos de Planes:**
    - 📋 **Template:** Plan individual, cada usuario lo inicia cuando quiere
    - 🔴 **Live:** Plan grupal sincronizado, fecha de inicio fija para todos
    - 📚 **Archived:** Plan histórico creado automáticamente desde lives terminados
    
    **Campos Requeridos:**
    - `title`: Nombre del plan (máximo 200 caracteres)
    - `goal`: Objetivo nutricional (loss, gain, bulk, cut, maintain)
    - `duration_days`: Duración en días (1-365)
    - `plan_type`: Tipo de plan (template, live, archived)
    
    **Campos Específicos por Tipo:**
    - **Live Plans:** Requieren `live_start_date`
    - **Template/Archived:** `live_start_date` debe ser null
    
    **Permisos:**
    - 👨‍⚕️ Solo entrenadores y administradores pueden crear planes
    - ✅ Automáticamente asigna al usuario como creador
    
    **Proceso de Creación:**
    1. Crear plan básico ➡️ 
    2. Agregar días (`POST /plans/{id}/days`) ➡️ 
    3. Agregar comidas (`POST /days/{id}/meals`) ➡️ 
    4. Agregar ingredientes (`POST /meals/{id}/ingredients`)
    
    **Validaciones Automáticas:**
    - Verificación de permisos de usuario
    - Validación de fechas para planes live
    - Conversión automática de tags a JSON
    - Asignación de gym_id del contexto actual
    
    **Ejemplo de Request:**
    ```json
    {
      "title": "Plan Detox 21 días",
      "description": "Plan de limpieza corporal",
      "goal": "loss",
      "difficulty_level": "beginner",
      "plan_type": "live",
      "duration_days": 21,
      "live_start_date": "2024-02-01T00:00:00Z",
      "target_calories": 1500,
      "is_public": true,
      "tags": ["detox", "principiante"]
    }
    ```
    
    **Códigos de Error:**
    - `400`: Datos inválidos o validación fallida
    - `403`: Sin permisos para crear planes
    - `404`: Usuario no encontrado
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        # Usar el método específico para planes live o el método base
        if plan_data.plan_type == PlanType.LIVE:
            plan = service.create_live_nutrition_plan(
                plan_data=plan_data,
                creator_id=db_user.id,
                gym_id=current_gym.id
            )
        else:
            plan = service.create_nutrition_plan(
                plan_data=plan_data,
                creator_id=db_user.id,
                gym_id=current_gym.id
            )
        return plan
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/plans/{plan_id}", response_model=NutritionPlanWithDetails)
def get_nutrition_plan(
    plan_id: int = Path(..., description="ID único del plan nutricional"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    📖 **Obtener Plan Nutricional Completo**
    
    **Descripción:**
    Obtiene un plan nutricional con toda su información detallada incluyendo:
    días, comidas, ingredientes y metadatos del sistema híbrido.
    
    **Información Incluida:**
    - 📋 **Plan Base:** Título, descripción, objetivos, duración, tipo
    - 📅 **Días Completos:** Todos los días del plan (1 a N)
    - 🍽️ **Meals Detalladas:** Comidas de cada día con ingredientes
    - 🧮 **Información Nutricional:** Calorías, proteínas, carbos, grasas
    - 📊 **Metadatos Híbridos:** Estado actual, día en curso, participantes
    - 👤 **Info del Creador:** Nombre del entrenador que lo creó
    - ✅ **Estado del Usuario:** Si el usuario actual lo está siguiendo
    
    **Control de Acceso:**
    - ✅ **Planes Públicos:** Cualquier miembro puede verlos
    - 🔒 **Planes Privados:** Solo creador y seguidores activos
    - 👨‍⚕️ **Creadores:** Acceso total a sus propios planes
    - 👥 **Seguidores:** Acceso si están siguiendo activamente
    
    **Información por Tipo de Plan:**
    - **Template:** Información estática, disponible siempre
    - **Live:** Estado actualizado en tiempo real, participantes actuales
    - **Archived:** Plan histórico con datos originales preservados
    
    **Casos de Uso:**
    - 📱 Pantalla de detalles del plan
    - 📝 Vista previa antes de seguir un plan
    - 🔍 Navegación completa del contenido
    - 📊 Análisis nutricional detallado
    - 🍽️ Planificación de comidas y compras
    
    **Estructura de Respuesta:**
    ```json
    {
      "id": 1,
      "title": "Plan Detox 21 días",
      "plan_type": "live",
      "current_day": 5,
      "status": "running",
      "live_participants_count": 87,
      "daily_plans": [
        {
          "id": 1,
          "day_number": 1,
          "total_calories": 1500,
          "meals": [
            {
              "id": 1,
              "meal_type": "breakfast",
              "name": "Batido Verde",
              "calories": 250,
              "ingredients": [...]
            }
          ]
        }
      ],
      "creator_name": "Dr. Martínez",
      "is_followed_by_user": true
    }
    ```
    
    **Códigos de Error:**
    - `403`: Sin permisos para ver este plan privado
    - `404`: Plan no encontrado o no pertenece al gimnasio
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        plan = service.get_nutrition_plan_with_details(plan_id, current_gym.id, db_user.id)
        return plan
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/plans/{plan_id}/follow", response_model=NutritionPlanFollower)
def follow_nutrition_plan(
    plan_id: int = Path(..., description="ID del plan nutricional a seguir"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    ✅ **Seguir Plan Nutricional**
    
    **Descripción:**
    Permite al usuario empezar a seguir un plan nutricional específico.
    El comportamiento varía según el tipo de plan del sistema híbrido.
    
    **Comportamiento por Tipo:**
    - 📋 **Template:** Usuario inicia inmediatamente, progreso individual
    - 🔴 **Live:** Usuario se une al plan grupal, progreso sincronizado
    - 📚 **Archived:** Usuario inicia como template, usando contenido archivado
    
    **Proceso de Seguimiento:**
    1. **Validación:** Verifica que el plan existe y es accesible
    2. **Check Duplicados:** Evita seguir el mismo plan dos veces
    3. **Registro:** Crea entrada en NutritionPlanFollower
    4. **Configuración:** Establece notificaciones y preferencias
    5. **Inicio:** Determina fecha de inicio según tipo de plan
    
    **Configuraciones Incluidas:**
    - 🔔 **Notificaciones:** Habilitadas por defecto
    - ⏰ **Horarios Default:**
      - Desayuno: 08:00
      - Almuerzo: 13:00
      - Cena: 20:00
    - 📅 **Fecha Inicio:** 
      - Template/Archived: Inmediata (hoy)
      - Live: Fecha global del plan
    
    **Estados Posibles:**
    - **Template/Archived:** Inicia inmediatamente como "running"
    - **Live (futuro):** Estado "not_started" hasta fecha de inicio
    - **Live (activo):** Inicia inmediatamente sincronizado
    - **Live (terminado):** No se puede seguir
    
    **Validaciones:**
    - ✅ Plan existe y pertenece al gimnasio
    - ✅ Usuario no está siguiendo ya este plan
    - ✅ Plan es público o usuario tiene acceso
    - ✅ Plan live no está terminado
    
    **Casos de Uso:**
    - 🎯 Unirse a un plan personal (template)
    - 👥 Participar en challenge grupal (live)
    - 📚 Usar plan de éxito pasado (archived)
    - 🔄 Reactivar plan que se había dejado
    
    **Ejemplo de Respuesta:**
    ```json
    {
      "id": 123,
      "user_id": 456,
      "plan_id": 789,
      "is_active": true,
      "start_date": "2024-01-15T00:00:00Z",
      "notifications_enabled": true,
      "notification_time_breakfast": "08:00",
      "notification_time_lunch": "13:00",
      "notification_time_dinner": "20:00"
    }
    ```
    
    **Códigos de Error:**
    - `400`: Ya sigues este plan o plan no disponible
    - `404`: Plan no encontrado
    - `403`: Sin acceso a plan privado
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        follower = service.follow_nutrition_plan(
            plan_id=plan_id,
            user_id=db_user.id,
            gym_id=current_gym.id
        )
        return follower
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/plans/{plan_id}/follow")
def unfollow_nutrition_plan(
    plan_id: int = Path(..., description="ID del plan nutricional a dejar de seguir"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    ❌ **Dejar de Seguir Plan Nutricional**
    
    **Descripción:**
    Permite al usuario dejar de seguir un plan nutricional activo.
    Los datos de progreso se conservan pero se marca como inactivo.
    
    **Proceso de Desvinculación:**
    1. **Validación:** Verifica que el usuario esté siguiendo el plan
    2. **Soft Delete:** Marca como `is_active = false`
    3. **Fecha Fin:** Establece `end_date` como timestamp actual
    4. **Preservación:** Mantiene historial de progreso y completaciones
    5. **Notificaciones:** Desactiva automáticamente las notificaciones
    
    **Datos Preservados:**
    - 📊 **Progreso Histórico:** Todas las meals completadas
    - 📈 **Estadísticas:** Porcentajes de completación por día
    - 📸 **Fotos de Comidas:** URLs de imágenes subidas
    - ⭐ **Calificaciones:** Ratings de satisfacción dados
    - 💬 **Notas Personales:** Comentarios en completaciones
    
    **Implicaciones por Tipo:**
    - **Template:** Pausa progreso individual, puede retomar después
    - **Live:** Se sale del challenge grupal, no afecta a otros
    - **Archived:** Detiene seguimiento del plan histórico
    
    **Reactivación Posterior:**
    - ✅ Usuario puede volver a seguir el mismo plan más tarde
    - 🔄 Se crea nueva entrada en NutritionPlanFollower
    - 📅 Nuevo `start_date` si vuelve a seguirlo
    - 📊 Progreso anterior permanece en historial
    
    **Casos de Uso:**
    - 🛑 Pausar plan temporalmente
    - 🔄 Cambiar a un plan diferente
    - 😔 Abandono por dificultad o falta de tiempo
    - ✅ Completar plan exitosamente
    
    **Validaciones:**
    - ✅ Plan existe y pertenece al gimnasio
    - ✅ Usuario está actualmente siguiendo el plan
    - ✅ Entrada de seguimiento está activa
    
    **Ejemplo de Respuesta:**
    ```json
    {
      "success": true
    }
    ```
    
    **Análisis de Abandono:**
    - 📊 Los datos quedan disponibles para analytics del creador
    - 📈 Métricas de retención y engagement
    - 🎯 Identificación de puntos de abandono comunes
    - 💡 Insights para mejorar futuros planes
    
    **Códigos de Error:**
    - `404`: No estás siguiendo este plan actualmente
    - `404`: Plan no encontrado en este gimnasio
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        success = service.unfollow_nutrition_plan(
            plan_id=plan_id,
            user_id=db_user.id,
            gym_id=current_gym.id
        )
        return {"success": success}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/meals/{meal_id}/complete", response_model=UserMealCompletion)
def complete_meal(
    completion_data: UserMealCompletionCreate,
    meal_id: int = Path(..., description="ID único de la comida a completar"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    ✅ **Completar Comida (Tracking Central)**
    
    **Descripción:**
    Marca una comida específica como completada por el usuario.
    Endpoint fundamental para el tracking y analytics del sistema.
    
    **Proceso de Completación:**
    1. **Validación:** Verifica que la comida existe y usuario sigue el plan
    2. **Check Duplicados:** Evita completar la misma comida dos veces
    3. **Registro:** Crea entrada en UserMealCompletion con timestamp
    4. **Analytics:** Actualiza progreso diario automáticamente
    5. **Notificaciones:** Trigger para celebraciones y logros
    
    **Datos Opcionales Incluidos:**
    - ⭐ **satisfaction_rating:** Calificación 1-5 de qué tan rica estuvo
    - 📸 **photo_url:** URL de foto de la comida preparada
    - 💬 **notes:** Comentarios personales del usuario
    - 🕒 **completed_at:** Timestamp automático de completación
    
    **Validaciones Automáticas:**
    - ✅ La comida pertenece a un plan que el usuario está siguiendo
    - ✅ El usuario está activamente siguiendo ese plan
    - ✅ La comida no ha sido completada previamente
    - ✅ La comida pertenece al gimnasio correcto
    
    **Impacto en el Sistema:**
    - 📊 **Progreso Diario:** Se recalcula el porcentaje del día
    - 🎯 **Streaks:** Actualiza rachas de completación
    - 📈 **Analytics:** Contribuye a métricas del plan
    - 🏆 **Gamificación:** Puede disparar logros o badges
    
    **Ejemplo de Request:**
    ```json
    {
      "satisfaction_rating": 5,
      "photo_url": "https://example.com/my-meal.jpg",
      "notes": "Estuvo deliciosa, muy fácil de preparar"
    }
    ```
    
    **Ejemplo de Respuesta:**
    ```json
    {
      "id": 789,
      "user_id": 123,
      "meal_id": 456,
      "satisfaction_rating": 5,
      "photo_url": "https://example.com/my-meal.jpg",
      "notes": "Estuvo deliciosa, muy fácil de preparar",
      "completed_at": "2024-01-15T12:30:00Z",
      "created_at": "2024-01-15T12:30:00Z"
    }
    ```
    
    **Casos de Uso:**
    - ✅ Check diario de comidas consumidas
    - 📸 Compartir progreso con fotos
    - ⭐ Feedback para mejorar futuras comidas
    - 📊 Tracking personal de adherencia
    - 👥 Participación en challenges grupales
    
    **Metrics Calculadas:**
    - 📈 **Completion Rate:** % de comidas completadas vs planeadas
    - 🔥 **Current Streak:** Días consecutivos cumpliendo metas
    - ⭐ **Average Rating:** Satisfacción promedio con el plan
    - 📅 **Daily Progress:** Progreso del día actual (0-100%)
    
    **Información para Creadores:**
    - 📊 Los datos anónimos contribuyen a analytics del plan
    - ⭐ Ratings ayudan a identificar comidas populares
    - 📸 Fotos pueden inspirar a otros usuarios
    - 💬 Comentarios revelan insights de mejora
    
    **Códigos de Error:**
    - `400`: Comida ya completada anteriormente
    - `400`: No estás siguiendo el plan que contiene esta comida
    - `404`: Comida no encontrada o no pertenece al gimnasio
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        completion = service.complete_meal(
            meal_id=meal_id,
            user_id=db_user.id,
            gym_id=current_gym.id,
            satisfaction_rating=completion_data.satisfaction_rating,
            photo_url=completion_data.photo_url,
            notes=completion_data.notes
        )
        return completion
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/today", response_model=TodayMealPlan)
def get_today_meal_plan(
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    🍽️ **Plan de Comidas de HOY (Lógica Híbrida)**
    
    **Descripción:**
    Endpoint más usado del sistema. Obtiene las comidas específicas que el usuario
    debe consumir HOY, con lógica inteligente según el tipo de plan.
    
    **Lógica de Cálculo del Día Actual:**
    - 📋 **Template/Archived:** Día basado en cuándo empezó el usuario individualmente
    - 🔴 **Live:** Día basado en fecha global compartida por todos los usuarios
    - 🕒 **Cálculo:** `current_day = días_transcurridos + 1`
    
    **Ejemplos de Cálculo:**
    ```
    Template Plan:
    - Usuario empezó: 1 enero
    - Hoy: 15 enero  
    - current_day = (15-1) + 1 = 15
    - Devuelve: Comidas del Día 15
    
    Live Plan:
    - Plan empezó: 1 febrero (para todos)
    - Hoy: 5 febrero
    - current_day = (5-1) + 1 = 5  
    - Devuelve: Comidas del Día 5 (todos ven lo mismo)
    ```
    
    **Estados Posibles:**
    - ✅ **running:** Plan activo, devuelve comidas del día actual
    - ⏳ **not_started:** Plan live futuro, devuelve `meals: []` y días restantes
    - 🏁 **finished:** Plan terminado, busca próximo plan activo
    
    **Información Incluida:**
    - 🍽️ **Meals Completas:** Desayuno, almuerzo, cena con ingredientes
    - 📊 **Progreso:** Porcentaje de comidas completadas hoy (0-100%)
    - 🎯 **Plan Context:** Información del plan que se está siguiendo
    - 📅 **Metadatos:** Día actual, estado, días hasta inicio (si aplica)
    
    **Casos de Respuesta:**
    
    **1. Plan Activo con Comidas:**
    ```json
    {
      "date": "2024-01-15",
      "current_day": 15,
      "status": "running",
      "plan": {
        "id": 123,
        "title": "Plan Pérdida Peso",
        "plan_type": "template"
      },
      "meals": [
        {
          "id": 456,
          "meal_type": "breakfast",
          "meal_name": "Avena con Frutas",
          "calories": 350,
          "ingredients": [...]
        }
      ],
      "completion_percentage": 33.3
    }
    ```
    
    **2. Plan Live Próximo a Empezar:**
    ```json
    {
      "date": "2024-01-15",
      "current_day": 0,
      "status": "not_started", 
      "days_until_start": 7,
      "plan": {
        "id": 789,
        "title": "Challenge Detox",
        "plan_type": "live"
      },
      "meals": []
    }
    ```
    
    **3. Sin Planes Activos:**
    ```json
    {
      "date": "2024-01-15",
      "current_day": 0,
      "status": "not_started",
      "meals": []
    }
    ```
    
    **Casos de Uso:**
    - 📱 Pantalla principal de la app nutricional
    - 🔔 Notificaciones push con comidas del día
    - ✅ Lista de pendientes diarios
    - 📊 Dashboard de progreso
    - 🍽️ Widget de "comidas de hoy"
    
    **Optimizaciones:**
    - 🔄 Actualización automática de estados live
    - 📦 Carga eficiente con selectinload
    - 🎯 Búsqueda inteligente de plan activo
    - ⚡ Cache-friendly para llamadas frecuentes
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Usar la nueva lógica híbrida
    meal_plan = service.get_hybrid_today_meal_plan(
        user_id=db_user.id,
        gym_id=current_gym.id
    )
    
    return meal_plan


@router.get("/dashboard", response_model=NutritionDashboardHybrid)
def get_nutrition_dashboard(
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    📊 **Dashboard Nutricional Híbrido**
    
    **Descripción:**
    Vista unificada del estado nutricional completo del usuario.
    Organiza planes por categorías y muestra métricas de progreso.
    
    **Categorización Inteligente:**
    - 📋 **Template Plans:** Planes individuales que el usuario está siguiendo
    - 🔴 **Live Plans:** Challenges grupales activos o próximos
    - 📚 **Available Plans:** Planes públicos disponibles para unirse
    - 🍽️ **Today Plan:** Plan específico de comidas para hoy
    
    **Información por Categoría:**
    
    **Template Plans:**
    - Planes personales en progreso
    - Progreso individual por usuario
    - current_day basado en fecha de inicio individual
    - Estado: running, finished según duración personal
    
    **Live Plans:**
    - Challenges con fechas sincronizadas
    - Contador de participantes en tiempo real
    - current_day basado en fecha global del plan
    - Estados: not_started, running, finished (para todos igual)
    
    **Available Plans:**
    - Planes públicos del gimnasio que no sigue
    - Preview de contenido y características
    - Información para decidir si unirse
    - Filtrados por relevancia y popularidad
    
    **Today Plan:**
    - Comidas específicas para HOY
    - Progreso de completación del día actual
    - Información del plan activo
    - Llamadas a acción pendientes
    
    **Métricas Incluidas:**
    - 🔥 **Completion Streak:** Días consecutivos cumpliendo objetivos
    - 📈 **Weekly Progress:** Progreso de los últimos 7 días
    - 🎯 **Today Progress:** % de comidas completadas hoy
    - 📊 **Plan Status:** Estado actualizado de cada plan
    
    **Estructura de Respuesta:**
    ```json
    {
      "template_plans": [
        {
          "id": 123,
          "title": "Mi Plan Personal",
          "plan_type": "template",
          "current_day": 15,
          "status": "running",
          "completion_percentage": 85.5
        }
      ],
      "live_plans": [
        {
          "id": 456,
          "title": "Challenge Detox",
          "plan_type": "live", 
          "current_day": 5,
          "status": "running",
          "live_participants_count": 87,
          "days_until_start": 0
        }
      ],
      "available_plans": [
        {
          "id": 789,
          "title": "Plan Masa Muscular",
          "plan_type": "template",
          "total_followers": 150,
          "avg_satisfaction": 4.8
        }
      ],
      "today_plan": {
        "date": "2024-01-15",
        "current_day": 5,
        "status": "running",
        "meals": [...],
        "completion_percentage": 66.7
      },
      "completion_streak": 7,
      "weekly_progress": [...]
    }
    ```
    
    **Casos de Uso:**
    - 📱 Pantalla principal de la sección nutrition
    - 👁️ Vista rápida del estado general
    - 🎯 Identificar tareas pendientes del día
    - 📊 Monitorear progreso semanal
    - 🔍 Descubrir nuevos planes disponibles
    
    **Optimizaciones:**
    - 🔄 Estados actualizados en tiempo real para planes live
    - 📦 Carga eficiente de datos relacionados
    - 🎯 Filtrado inteligente de planes relevantes
    - ⚡ Agregación optimizada de métricas
    
    **Personalización:**
    - Orden por relevancia personal
    - Planes recomendados según historial
    - Métricas adaptadas a objetivos del usuario
    - Filtros automáticos de contenido apropiado
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    dashboard = service.get_hybrid_dashboard(
        user_id=db_user.id,
        gym_id=current_gym.id
    )
    
    return dashboard


# ===== ENDPOINTS PARA CREADORES DE CONTENIDO =====

@router.post("/plans/{plan_id}/days", response_model=DailyNutritionPlan)
def create_daily_plan(
    daily_plan_data: DailyNutritionPlanCreate,
    plan_id: int = Path(..., description="ID del plan nutricional al que agregar el día"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    📅 **Crear Día de Plan Nutricional (Para Creadores)**
    
    **Descripción:**
    Permite a entrenadores y creadores agregar un día específico a su plan nutricional.
    Cada día representa una jornada completa de comidas estructuradas.
    
    **Proceso de Creación:**
    1. **Validación de Permisos:** Solo el creador del plan puede agregar días
    2. **Verificación de Secuencia:** Valida número de día lógico
    3. **Estructura Base:** Crea contenedor para las comidas del día
    4. **Información Nutricional:** Establece metas calóricas del día
    
    **Campos Requeridos:**
    - `day_number`: Número del día (1, 2, 3... hasta duración del plan)
    - `nutrition_plan_id`: Debe coincidir con el {plan_id} del path
    
    **Campos Opcionales:**
    - `planned_date`: Fecha específica (principalmente para planes live)
    - `total_calories`: Meta calórica total del día
    - `total_protein_g`: Meta de proteína en gramos
    - `total_carbs_g`: Meta de carbohidratos en gramos  
    - `total_fat_g`: Meta de grasas en gramos
    - `notes`: Notas especiales para el día (hidratación, descanso, etc.)
    
    **Validaciones Automáticas:**
    - ✅ Usuario es el creador del plan
    - ✅ Plan existe y pertenece al gimnasio
    - ✅ Número de día dentro del rango válido
    - ✅ No duplicar días ya existentes
    - ✅ Consistencia con el plan padre
    
    **Estado Inicial:**
    - `is_published`: false (draft por defecto)
    - `published_at`: null hasta que se publique
    - Listo para agregar comidas con `POST /days/{daily_plan_id}/meals`
    
    **Ejemplo de Request:**
    ```json
    {
      "nutrition_plan_id": 123,
      "day_number": 1,
      "total_calories": 1800,
      "total_protein_g": 120,
      "total_carbs_g": 180,
      "total_fat_g": 80,
      "notes": "Día de inicio - enfoque en hidratación"
    }
    ```
    
    **Ejemplo de Respuesta:**
    ```json
    {
      "id": 456,
      "nutrition_plan_id": 123,
      "day_number": 1,
      "total_calories": 1800,
      "total_protein_g": 120.0,
      "total_carbs_g": 180.0,
      "total_fat_g": 80.0,
      "notes": "Día de inicio - enfoque en hidratación",
      "is_published": false,
      "published_at": null,
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-15T10:00:00Z"
    }
    ```
    
    **Flujo de Trabajo del Creador:**
    1. **Crear Plan Base** ➡️ `POST /plans`
    2. **Agregar Días** ➡️ `POST /plans/{id}/days` (repetir por cada día)
    3. **Agregar Comidas** ➡️ `POST /days/{id}/meals` (por cada comida del día)
    4. **Agregar Ingredientes** ➡️ `POST /meals/{id}/ingredients` (detalles de comidas)
    5. **Publicar Día** ➡️ Cuando esté completo y listo
    
    **Casos de Uso:**
    - 📝 Creación inicial de contenido del plan
    - ✏️ Estructuración día por día del programa
    - 🎯 Definición de metas nutricionales diarias
    - 📊 Planificación balanceada de macronutrientes
    
    **Códigos de Error:**
    - `400`: El plan_id del body no coincide con el path
    - `403`: Solo el creador puede agregar días al plan
    - `404`: Plan no encontrado o no pertenece al gimnasio
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Verificar que el plan_id coincide
    if daily_plan_data.nutrition_plan_id != plan_id:
        raise HTTPException(status_code=400, detail="El plan_id no coincide")
    
    try:
        daily_plan = service.create_daily_plan(
            daily_plan_data=daily_plan_data,
            user_id=db_user.id
        )
        return daily_plan
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/days/{daily_plan_id}/meals", response_model=Meal)
def create_meal(
    meal_data: MealCreate,
    daily_plan_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Crear una comida dentro de un plan diario.
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Verificar que el daily_plan_id coincide
    if meal_data.daily_plan_id != daily_plan_id:
        raise HTTPException(status_code=400, detail="El daily_plan_id no coincide")
    
    try:
        meal = service.create_meal(
            meal_data=meal_data,
            user_id=db_user.id
        )
        return meal
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/meals/{meal_id}/ingredients", response_model=MealIngredient)
def add_ingredient_to_meal(
    ingredient_data: MealIngredientCreate,
    meal_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Añadir un ingrediente a una comida.
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Verificar que el meal_id coincide
    if ingredient_data.meal_id != meal_id:
        raise HTTPException(status_code=400, detail="El meal_id no coincide")
    
    try:
        ingredient = service.add_ingredient_to_meal(
            ingredient_data=ingredient_data,
            user_id=db_user.id
        )
        return ingredient
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ===== ENDPOINTS DE ANALYTICS =====

@router.get("/plans/{plan_id}/analytics", response_model=NutritionAnalytics)
def get_plan_analytics(
    plan_id: int = Path(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Obtener analytics de un plan nutricional.
    Solo el creador puede ver los analytics.
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        analytics = service.get_nutrition_analytics(
            plan_id=plan_id,
            user_id=db_user.id,
            gym_id=current_gym.id
        )
        return analytics
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ===== ENDPOINTS DE UTILIDAD =====

@router.get("/enums/goals")
def get_nutrition_goals():
    """Obtener lista de objetivos nutricionales disponibles."""
    return [{"value": goal.value, "label": goal.value.replace("_", " ").title()} 
            for goal in NutritionGoal]


@router.get("/enums/difficulty-levels")
def get_difficulty_levels():
    """Obtener lista de niveles de dificultad disponibles."""
    return [{"value": level.value, "label": level.value.title()} 
            for level in DifficultyLevel]


@router.get("/enums/budget-levels")
def get_budget_levels():
    """Obtener lista de niveles de presupuesto disponibles."""
    return [{"value": level.value, "label": level.value.title()} 
            for level in BudgetLevel]


@router.get("/enums/dietary-restrictions")
def get_dietary_restrictions():
    """Obtener lista de restricciones dietéticas disponibles."""
    return [{"value": restriction.value, "label": restriction.value.replace("_", " ").title()} 
            for restriction in DietaryRestriction]


@router.get("/enums/meal-types")
def get_meal_types():
    """Obtener lista de tipos de comidas disponibles."""
    return [{"value": meal_type.value, "label": meal_type.value.replace("_", " ").title()} 
            for meal_type in MealType]


@router.get("/enums/plan-types")
def get_plan_types():
    """Obtener lista de tipos de planes disponibles."""
    return [{"value": plan_type.value, "label": plan_type.value.title()} 
            for plan_type in PlanType]


@router.get("/enums/plan-statuses")
def get_plan_statuses():
    """Obtener lista de estados de planes disponibles."""
    return [{"value": status.value, "label": status.value.replace("_", " ").title()} 
            for status in PlanStatus]


# ===== NUEVOS ENDPOINTS DEL SISTEMA HÍBRIDO =====

@router.get("/plans/hybrid", response_model=NutritionPlanListResponseHybrid)
def list_plans_by_type(
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """
    Listar planes categorizados por tipo (live, template, archived).
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Obtener planes por tipo
    live_filters = NutritionPlanFilters(plan_type=PlanType.LIVE)
    template_filters = NutritionPlanFilters(plan_type=PlanType.TEMPLATE)
    archived_filters = NutritionPlanFilters(plan_type=PlanType.ARCHIVED)
    
    live_plans, live_total = service.list_nutrition_plans(
        gym_id=current_gym.id, filters=live_filters, page=1, per_page=50, user_id=db_user.id
    )
    
    template_plans, template_total = service.list_nutrition_plans(
        gym_id=current_gym.id, filters=template_filters, page=1, per_page=50, user_id=db_user.id
    )
    
    archived_plans, archived_total = service.list_nutrition_plans(
        gym_id=current_gym.id, filters=archived_filters, page=1, per_page=50, user_id=db_user.id
    )
    
    total = live_total + template_total + archived_total
    
    return NutritionPlanListResponseHybrid(
        live_plans=live_plans,
        template_plans=template_plans,
        archived_plans=archived_plans,
        total=total,
        page=page,
        per_page=per_page,
        has_next=(page * per_page) < total,
        has_prev=page > 1
    )


@router.put("/plans/{plan_id}/live-status", response_model=NutritionPlan)
def update_live_plan_status(
    plan_id: int = Path(...),
    status_update: LivePlanStatusUpdate = ...,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Actualizar el estado de un plan live (solo creadores).
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        # Verificar permisos
        plan = service.get_nutrition_plan(plan_id, current_gym.id)
        if plan.creator_id != db_user.id:
            raise HTTPException(status_code=403, detail="Solo el creador puede actualizar el estado del plan")
        
        if plan.plan_type != PlanType.LIVE:
            raise HTTPException(status_code=400, detail="Solo se puede actualizar el estado de planes live")
        
        # Actualizar estado
        plan.is_live_active = status_update.is_live_active
        if status_update.live_participants_count is not None:
            plan.live_participants_count = status_update.live_participants_count
        
        service.db.commit()
        service.db.refresh(plan)
        
        return plan
        
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/plans/{plan_id}/archive", response_model=NutritionPlan)
def archive_live_plan(
    plan_id: int = Path(...),
    archive_request: ArchivePlanRequest = ...,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Archivar un plan live terminado (solo creadores).
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        archived_plan = service.archive_live_plan(
            plan_id=plan_id,
            user_id=db_user.id,
            gym_id=current_gym.id,
            archive_request=archive_request
        )
        return archived_plan
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/plans/{plan_id}/status")
def get_plan_status(
    plan_id: int = Path(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Obtener el estado actual de un plan (day, status, etc.).
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        plan = service.get_nutrition_plan(plan_id, current_gym.id)
        
        # Obtener información de seguimiento del usuario
        follower = None
        if db_user.id != plan.creator_id:
            from app.models.nutrition import NutritionPlanFollower
            follower = service.db.query(NutritionPlanFollower).filter(
                NutritionPlanFollower.plan_id == plan_id,
                NutritionPlanFollower.user_id == db_user.id,
                NutritionPlanFollower.is_active == True
            ).first()
        
        # Calcular estado
        current_day, status = service.get_current_plan_day(plan, follower)
        days_until_start = service.get_days_until_start(plan)
        
        # Actualizar estado de planes live
        if plan.plan_type == PlanType.LIVE:
            plan = service.update_live_plan_status(plan.id, current_gym.id)
        
        return {
            "plan_id": plan.id,
            "plan_type": plan.plan_type,
            "current_day": current_day,
            "status": status,
            "days_until_start": days_until_start,
            "is_live_active": plan.is_live_active,
            "live_participants_count": plan.live_participants_count,
            "is_following": follower is not None
        }
        
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) 