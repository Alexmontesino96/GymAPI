"""
Endpoints para el sistema de planes nutricionales.
"""

from typing import List, Optional, Any, Dict
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
from app.schemas.nutrition_ai import (
    AIIngredientRequest, AIRecipeResponse, ApplyGeneratedIngredientsRequest, ApplyIngredientsResponse
)
from app.services.nutrition import NutritionService, NotFoundError, ValidationError, PermissionError
from app.services.user import user_service
from app.core.dependencies import module_enabled
from app.models.nutrition import Meal as MealModel, DailyNutritionPlan as DailyNutritionPlanModel, MealIngredient as MealIngredientModel
from sqlalchemy.orm import joinedload
import logging

logger = logging.getLogger(__name__)

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
    daily_plan_id: int = Path(..., description="ID del día al que agregar la comida"),
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    🍽️ **Crear Comida en Plan Diario (Para Creadores)**
    
    **Descripción:**
    Permite a creadores agregar una comida específica a un día de su plan nutricional.
    Cada comida representa una instancia alimentaria (desayuno, almuerzo, cena, etc.).
    
    **Proceso de Creación:**
    1. **Validación de Permisos:** Solo el creador del plan puede agregar comidas
    2. **Verificación del Día:** Valida que el día existe y pertenece al plan
    3. **Estructura Base:** Crea contenedor para los ingredientes de la comida
    4. **Información Nutricional:** Establece valores nutricionales base
    
    **Campos Requeridos:**
    - `meal_type`: Tipo de comida (breakfast, lunch, dinner, snack_morning, snack_afternoon, snack_evening)
    - `name`: Nombre descriptivo de la comida
    - `daily_plan_id`: Debe coincidir con el {daily_plan_id} del path
    
    **Campos Opcionales:**
    - `description`: Descripción detallada de la comida
    - `preparation_time_minutes`: Tiempo de preparación estimado
    - `cooking_instructions`: Instrucciones paso a paso
    - `calories`, `protein_g`, `carbs_g`, `fat_g`: Valores nutricionales
    - `fiber_g`: Contenido de fibra
    - `image_url`: URL de imagen de la comida
    - `video_url`: URL de video de preparación
    
    **Tipos de Comidas Disponibles:**
    - `breakfast`: Desayuno
    - `lunch`: Almuerzo  
    - `dinner`: Cena
    - `snack_morning`: Snack de media mañana
    - `snack_afternoon`: Snack de media tarde
    - `snack_evening`: Snack nocturno
    
    **Validaciones Automáticas:**
    - ✅ Usuario es el creador del plan que contiene este día
    - ✅ Día existe y pertenece a un plan del gimnasio
    - ✅ Tipo de comida válido según enum
    - ✅ Valores nutricionales no negativos
    - ✅ URLs válidas para imagen y video
    
    **Estado Inicial:**
    - Lista para agregar ingredientes con `POST /meals/{meal_id}/ingredients`
    - Valores nutricionales se actualizan automáticamente al agregar ingredientes
    - Visible para usuarios una vez que el día se publique
    
    **Ejemplo de Request:**
    ```json
    {
      "daily_plan_id": 456,
      "meal_type": "breakfast",
      "name": "Batido Verde Energético",
      "description": "Batido nutritivo con espinaca, plátano y proteína",
      "preparation_time_minutes": 5,
      "cooking_instructions": "1. Agregar espinaca al blender\\n2. Añadir plátano y proteína\\n3. Licuar hasta obtener consistencia cremosa",
      "calories": 280,
      "protein_g": 25,
      "carbs_g": 35,
      "fat_g": 8,
      "fiber_g": 6,
      "image_url": "https://example.com/batido-verde.jpg"
    }
    ```
    
    **Ejemplo de Respuesta:**
    ```json
    {
      "id": 789,
      "daily_plan_id": 456,
      "meal_type": "breakfast",
      "name": "Batido Verde Energético",
      "description": "Batido nutritivo con espinaca, plátano y proteína",
      "preparation_time_minutes": 5,
      "cooking_instructions": "1. Agregar espinaca al blender\\n2. Añadir plátano y proteína\\n3. Licuar hasta obtener consistencia cremosa",
      "calories": 280,
      "protein_g": 25.0,
      "carbs_g": 35.0,
      "fat_g": 8.0,
      "fiber_g": 6.0,
      "image_url": "https://example.com/batido-verde.jpg",
      "video_url": null,
      "created_at": "2024-01-15T11:00:00Z",
      "updated_at": "2024-01-15T11:00:00Z"
    }
    ```
    
    **Flujo de Trabajo del Creador:**
    1. **Crear Plan** ➡️ `POST /plans`
    2. **Agregar Días** ➡️ `POST /plans/{id}/days`
    3. **Agregar Comidas** ➡️ `POST /days/{id}/meals` (este endpoint)
    4. **Agregar Ingredientes** ➡️ `POST /meals/{id}/ingredients`
    5. **Revisar Totales** ➡️ Los valores nutricionales se actualizan automáticamente
    
    **Mejores Prácticas:**
    - 📸 Incluir imágenes atractivas para motivar a los usuarios
    - 🎥 Videos cortos para técnicas de preparación complejas
    - ⏱️ Tiempo de preparación realista para planificación
    - 📝 Instrucciones claras y paso a paso
    - 🧮 Valores nutricionales aproximados (se refinan con ingredientes)
    
    **Casos de Uso:**
    - 📝 Creación de contenido gastronómico
    - 🎨 Diseño de experiencias culinarias
    - 📊 Estructuración de planes nutricionales
    - 🍳 Documentación de recetas personalizadas
    
    **Códigos de Error:**
    - `400`: El daily_plan_id del body no coincide con el path
    - `403`: Solo el creador puede agregar comidas al plan
    - `404`: Día no encontrado o no pertenece al gimnasio
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
    meal_id: int = Path(..., description="ID de la comida a la que agregar el ingrediente"),
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    🥕 **Agregar Ingrediente a Comida (Para Creadores)**
    
    **Descripción:**
    Permite a creadores agregar ingredientes específicos a una comida de su plan.
    Los ingredientes forman la base detallada de cada receta con información nutricional precisa.
    
    **Proceso de Agregado:**
    1. **Validación de Permisos:** Solo el creador del plan puede agregar ingredientes
    2. **Verificación de Comida:** Valida que la comida existe y pertenece al plan
    3. **Cálculo Nutricional:** Procesa valores nutricionales por cantidad
    4. **Actualización Automática:** Recalcula totales de la comida y día
    
    **Campos Requeridos:**
    - `meal_id`: Debe coincidir con el {meal_id} del path
    - `name`: Nombre del ingrediente (ej: "Pollo pechuga", "Arroz integral")
    - `quantity`: Cantidad numérica (ej: 200, 1.5, 0.5)
    - `unit`: Unidad de medida (gr, ml, units, cups, tbsp, etc.)
    
    **Campos Opcionales:**
    - `calories_per_unit`: Calorías por unidad especificada
    - `protein_g_per_unit`: Proteína por unidad
    - `carbs_g_per_unit`: Carbohidratos por unidad
    - `fat_g_per_unit`: Grasas por unidad
    - `fiber_g_per_unit`: Fibra por unidad
    - `notes`: Notas especiales (ej: "orgánico", "bajo en sodio")
    
    **Unidades de Medida Comunes:**
    - `gr`: Gramos (sólidos)
    - `ml`: Mililitros (líquidos)
    - `units`: Unidades (1 manzana, 2 huevos)
    - `cups`: Tazas
    - `tbsp`: Cucharadas
    - `tsp`: Cucharaditas
    - `oz`: Onzas
    
    **Cálculo Automático:**
    - **Total Ingredient:** `quantity * valor_per_unit`
    - **Update Meal:** Suma todos los ingredientes
    - **Update Day:** Suma todas las comidas del día
    - **Consistency Check:** Verifica coherencia nutricional
    
    **Ejemplo de Request:**
    ```json
    {
      "meal_id": 789,
      "name": "Pollo pechuga sin piel",
      "quantity": 150,
      "unit": "gr",
      "calories_per_unit": 1.65,
      "protein_g_per_unit": 0.31,
      "carbs_g_per_unit": 0,
      "fat_g_per_unit": 0.036,
      "fiber_g_per_unit": 0,
      "notes": "Pollo de granja libre"
    }
    ```
    
    **Ejemplo de Respuesta:**
    ```json
    {
      "id": 1234,
      "meal_id": 789,
      "name": "Pollo pechuga sin piel",
      "quantity": 150.0,
      "unit": "gr",
      "calories_per_unit": 1.65,
      "protein_g_per_unit": 0.31,
      "carbs_g_per_unit": 0.0,
      "fat_g_per_unit": 0.036,
      "fiber_g_per_unit": 0.0,
      "notes": "Pollo de granja libre",
      "total_calories": 247.5,
      "total_protein_g": 46.5,
      "total_carbs_g": 0.0,
      "total_fat_g": 5.4,
      "total_fiber_g": 0.0,
      "created_at": "2024-01-15T11:30:00Z",
      "updated_at": "2024-01-15T11:30:00Z"
    }
    ```
    
    **Validaciones Automáticas:**
    - ✅ Usuario es el creador del plan que contiene esta comida
    - ✅ Comida existe y pertenece a un plan del gimnasio
    - ✅ Cantidad es un valor positivo
    - ✅ Unidad es válida según enum
    - ✅ Valores nutricionales no negativos
    
    **Flujo de Trabajo del Creador:**
    1. **Crear Plan** ➡️ `POST /plans`
    2. **Agregar Días** ➡️ `POST /plans/{id}/days`
    3. **Agregar Comidas** ➡️ `POST /days/{id}/meals`
    4. **Agregar Ingredientes** ➡️ `POST /meals/{id}/ingredients` (este endpoint)
    5. **Verificar Totales** ➡️ Los valores se actualizan automáticamente
    
    **Mejores Prácticas:**
    - 🎯 **Precisión Nutricional:** Usar valores confiables (USDA, tablas oficiales)
    - 📏 **Unidades Consistentes:** Mantener unidades lógicas por tipo de alimento
    - 📝 **Nombres Descriptivos:** Especificar tipo y preparación
    - 🔍 **Notas Útiles:** Incluir información relevante para usuarios
    - ⚖️ **Porciones Realistas:** Cantidades apropiadas para el objetivo
    
    **Casos de Uso:**
    - 📊 Precisión nutricional en recetas
    - 🛒 Generación de listas de compras
    - 🔄 Sustitución de ingredientes
    - 📈 Análisis de macronutrientes
    - 🍽️ Información detallada para usuarios
    
    **Códigos de Error:**
    - `400`: El meal_id del body no coincide con el path
    - `403`: Solo el creador puede agregar ingredientes
    - `404`: Comida no encontrada o no pertenece al gimnasio
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


# ===== ENDPOINTS DE IA NUTRICIONAL =====

@router.post("/meals/{meal_id}/ingredients/ai-generate", response_model=AIRecipeResponse)
async def generate_ingredients_with_ai(
    request: AIIngredientRequest,
    meal_id: int = Path(..., description="ID de la comida para generar ingredientes"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    🤖 **Generar Ingredientes Automáticamente con IA**
    
    **Descripción:**
    Utiliza ChatGPT para generar automáticamente una lista completa de ingredientes
    con valores nutricionales precisos basándose en el nombre de una receta.
    
    **Casos de Uso:**
    - Acelerar la creación de contenido nutricional
    - Generar recetas completas desde nombres simples
    - Obtener valores nutricionales precisos automáticamente
    - Crear variaciones de recetas existentes
    
    **Proceso de Generación:**
    1. **Validación:** Verifica permisos y existencia de la comida
    2. **Prompt Construction:** Construye prompts optimizados para ChatGPT
    3. **IA Generation:** Llama a OpenAI GPT-4o-mini para generar ingredientes
    4. **Validation:** Valida valores nutricionales realistas
    5. **Response:** Devuelve ingredientes listos para usar
    
    **Campos de Request:**
    - `recipe_name`: Nombre de la receta (ej: "Paella de mariscos")
    - `servings`: Número de porciones (1-20)
    - `dietary_restrictions`: Restricciones dietéticas opcionales
    - `cuisine_type`: Tipo de cocina (española, italiana, etc.)
    - `target_calories`: Calorías objetivo por porción
    - `notes`: Notas adicionales o preferencias
    
    **Restricciones Dietéticas Soportadas:**
    - Vegetariana, Vegana, Sin gluten, Sin lactosa
    - Keto, Paleo, Mediterránea
    
    **Validaciones Automáticas:**
    - ✅ Solo el creador del plan puede generar ingredientes
    - ✅ Valores nutricionales dentro de rangos realistas
    - ✅ Coherencia entre macronutrientes y calorías
    - ✅ Ingredientes específicos y cantidades prácticas
    
    **Ejemplo de Request:**
    ```json
    {
      "recipe_name": "Paella de mariscos",
      "servings": 4,
      "dietary_restrictions": ["gluten_free"],
      "cuisine_type": "española",
      "target_calories": 450,
      "notes": "Versión tradicional valenciana"
    }
    ```
    
    **Ejemplo de Response:**
    ```json
    {
      "success": true,
      "ingredients": [
        {
          "name": "Arroz bomba",
          "quantity": 320,
          "unit": "gr",
          "calories_per_unit": 3.5,
          "protein_g_per_unit": 0.07,
          "carbs_g_per_unit": 0.77,
          "fat_g_per_unit": 0.006,
          "notes": "Arroz tradicional para paella"
        }
      ],
      "recipe_instructions": "1. Sofreír el sofrito...",
      "estimated_prep_time": 45,
      "difficulty_level": "intermediate",
      "total_estimated_calories": 1800,
      "model_used": "gpt-4o-mini",
      "generation_time_ms": 2500
    }
    ```
    
    **Características de la IA:**
    - **Modelo:** GPT-4o-mini (optimizado para costo-efectividad)
    - **Precisión:** Valores nutricionales basados en USDA/BEDCA
    - **Velocidad:** Generación típica en 2-5 segundos
    - **Costo:** ~$0.0008 por receta generada
    
    **Códigos de Error:**
    - `400`: Datos de request inválidos
    - `403`: Sin permisos para generar ingredientes
    - `404`: Comida no encontrada
    - `429`: Límite de rate de OpenAI alcanzado
    - `500`: Error interno de IA o timeout
    
    **Mejores Prácticas:**
    - Usa nombres específicos de recetas para mejores resultados
    - Especifica restricciones dietéticas para mayor precisión
    - Revisa y ajusta ingredientes generados según necesidades
    - Considera el tipo de cocina para ingredientes auténticos
    """
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Validar que la comida existe y pertenece al gimnasio
    meal = db.query(MealModel).options(
        joinedload(MealModel.daily_plan).joinedload(DailyNutritionPlanModel.nutrition_plan)
    ).filter(MealModel.id == meal_id).first()
    
    if not meal:
        raise HTTPException(status_code=404, detail="Comida no encontrada")
    
    # Validar que el plan pertenece al gimnasio actual
    if meal.daily_plan.nutrition_plan.gym_id != current_gym.id:
        raise HTTPException(status_code=404, detail="Comida no pertenece a este gimnasio")
    
    # Validar permisos: solo el creador del plan puede generar ingredientes
    if meal.daily_plan.nutrition_plan.creator_id != db_user.id:
        raise HTTPException(
            status_code=403, 
            detail="Solo el creador del plan puede generar ingredientes con IA"
        )
    
    try:
        # Obtener servicio de IA
        from app.services.nutrition_ai import get_nutrition_ai_service, NutritionAIError
        ai_service = get_nutrition_ai_service()
        
        # Generar ingredientes con IA
        logger.info(f"🤖 Generando ingredientes IA para meal {meal_id}: '{request.recipe_name}'")
        result = await ai_service.generate_recipe_ingredients(request)
        
        logger.info(f"✅ IA generó {len(result.ingredients)} ingredientes para meal {meal_id}")
        return result
        
    except NutritionAIError as e:
        logger.error(f"❌ Error de IA nutricional: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Error inesperado en generación IA: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno en generación de IA")


@router.post("/meals/{meal_id}/ingredients/ai-apply", response_model=ApplyIngredientsResponse)
async def apply_generated_ingredients(
    request: ApplyGeneratedIngredientsRequest,
    meal_id: int = Path(..., description="ID de la comida donde aplicar ingredientes"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    ✅ **Aplicar Ingredientes Generados por IA a Comida**
    
    **Descripción:**
    Aplica una lista de ingredientes generados por IA a una comida específica,
    actualizando automáticamente los valores nutricionales totales.
    
    **Proceso de Aplicación:**
    1. **Validación:** Verifica permisos y existencia de comida
    2. **Limpieza:** Opcionalmente reemplaza ingredientes existentes
    3. **Creación:** Crea nuevos MealIngredient en la base de datos
    4. **Cálculo:** Actualiza valores nutricionales de la comida
    5. **Response:** Confirma aplicación exitosa
    
    **Opciones de Aplicación:**
    - `replace_existing`: Si reemplazar ingredientes existentes
    - `update_meal_nutrition`: Si actualizar valores nutricionales automáticamente
    
    **Validaciones Automáticas:**
    - ✅ Solo el creador puede aplicar ingredientes
    - ✅ Ingredientes válidos según schemas
    - ✅ Valores nutricionales realistas
    - ✅ Unidades de medida válidas
    
    **Ejemplo de Request:**
    ```json
    {
      "ingredients": [
        {
          "name": "Arroz bomba",
          "quantity": 320,
          "unit": "gr",
          "calories_per_unit": 3.5,
          "protein_g_per_unit": 0.07,
          "carbs_g_per_unit": 0.77,
          "fat_g_per_unit": 0.006,
          "notes": "Arroz tradicional"
        }
      ],
      "replace_existing": false,
      "update_meal_nutrition": true
    }
    ```
    
    **Códigos de Error:**
    - `400`: Ingredientes inválidos o datos malformados
    - `403`: Sin permisos para modificar la comida
    - `404`: Comida no encontrada
    - `500`: Error interno en aplicación
    """
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
            # Validar comida y permisos (mismo código que endpoint anterior)
        meal = db.query(MealModel).options(
            joinedload(MealModel.daily_plan).joinedload(DailyNutritionPlanModel.nutrition_plan),
            joinedload(MealModel.ingredients)
        ).filter(MealModel.id == meal_id).first()
    
    if not meal:
        raise HTTPException(status_code=404, detail="Comida no encontrada")
    
    if meal.daily_plan.nutrition_plan.gym_id != current_gym.id:
        raise HTTPException(status_code=404, detail="Comida no pertenece a este gimnasio")
    
    if meal.daily_plan.nutrition_plan.creator_id != db_user.id:
        raise HTTPException(
            status_code=403, 
            detail="Solo el creador del plan puede aplicar ingredientes"
        )
    
    try:
        # Importar servicios necesarios
        from app.services.nutrition import NutritionService
        nutrition_service = NutritionService(db)
        
        # Si se debe reemplazar ingredientes existentes
        ingredients_replaced = 0
        if request.replace_existing and meal.ingredients:
            # Eliminar ingredientes existentes
            for existing_ingredient in meal.ingredients:
                db.delete(existing_ingredient)
            ingredients_replaced = len(meal.ingredients)
            db.flush()  # Aplicar eliminaciones
        
        # Crear nuevos ingredientes
        ingredients_added = 0
        total_calories = 0
        total_protein = 0
        total_carbs = 0
        total_fat = 0
        
        for generated_ingredient in request.ingredients:
            # Crear MealIngredient
            meal_ingredient = MealIngredient(
                meal_id=meal_id,
                name=generated_ingredient.name,
                quantity=generated_ingredient.quantity,
                unit=generated_ingredient.unit,
                calories_per_serving=generated_ingredient.calories_per_unit * generated_ingredient.quantity,
                protein_per_serving=generated_ingredient.protein_g_per_unit * generated_ingredient.quantity,
                carbs_per_serving=generated_ingredient.carbs_g_per_unit * generated_ingredient.quantity,
                fat_per_serving=generated_ingredient.fat_g_per_unit * generated_ingredient.quantity,
                alternatives=generated_ingredient.notes
            )
            
            db.add(meal_ingredient)
            ingredients_added += 1
            
            # Sumar a totales
            total_calories += meal_ingredient.calories_per_serving
            total_protein += meal_ingredient.protein_per_serving
            total_carbs += meal_ingredient.carbs_per_serving
            total_fat += meal_ingredient.fat_per_serving
        
        # Actualizar valores nutricionales de la comida si se solicita
        meal_updated = False
        if request.update_meal_nutrition:
            meal.calories = int(total_calories)
            meal.protein_g = total_protein
            meal.carbs_g = total_carbs
            meal.fat_g = total_fat
            meal_updated = True
        
        # Commit cambios
        db.commit()
        
        logger.info(f"✅ Aplicados {ingredients_added} ingredientes IA a meal {meal_id}")
        
        return ApplyIngredientsResponse(
            success=True,
            ingredients_added=ingredients_added,
            ingredients_replaced=ingredients_replaced,
            meal_updated=meal_updated,
            total_calories=total_calories if meal_updated else None,
            total_protein=total_protein if meal_updated else None,
            total_carbs=total_carbs if meal_updated else None,
            total_fat=total_fat if meal_updated else None
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error aplicando ingredientes IA: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error aplicando ingredientes: {str(e)}")


@router.get("/ai/test-connection")
async def test_ai_connection(
    current_user: Auth0User = Depends(get_current_user)
):
    """
    🔧 **Probar Conexión con OpenAI**
    
    **Descripción:**
    Endpoint de diagnóstico para verificar que la conexión con OpenAI
    está funcionando correctamente.
    
    **Uso:**
    - Verificar configuración de API key
    - Diagnosticar problemas de conectividad
    - Validar funcionamiento del servicio de IA
    
    **Response:**
    ```json
    {
      "success": true,
      "message": "Conexión OpenAI exitosa",
      "model": "gpt-4o-mini",
      "api_key_configured": true
    }
    ```
    """
    try:
        from app.services.nutrition_ai import get_nutrition_ai_service, NutritionAIError
        
        # Obtener servicio
        ai_service = get_nutrition_ai_service()
        
        # Probar conexión
        connection_ok = await ai_service.test_connection()
        
        if connection_ok:
            return {
                "success": True,
                "message": "Conexión OpenAI exitosa",
                "model": ai_service.model,
                "api_key_configured": bool(ai_service.settings.OPENAI_API_KEY)
            }
        else:
            return {
                "success": False,
                "message": "Error en conexión OpenAI",
                "model": ai_service.model,
                "api_key_configured": bool(ai_service.settings.OPENAI_API_KEY)
            }
            
    except NutritionAIError as e:
        return {
            "success": False,
            "message": f"Error de configuración: {str(e)}",
            "api_key_configured": False
        }
    except Exception as e:
        logger.error(f"Error en test de conexión IA: {str(e)}")
        return {
            "success": False,
            "message": f"Error inesperado: {str(e)}",
            "api_key_configured": False
        }


# ===== ENDPOINTS DE ANALYTICS =====

@router.get("/plans/{plan_id}/analytics", response_model=NutritionAnalytics)
def get_plan_analytics(
    plan_id: int = Path(..., description="ID del plan nutricional para analytics"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    📊 **Analytics del Plan Nutricional (Solo Creadores)**
    
    **Descripción:**
    Proporciona métricas detalladas sobre el rendimiento y engagement de un plan nutricional.
    Exclusivo para creadores/entrenadores que desean analizar el éxito de sus planes.
    
    **Métricas Principales:**
    
    **📈 Engagement:**
    - `total_followers`: Número total de usuarios que han seguido el plan
    - `active_followers`: Usuarios actualmente siguiendo el plan
    - `completion_rate`: Porcentaje promedio de completación de comidas
    - `average_days_followed`: Promedio de días que los usuarios siguen el plan
    - `dropout_rate`: Porcentaje de usuarios que abandona el plan
    
    **⭐ Satisfacción:**
    - `average_satisfaction`: Rating promedio de satisfacción (1-5)
    - `satisfaction_distribution`: Distribución de ratings
    - `most_popular_meals`: Comidas con mejores ratings
    - `least_popular_meals`: Comidas con peores ratings
    
    **🍽️ Comportamiento de Comidas:**
    - `meal_completion_by_type`: Completación por tipo (desayuno, almuerzo, etc.)
    - `meal_completion_by_day`: Completación por día del plan
    - `peak_completion_hours`: Horas cuando más se completan comidas
    - `photos_shared`: Número de fotos compartidas por usuarios
    
    **📅 Análisis Temporal:**
    - `daily_engagement`: Engagement día por día
    - `weekly_trends`: Tendencias semanales de actividad
    - `seasonal_patterns`: Patrones estacionales si aplicable
    - `retention_curve`: Curva de retención de usuarios
    
    **🎯 Datos Específicos por Tipo:**
    
    **Template Plans:**
    - Análisis de adopción individual
    - Patrones de inicio personalizados
    - Métricas de éxito a largo plazo
    
    **Live Plans:**
    - Análisis de participación grupal
    - Sincronización de actividad
    - Métricas de challenge grupal
    - Comparación con otros live plans
    
    **Archived Plans:**
    - Datos históricos preservados
    - Comparación con performance original
    - Métricas de reutilización como template
    
    **Ejemplo de Respuesta:**
    ```json
    {
      "plan_id": 123,
      "plan_title": "Challenge Detox 21 días",
      "plan_type": "live",
      "total_followers": 87,
      "active_followers": 23,
      "completion_rate": 78.5,
      "average_satisfaction": 4.2,
      "dropout_rate": 15.3,
      "meal_completion_by_type": {
        "breakfast": 85.2,
        "lunch": 78.9,
        "dinner": 71.4
      },
      "most_popular_meals": [
        {
          "meal_name": "Batido Verde",
          "satisfaction": 4.8,
          "completion_rate": 92.1
        }
      ],
      "daily_engagement": [
        {"day": 1, "completion_rate": 95.2},
        {"day": 2, "completion_rate": 89.1}
      ],
      "retention_curve": [
        {"day": 1, "active_users": 87},
        {"day": 7, "active_users": 78},
        {"day": 14, "active_users": 65}
      ]
    }
    ```
    
    **Permisos Estrictos:**
    - ✅ Solo el creador/entrenador del plan puede ver analytics
    - ❌ Usuarios regulares no tienen acceso a estos datos
    - ❌ Otros entrenadores no pueden ver analytics de planes ajenos
    
    **Casos de Uso:**
    - 📊 Evaluar éxito de planes creados
    - 🎯 Identificar áreas de mejora
    - 📈 Optimizar contenido futuro
    - 💡 Inspiración para nuevos planes
    - 🏆 Demostrar valor a clientes
    - 📝 Reportes de rendimiento
    
    **Insights Accionables:**
    - **Alta Dropout:** Revisar dificultad o contenido
    - **Baja Satisfacción:** Mejorar recetas específicas
    - **Patrones Temporales:** Optimizar timing de notificaciones
    - **Comidas Populares:** Replicar en futuros planes
    - **Días Problemáticos:** Reforzar contenido específico
    
    **Privacidad y Ética:**
    - Datos agregados y anonimizados
    - Sin información personal identificable
    - Cumple con regulaciones de privacidad
    - Enfoque en mejora de contenido
    
    **Códigos de Error:**
    - `403`: Solo el creador puede ver analytics del plan
    - `404`: Plan no encontrado o no pertenece al gimnasio
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
    """
    🎯 **Objetivos Nutricionales Disponibles**
    
    Obtiene lista de objetivos nutricionales para filtrado y creación de planes.
    Usado en formularios de creación y filtros de búsqueda.
    
    **Objetivos Disponibles:**
    - `loss`: Pérdida de peso
    - `gain`: Ganancia de peso
    - `bulk`: Volumen/masa muscular
    - `cut`: Definición muscular
    - `maintain`: Mantenimiento de peso
    
    **Formato de Respuesta:**
    ```json
    [
      {"value": "loss", "label": "Loss"},
      {"value": "gain", "label": "Gain"},
      {"value": "bulk", "label": "Bulk"},
      {"value": "cut", "label": "Cut"},
      {"value": "maintain", "label": "Maintain"}
    ]
    ```
    """
    return [{"value": goal.value, "label": goal.value.replace("_", " ").title()} 
            for goal in NutritionGoal]


@router.get("/enums/difficulty-levels")
def get_difficulty_levels():
    """
    ⚡ **Niveles de Dificultad Disponibles**
    
    Obtiene lista de niveles de dificultad para clasificación de planes.
    Ayuda a usuarios a encontrar planes apropiados para su experiencia.
    
    **Niveles Disponibles:**
    - `beginner`: Principiante (recetas simples, ingredientes básicos)
    - `intermediate`: Intermedio (técnicas moderadas, ingredientes diversos)
    - `advanced`: Avanzado (técnicas complejas, ingredientes especializados)
    
    **Formato de Respuesta:**
    ```json
    [
      {"value": "beginner", "label": "Beginner"},
      {"value": "intermediate", "label": "Intermediate"},
      {"value": "advanced", "label": "Advanced"}
    ]
    ```
    """
    return [{"value": level.value, "label": level.value.title()} 
            for level in DifficultyLevel]


@router.get("/enums/budget-levels")
def get_budget_levels():
    """
    💰 **Niveles de Presupuesto Disponibles**
    
    Obtiene lista de niveles de presupuesto para filtrado económico.
    Permite a usuarios encontrar planes dentro de su rango de gasto.
    
    **Niveles Disponibles:**
    - `low`: Bajo presupuesto (ingredientes económicos y accesibles)
    - `medium`: Presupuesto medio (balance entre calidad y precio)
    - `high`: Presupuesto alto (ingredientes premium y especializados)
    
    **Formato de Respuesta:**
    ```json
    [
      {"value": "low", "label": "Low"},
      {"value": "medium", "label": "Medium"},
      {"value": "high", "label": "High"}
    ]
    ```
    """
    return [{"value": level.value, "label": level.value.title()} 
            for level in BudgetLevel]


@router.get("/enums/dietary-restrictions")
def get_dietary_restrictions():
    """
    🚫 **Restricciones Dietéticas Disponibles**
    
    Obtiene lista de restricciones dietéticas para filtrado y personalización.
    Esencial para usuarios con necesidades alimentarias específicas.
    
    **Restricciones Disponibles:**
    - `vegetarian`: Vegetariano (sin carne)
    - `vegan`: Vegano (sin productos animales)
    - `gluten_free`: Sin gluten
    - `dairy_free`: Sin lácteos
    - `keto`: Dieta cetogénica
    - `paleo`: Dieta paleolítica
    - `low_carb`: Bajo en carbohidratos
    - `none`: Sin restricciones
    
    **Formato de Respuesta:**
    ```json
    [
      {"value": "vegetarian", "label": "Vegetarian"},
      {"value": "vegan", "label": "Vegan"},
      {"value": "gluten_free", "label": "Gluten Free"},
      {"value": "dairy_free", "label": "Dairy Free"}
    ]
    ```
    """
    return [{"value": restriction.value, "label": restriction.value.replace("_", " ").title()} 
            for restriction in DietaryRestriction]


@router.get("/enums/meal-types")
def get_meal_types():
    """
    🍽️ **Tipos de Comidas Disponibles**
    
    Obtiene lista de tipos de comidas para creación de contenido.
    Usado por creadores para estructurar días de planes nutricionales.
    
    **Tipos Disponibles:**
    - `breakfast`: Desayuno
    - `lunch`: Almuerzo
    - `dinner`: Cena
    - `snack_morning`: Snack de media mañana
    - `snack_afternoon`: Snack de media tarde
    - `snack_evening`: Snack nocturno
    
    **Formato de Respuesta:**
    ```json
    [
      {"value": "breakfast", "label": "Breakfast"},
      {"value": "lunch", "label": "Lunch"},
      {"value": "dinner", "label": "Dinner"},
      {"value": "snack_morning", "label": "Snack Morning"}
    ]
    ```
    """
    return [{"value": meal_type.value, "label": meal_type.value.replace("_", " ").title()} 
            for meal_type in MealType]


@router.get("/enums/plan-types")
def get_plan_types():
    """
    📋 **Tipos de Planes Disponibles (Sistema Híbrido)**
    
    Obtiene lista de tipos de planes del sistema híbrido.
    Fundamental para entender las opciones disponibles.
    
    **Tipos Disponibles:**
    - `template`: Plan individual, cada usuario inicia cuando quiere
    - `live`: Plan grupal sincronizado, fecha fija para todos
    - `archived`: Plan histórico, creado desde lives terminados
    
    **Formato de Respuesta:**
    ```json
    [
      {"value": "template", "label": "Template"},
      {"value": "live", "label": "Live"},
      {"value": "archived", "label": "Archived"}
    ]
    ```
    """
    return [{"value": plan_type.value, "label": plan_type.value.title()} 
            for plan_type in PlanType]


@router.get("/enums/plan-statuses")
def get_plan_statuses():
    """
    📊 **Estados de Planes Disponibles**
    
    Obtiene lista de estados posibles para planes nutricionales.
    Usado para filtrado y visualización de estado actual.
    
    **Estados Disponibles:**
    - `not_started`: No iniciado (plan live futuro o usuario no ha empezado)
    - `running`: En ejecución (plan activo y usuario participando)
    - `finished`: Terminado (plan completado exitosamente)
    - `archived`: Archivado (plan live convertido a template)
    
    **Formato de Respuesta:**
    ```json
    [
      {"value": "not_started", "label": "Not Started"},
      {"value": "running", "label": "Running"},
      {"value": "finished", "label": "Finished"},
      {"value": "archived", "label": "Archived"}
    ]
    ```
    """
    return [{"value": status.value, "label": status.value.replace("_", " ").title()} 
            for status in PlanStatus]


# ===== NUEVOS ENDPOINTS DEL SISTEMA HÍBRIDO =====

@router.get("/plans/hybrid", response_model=NutritionPlanListResponseHybrid)
def list_plans_by_type(
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Página para paginación general"),
    per_page: int = Query(20, ge=1, le=100, description="Elementos por página"),
):
    """
    🔀 **Lista de Planes Categorizados (Vista Híbrida)**
    
    **Descripción:**
    Obtiene planes organizados por categorías del sistema híbrido.
    Ideal para interfaces que necesitan mostrar planes separados por tipo.
    
    **Organización por Categorías:**
    
    **🔴 Live Plans (Challenges Grupales):**
    - Planes sincronizados con fecha fija
    - Todos los usuarios empiezan al mismo tiempo
    - Estado compartido entre participantes
    - Contador de participantes en tiempo real
    - Información de días hasta inicio
    
    **📋 Template Plans (Planes Individuales):**
    - Planes que cada usuario inicia cuando quiere
    - Progreso personal e independiente
    - Disponibles permanentemente
    - Estadísticas de popularidad
    
    **📚 Archived Plans (Históricos):**
    - Planes live exitosos convertidos a templates
    - Datos originales preservados
    - Información de performance histórica
    - Reutilizables como planes individuales
    
    **Información Específica por Tipo:**
    
    **Para Live Plans:**
    - `live_participants_count`: Participantes actuales
    - `is_live_active`: Si está actualmente activo
    - `days_until_start`: Días restantes hasta inicio
    - `status`: not_started, running, finished
    
    **Para Template Plans:**
    - `total_followers`: Total de usuarios que lo han seguido
    - `avg_satisfaction`: Rating promedio de satisfacción
    - `is_followed_by_user`: Si el usuario actual lo sigue
    
    **Para Archived Plans:**
    - `original_participants_count`: Participantes del live original
    - `archived_at`: Fecha de archivado
    - `original_live_plan_id`: ID del plan live original
    
    **Ejemplo de Respuesta:**
    ```json
    {
      "live_plans": [
        {
          "id": 123,
          "title": "Challenge Detox Enero",
          "plan_type": "live",
          "live_participants_count": 87,
          "is_live_active": true,
          "days_until_start": 0,
          "status": "running",
          "current_day": 5
        }
      ],
      "template_plans": [
        {
          "id": 456,
          "title": "Plan Pérdida Peso 30 días",
          "plan_type": "template",
          "total_followers": 234,
          "avg_satisfaction": 4.2,
          "is_followed_by_user": false
        }
      ],
      "archived_plans": [
        {
          "id": 789,
          "title": "Challenge Verano Exitoso",
          "plan_type": "archived",
          "original_participants_count": 156,
          "archived_at": "2023-09-15T00:00:00Z",
          "total_followers": 45
        }
      ],
      "total": 3,
      "page": 1,
      "per_page": 20,
      "has_next": false,
      "has_prev": false
    }
    ```
    
    **Casos de Uso:**
    - 🏠 Pantalla principal con secciones separadas
    - 🎯 Navegación por tipo de experiencia deseada
    - 📊 Dashboard administrativo categorizado
    - 🔍 Exploración organizada de contenido
    - 📱 Tabs o secciones en apps móviles
    
    **Ventajas de esta Vista:**
    - **Claridad:** Separación clara de tipos de planes
    - **Contexto:** Información relevante por categoría
    - **UX:** Facilita decisión del usuario
    - **Performance:** Cargas optimizadas por tipo
    - **Filtrado:** Pre-filtrado automático
    
    **Limitaciones de Paginación:**
    - Cada categoría está limitada a 50 elementos máximo
    - Paginación general afecta el total combinado
    - Para listas extensas, usar endpoints específicos por tipo
    
    **Comparación con GET /plans:**
    - **GET /plans:** Lista unificada con filtros flexibles
    - **GET /plans/hybrid:** Vista categorizada pre-organizada
    - **Uso recomendado:** Hybrid para dashboards, /plans para búsquedas
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
    plan_id: int = Path(..., description="ID del plan para obtener estado actual"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    📊 **Estado Actual del Plan (Información en Tiempo Real)**
    
    **Descripción:**
    Obtiene el estado actual detallado de un plan específico para el usuario.
    Información dinámica que se actualiza en tiempo real según el tipo de plan.
    
    **Información de Estado Incluida:**
    
    **📅 Estado Temporal:**
    - `current_day`: Día actual del plan (calculado según tipo)
    - `status`: Estado actual (not_started, running, finished)
    - `days_until_start`: Días restantes hasta inicio (solo para live futuros)
    
    **🔄 Estado del Plan:**
    - `plan_type`: Tipo de plan (template, live, archived)
    - `is_live_active`: Si un plan live está actualmente activo
    - `live_participants_count`: Número actual de participantes (live plans)
    
    **👤 Estado del Usuario:**
    - `is_following`: Si el usuario actual está siguiendo el plan
    - `user_start_date`: Cuándo empezó el usuario (si está siguiendo)
    - `user_progress`: Progreso personal del usuario
    
    **Cálculo de `current_day` por Tipo:**
    
    **Template/Archived Plans:**
    ```
    current_day = días_desde_que_usuario_empezó + 1
    Ejemplo: Usuario empezó hace 14 días → current_day = 15
    ```
    
    **Live Plans:**
    ```
    current_day = días_desde_fecha_global_del_plan + 1
    Ejemplo: Plan empezó hace 4 días → current_day = 5 (para todos)
    ```
    
    **Estados Posibles:**
    - **not_started**: Usuario no ha empezado o plan live futuro
    - **running**: Plan activo y usuario participando
    - **finished**: Plan completado (duración alcanzada)
    
    **Ejemplo de Respuesta - Plan Live Activo:**
    ```json
    {
      "plan_id": 123,
      "plan_type": "live",
      "current_day": 5,
      "status": "running",
      "days_until_start": 0,
      "is_live_active": true,
      "live_participants_count": 87,
      "is_following": true,
      "user_start_date": "2024-01-10T00:00:00Z",
      "user_progress": {
        "meals_completed_today": 2,
        "total_meals_today": 3,
        "completion_percentage": 66.7
      }
    }
    ```
    
    **Ejemplo de Respuesta - Plan Live Futuro:**
    ```json
    {
      "plan_id": 456,
      "plan_type": "live",
      "current_day": 0,
      "status": "not_started",
      "days_until_start": 7,
      "is_live_active": false,
      "live_participants_count": 23,
      "is_following": true,
      "user_start_date": null
    }
    ```
    
    **Ejemplo de Respuesta - Template Plan:**
    ```json
    {
      "plan_id": 789,
      "plan_type": "template",
      "current_day": 12,
      "status": "running",
      "days_until_start": null,
      "is_live_active": null,
      "live_participants_count": null,
      "is_following": true,
      "user_start_date": "2024-01-03T00:00:00Z",
      "user_progress": {
        "total_days_completed": 11,
        "overall_completion_rate": 78.5
      }
    }
    ```
    
    **Actualizaciones Automáticas:**
    - Estados de planes live se actualizan automáticamente
    - Contadores de participantes en tiempo real
    - Verificación de fechas de finalización
    - Cálculo dinámico de días transcurridos
    
    **Casos de Uso:**
    - 📱 Widgets de estado en tiempo real
    - 🔔 Triggers para notificaciones
    - 📊 Dashboards de progreso
    - 🎯 Lógica condicional en frontend
    - ⏰ Cálculo de elementos dependientes del tiempo
    
    **Optimización:**
    - Endpoint ligero optimizado para llamadas frecuentes
    - Cálculos eficientes en tiempo real
    - Datos mínimos necesarios para estado
    - Cache-friendly para polling
    
    **Permisos:**
    - ✅ Cualquier usuario puede ver estado de planes públicos
    - 🔒 Planes privados solo creador y seguidores
    - 📊 Información de progreso solo para seguidores
    
    **Códigos de Error:**
    - `403`: Sin acceso a plan privado
    - `404`: Plan no encontrado o no pertenece al gimnasio
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


# ============================================================================
# ENDPOINTS DE NOTIFICACIONES
# ============================================================================

@router.get(
    "/notifications/settings",
    response_model=Dict[str, Any],
    summary="Obtener configuración de notificaciones",
    description="""
    Obtiene la configuración de notificaciones del usuario para todos sus planes activos.

    **Información Devuelta:**
    - Configuración global de notificaciones
    - Horarios personalizados por tipo de comida
    - Planes con notificaciones activas

    **Permisos:**
    - Usuario autenticado
    """
)
def get_notification_settings(
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access)
) -> Dict[str, Any]:
    """Obtener configuración de notificaciones del usuario"""
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Obtener planes activos del usuario
    from app.models.nutrition import NutritionPlanFollower, NutritionPlan

    active_followers = db.query(NutritionPlanFollower).join(
        NutritionPlan
    ).filter(
        NutritionPlanFollower.user_id == db_user.id,
        NutritionPlanFollower.is_active == True,
        NutritionPlan.gym_id == current_gym.id
    ).all()

    # Si no hay planes activos, devolver configuración por defecto
    if not active_followers:
        return {
            "has_active_plans": False,
            "global_enabled": True,
            "default_times": {
                "breakfast": "08:00",
                "lunch": "13:00",
                "dinner": "20:00"
            },
            "active_plans": []
        }

    # Obtener configuración del primer plan activo (asumimos que todos tienen la misma)
    primary_config = active_followers[0]

    # Listar todos los planes con su configuración
    plans_config = []
    for follower in active_followers:
        plan = db.query(NutritionPlan).filter(
            NutritionPlan.id == follower.plan_id
        ).first()

        plans_config.append({
            "plan_id": plan.id,
            "plan_title": plan.title,
            "plan_type": plan.plan_type,
            "notifications_enabled": follower.notifications_enabled,
            "notification_times": {
                "breakfast": follower.notification_time_breakfast,
                "lunch": follower.notification_time_lunch,
                "dinner": follower.notification_time_dinner
            }
        })

    return {
        "has_active_plans": True,
        "global_enabled": primary_config.notifications_enabled,
        "default_times": {
            "breakfast": primary_config.notification_time_breakfast,
            "lunch": primary_config.notification_time_lunch,
            "dinner": primary_config.notification_time_dinner
        },
        "active_plans": plans_config
    }


@router.put(
    "/notifications/settings",
    response_model=Dict[str, Any],
    summary="Actualizar configuración de notificaciones",
    description="""
    Actualiza la configuración de notificaciones para los planes del usuario.

    **Opciones de Configuración:**
    - Habilitar/deshabilitar notificaciones globalmente
    - Configurar horarios por tipo de comida (formato HH:MM)
    - Aplicar a todos los planes o a uno específico

    **Horarios Válidos:**
    - Formato 24 horas: "08:00", "13:30", "20:15"
    - Rango: 00:00 a 23:59

    **Permisos:**
    - Usuario autenticado
    - Solo puede modificar sus propias notificaciones
    """
)
def update_notification_settings(
    settings: Dict[str, Any],
    plan_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access)
) -> Dict[str, Any]:
    """Actualizar configuración de notificaciones"""
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Validar formato de horarios si se proporcionan
    import re
    time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')

    notification_times = settings.get("notification_times", {})
    for meal_type, time_str in notification_times.items():
        if time_str and not time_pattern.match(time_str):
            raise HTTPException(
                status_code=400,
                detail=f"Formato de hora inválido para {meal_type}: {time_str}. Use formato HH:MM"
            )

    from app.models.nutrition import NutritionPlanFollower, NutritionPlan

    # Si se especifica un plan, actualizar solo ese
    if plan_id:
        # Verificar que el plan existe y pertenece al gimnasio
        plan = db.query(NutritionPlan).filter(
            NutritionPlan.id == plan_id,
            NutritionPlan.gym_id == current_gym.id
        ).first()

        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado")

        # Obtener la relación follower
        follower = db.query(NutritionPlanFollower).filter(
            NutritionPlanFollower.plan_id == plan_id,
            NutritionPlanFollower.user_id == db_user.id,
            NutritionPlanFollower.is_active == True
        ).first()

        if not follower:
            raise HTTPException(status_code=404, detail="No estás siguiendo este plan")

        # Actualizar configuración
        if "enabled" in settings:
            follower.notifications_enabled = settings["enabled"]

        if "notification_times" in settings:
            times = settings["notification_times"]
            if "breakfast" in times:
                follower.notification_time_breakfast = times["breakfast"]
            if "lunch" in times:
                follower.notification_time_lunch = times["lunch"]
            if "dinner" in times:
                follower.notification_time_dinner = times["dinner"]

        db.commit()

        return {
            "success": True,
            "message": f"Configuración actualizada para el plan: {plan.title}",
            "plan_id": plan_id,
            "updated_settings": {
                "enabled": follower.notifications_enabled,
                "notification_times": {
                    "breakfast": follower.notification_time_breakfast,
                    "lunch": follower.notification_time_lunch,
                    "dinner": follower.notification_time_dinner
                }
            }
        }

    else:
        # Actualizar todos los planes activos del usuario
        active_followers = db.query(NutritionPlanFollower).join(
            NutritionPlan
        ).filter(
            NutritionPlanFollower.user_id == db_user.id,
            NutritionPlanFollower.is_active == True,
            NutritionPlan.gym_id == current_gym.id
        ).all()

        if not active_followers:
            raise HTTPException(status_code=404, detail="No tienes planes activos")

        updated_count = 0
        for follower in active_followers:
            if "enabled" in settings:
                follower.notifications_enabled = settings["enabled"]

            if "notification_times" in settings:
                times = settings["notification_times"]
                if "breakfast" in times:
                    follower.notification_time_breakfast = times["breakfast"]
                if "lunch" in times:
                    follower.notification_time_lunch = times["lunch"]
                if "dinner" in times:
                    follower.notification_time_dinner = times["dinner"]

            updated_count += 1

        db.commit()

        return {
            "success": True,
            "message": f"Configuración actualizada para {updated_count} planes",
            "plans_updated": updated_count,
            "updated_settings": settings
        }


@router.post(
    "/notifications/test",
    response_model=Dict[str, Any],
    summary="Enviar notificación de prueba",
    description="""
    Envía una notificación de prueba al usuario para verificar que las notificaciones están funcionando.

    **Tipos de Prueba:**
    - meal_reminder: Recordatorio de comida
    - achievement: Logro desbloqueado
    - daily_plan: Plan del día

    **Permisos:**
    - Usuario autenticado
    """
)
def send_test_notification(
    notification_type: str = "meal_reminder",
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access)
) -> Dict[str, Any]:
    """Enviar notificación de prueba"""
    from app.services.nutrition_notification_service import nutrition_notification_service

    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Validar tipo de notificación
    valid_types = ["meal_reminder", "achievement", "daily_plan"]
    if notification_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de notificación inválido. Opciones: {', '.join(valid_types)}"
        )

    try:
        success = False

        if notification_type == "meal_reminder":
            success = nutrition_notification_service.send_meal_reminder(
                db=db,
                user_id=db_user.id,
                meal_type="lunch",
                meal_name="Comida de Prueba",
                plan_title="Plan de Prueba",
                gym_id=current_gym.id
            )

        elif notification_type == "achievement":
            success = nutrition_notification_service.send_achievement_notification(
                db=db,
                user_id=db_user.id,
                achievement_type="week_streak",
                gym_id=current_gym.id
            )

        elif notification_type == "daily_plan":
            # Simular notificación de plan diario
            from app.services.notification_service import notification_service
            result = notification_service.send_to_users(
                user_ids=[str(db_user.id)],
                title="📋 Notificación de Prueba",
                message="Tu sistema de notificaciones está funcionando correctamente",
                data={
                    "type": "test",
                    "notification_type": notification_type
                },
                db=db
            )
            success = result.get("success", False)

        if success:
            return {
                "success": True,
                "message": "Notificación de prueba enviada exitosamente",
                "notification_type": notification_type
            }
        else:
            return {
                "success": False,
                "message": "No se pudo enviar la notificación. Verifica que tengas la app instalada y las notificaciones habilitadas",
                "notification_type": notification_type
            }

    except Exception as e:
        logger.error(f"Error sending test notification: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error al enviar la notificación de prueba"
        )



@router.get(
    "/notifications/analytics",
    response_model=Dict[str, Any],
    summary="Obtener analytics de notificaciones",
    description="""
    Obtiene estadísticas de notificaciones enviadas en los últimos días.

    **Métricas Disponibles:**
    - Total de notificaciones enviadas y fallidas
    - Tasa de éxito
    - Desglose por tipo de comida
    - Tendencia diaria

    **Permisos:**
    - Solo administradores y entrenadores
    """
)
def get_notifications_analytics(
    days: int = Query(default=7, ge=1, le=30, description="Número de días a analizar"),
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access)
) -> Dict[str, Any]:
    """Obtener analytics de notificaciones de nutrición"""
    from app.services.nutrition_notification_service import get_notification_analytics

    # Obtener analytics
    analytics = get_notification_analytics(current_gym.id, days)

    return analytics


@router.get(
    "/notifications/status",
    response_model=Dict[str, Any],
    summary="Obtener estado de notificaciones del usuario",
    description="""
    Obtiene el estado de notificaciones del usuario actual.

    **Información Devuelta:**
    - Notificaciones enviadas hoy por tipo de comida
    - Última notificación recibida
    - Días de racha

    **Permisos:**
    - Usuario autenticado
    """
)
def get_my_notification_status(
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access)
) -> Dict[str, Any]:
    """Obtener estado de notificaciones del usuario"""
    from app.services.nutrition_notification_service import get_user_notification_status

    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Obtener estado
    status = get_user_notification_status(db_user.id, current_gym.id)

    return status


# ============================================================================
# ENDPOINTS DE AUDITORÍA (Solo Admin/Trainer)
# ============================================================================

@router.get(
    "/notifications/audit",
    response_model=Dict[str, Any],
    summary="Obtener log de auditoría de notificaciones",
    description="Obtiene el historial de notificaciones enviadas. Solo Admin/Trainer."
)
async def get_audit_log(
    limit: int = Query(100, ge=1, le=500, description="Número máximo de entradas"),
    user_id: Optional[int] = Query(None, description="Filtrar por usuario específico"),
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access)
) -> Dict[str, Any]:
    """
    Obtener log de auditoría de notificaciones.

    Solo accesible por Admin y Trainer.
    Muestra las últimas N notificaciones enviadas con detalles.
    """
    from app.services.nutrition_notification_service import get_notification_audit_log

    # Verificar permisos (admin o trainer)
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user_gym = user_service.get_user_gym(db, db_user.id, current_gym.id)
    if not user_gym or user_gym.role not in ["admin", "trainer"]:
        raise HTTPException(
            status_code=403,
            detail="Solo administradores y entrenadores pueden ver la auditoría"
        )

    # Obtener auditoría
    audit_log = get_notification_audit_log(
        gym_id=current_gym.id,
        limit=limit,
        user_id=user_id
    )

    return audit_log


@router.get(
    "/notifications/audit/summary",
    response_model=Dict[str, Any],
    summary="Obtener resumen de auditoría",
    description="Obtiene un resumen de las notificaciones de las últimas N horas."
)
async def get_audit_summary(
    hours: int = Query(24, ge=1, le=168, description="Número de horas a analizar"),
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access)
) -> Dict[str, Any]:
    """
    Obtener resumen de auditoría de las últimas N horas.

    Incluye:
    - Total de notificaciones
    - Desglose por estado (sent, queued, failed)
    - Desglose por tipo de notificación
    - Número de usuarios únicos notificados
    """
    from app.services.nutrition_notification_service import get_notification_audit_summary

    # Verificar permisos (admin o trainer)
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user_gym = user_service.get_user_gym(db, db_user.id, current_gym.id)
    if not user_gym or user_gym.role not in ["admin", "trainer"]:
        raise HTTPException(
            status_code=403,
            detail="Solo administradores y entrenadores pueden ver la auditoría"
        )

    # Obtener resumen
    summary = get_notification_audit_summary(
        gym_id=current_gym.id,
        hours=hours
    )

    return summary
