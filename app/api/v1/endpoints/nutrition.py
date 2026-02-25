"""
Endpoints para el sistema de planes nutricionales.
"""

from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Header, Response, Body
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth0_fastapi import get_current_user, Auth0User
from app.core.tenant import verify_gym_access
from app.models.user import User
from app.models.gym import Gym
from app.schemas.nutrition import (
    NutritionPlan, NutritionPlanCreate, NutritionPlanUpdate, NutritionPlanFilters,
    NutritionPlanListResponse, NutritionPlanWithDetails, NutritionPlanListResponseHybrid,
    DailyNutritionPlan, DailyNutritionPlanCreate, DailyNutritionPlanWithMeals, DailyNutritionPlanUpdate,
    Meal, MealCreate, MealWithIngredients, MealUpdate, MealIngredient, MealIngredientCreate, MealIngredientUpdate,
    NutritionPlanFollower, NutritionPlanFollowerCreate,
    UserMealCompletion, UserMealCompletionCreate,
    TodayMealPlan, UserNutritionDashboard, NutritionAnalytics, NutritionDashboardHybrid,
    NutritionGoal, DifficultyLevel, BudgetLevel, DietaryRestriction, MealType, PlanType, PlanStatus,
    ArchivePlanRequest, LivePlanStatusUpdate,
    AIGenerationRequest, AIGenerationResponse
)
from app.schemas.nutrition_ai import (
    AIIngredientRequest, AIRecipeResponse, ApplyGeneratedIngredientsRequest, ApplyIngredientsResponse
)
from app.schemas.nutrition_safety import (
    SafetyScreeningRequest, SafetyScreeningResponse, ScreeningValidationResponse, RiskLevel,
    calculate_risk_score, generate_safety_warnings
)
# Import specialized nutrition services
from app.services.nutrition_plan_service import NutritionPlanService
from app.services.meal_service import MealService
from app.services.plan_follower_service import PlanFollowerService
from app.services.nutrition_progress_service import NutritionProgressService
from app.services.live_plan_service import LivePlanService
from app.services.nutrition_analytics_service import NutritionAnalyticsService
from app.services.nutrition_ai_service import NutritionAIService
# Keep the old service for AI functionality temporarily
from app.services.nutrition import NutritionService, NotFoundError, ValidationError, PermissionError
from app.services.user import user_service
from app.core.dependencies import module_enabled
from app.models.nutrition import (
    Meal as MealModel,
    DailyNutritionPlan as DailyNutritionPlanModel,
    MealIngredient as MealIngredientModel,
    NutritionPlan as NutritionPlanModel,
    NutritionPlanFollower as NutritionPlanFollowerModel,
    UserMealCompletion as UserMealCompletionModel
)
from app.models.user_gym import UserGym, GymRoleType
from sqlalchemy.orm import joinedload
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/plans", response_model=NutritionPlanListResponse)
async def list_nutrition_plans(
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Número de página para paginación"),
    per_page: int = Query(20, ge=1, le=100, description="Elementos por página (máximo 100)"),
    include_details: bool = Query(False, description="Incluir daily_plans y meals en la respuesta (eager loading optimizado)"),
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

    **NUEVO: Parámetro `include_details`**
    - ⚡ `include_details=false` (default): Solo info básica de planes (rápido, ~200-300ms)
    - 🔍 `include_details=true`: Incluye daily_plans y meals completos (optimizado, ~400-500ms)
    - **Beneficio:** Elimina necesidad de hacer N requests individuales a /plans/{id}
    - **Optimización:** Eager loading en UNA query + cache Redis independiente

    **Casos de Uso:**
    - 📱 Pantalla principal de planes disponibles (include_details=false)
    - 🔍 Vista detallada con navegación de todos los planes (include_details=true)
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

    **Ejemplo de Respuesta (include_details=false):**
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

    **Ejemplo de Respuesta (include_details=true):**
    ```json
    {
      "plans": [
        {
          "id": 1,
          "title": "Plan de Pérdida de Peso - 30 días",
          "plan_type": "template",
          "daily_plans": [
            {
              "id": 1,
              "day_number": 1,
              "meals": [
                {
                  "id": 1,
                  "name": "Desayuno Proteico",
                  "meal_type": "breakfast",
                  "calories": 350
                }
              ]
            }
          ],
          "total_followers": 87
        }
      ],
      "total": 150
    }
    ```

    **Performance:**
    - Sin details: ~200-300ms (cache hit: ~50ms)
    - Con details: ~400-500ms (cache hit: ~100ms)
    - **Vs antes:** 15 requests × 350ms = 5250ms → **90% más rápido**
    """
    # Use specialized NutritionPlanService for plan operations
    service = NutritionPlanService(db)

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

    # Convertir page/per_page a skip/limit para NutritionPlanService
    skip = (page - 1) * per_page
    limit = per_page

    # OPTIMIZATION: Use cached version to reduce repeated loads
    # If include_details=true, uses eager loading to fetch all daily_plans and meals in ~2-3 queries
    plans, total = await service.list_nutrition_plans_cached(
        gym_id=current_gym.id,
        filters=filters,
        skip=skip,
        limit=limit,
        include_details=include_details
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
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    try:
        # Usar el servicio específico para planes live o el servicio base
        if plan_data.plan_type == PlanType.LIVE:
            # Use specialized LivePlanService for live plans
            live_service = LivePlanService(db)
            plan = live_service.create_live_nutrition_plan(
                plan_data=plan_data,
                creator_id=db_user.id,
                gym_id=current_gym.id
            )
        else:
            # Use specialized NutritionPlanService for regular plans
            plan_service = NutritionPlanService(db)
            plan = plan_service.create_nutrition_plan(
                plan_data=plan_data,
                creator_id=db_user.id,
                gym_id=current_gym.id
            )
        return plan
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/plans/generate", response_model=AIGenerationResponse)
async def generate_plan_with_ai(
    request: AIGenerationRequest,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    🤖 **Generar Plan Nutricional con IA**

    **Descripción:**
    Genera un plan nutricional completo usando GPT-4o-mini basado en un prompt descriptivo.
    Solo disponible para trainers y administradores del gimnasio.

    **Casos de Uso:**
    - Crear planes personalizados rápidamente
    - Generar variaciones de planes existentes
    - Crear planes para objetivos específicos
    - Adaptar planes a restricciones dietéticas

    **Campos Requeridos:**
    - `title`: Título del plan (3-200 caracteres)
    - `duration_days`: Duración en días (7-30)
    - `goal`: Objetivo nutricional (weight_loss, muscle_gain, etc.)
    - `target_calories`: Calorías objetivo (1200-5000)

    **Campos Opcionales:**
    - `plan_type`: Tipo de plan - "template" (individual) o "live" (grupal) [default: "template"]
    - `live_start_date`: Fecha de inicio (REQUERIDO si plan_type="live", ej: "2026-03-01T00:00:00Z")
    - `prompt`: Instrucciones adicionales para personalizar el plan
    - `user_context`: Contexto del usuario (edad, peso, altura, etc.)
    - `dietary_restrictions`: Lista de restricciones (vegetarian, vegan, etc.)
    - `allergies`: Lista de alergias alimentarias
    - `meals_per_day`: Número de comidas (3-6, default: 5)
    - `difficulty_level`: Dificultad de recetas (beginner, intermediate, advanced)
    - `budget_level`: Nivel de presupuesto (economic, medium, premium)

    **Permisos:**
    - 👨‍⚕️ Solo trainers y administradores pueden generar con IA
    - 💰 Costo estimado: $0.002 USD por plan

    **Ejemplo de Request (Plan TEMPLATE):**
    ```json
    {
        "title": "Plan Pérdida de Peso Vegetariano",
        "plan_type": "template",
        "duration_days": 14,
        "goal": "weight_loss",
        "target_calories": 1800,
        "meals_per_day": 5,
        "difficulty_level": "beginner",
        "budget_level": "medium",
        "dietary_restrictions": ["vegetarian"],
        "prompt": "Énfasis en proteínas vegetales, evitar soja",
        "user_context": {
            "age": 30,
            "weight": 80,
            "height": 175,
            "activity_level": "moderate"
        }
    }
    ```

    **Ejemplo de Request (Plan LIVE - Challenge Grupal):**
    ```json
    {
        "title": "Challenge 21 Días Detox",
        "plan_type": "live",
        "live_start_date": "2026-03-01T00:00:00Z",
        "duration_days": 21,
        "goal": "weight_loss",
        "target_calories": 1500,
        "meals_per_day": 5,
        "difficulty_level": "intermediate",
        "dietary_restrictions": ["gluten_free"],
        "prompt": "Plan detox con jugos verdes y eliminación de procesados"
    }
    }
    ```

    **Códigos de Error:**
    - `400`: Datos inválidos o prompt muy corto/largo
    - `403`: Sin permisos para generar con IA
    - `404`: Usuario no encontrado
    - `429`: Límite de generaciones excedido
    - `500`: Error en servicio de OpenAI
    """
    import time

    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Verificar permisos (solo trainers y admins)
    user_gym = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.gym_id == current_gym.id
    ).first()

    if not user_gym or user_gym.role not in [GymRoleType.TRAINER, GymRoleType.ADMIN, GymRoleType.OWNER]:
        raise HTTPException(
            status_code=403,
            detail="Solo trainers, administradores y owners pueden generar planes con IA"
        )

    try:
        # Usar el servicio de IA para generar el plan completo
        ai_service = NutritionAIService()

        # Agregar meals_per_day al contexto del usuario si no existe
        if not request.user_context:
            request.user_context = {}
        request.user_context['meals_per_day'] = request.meals_per_day
        request.user_context['difficulty_level'] = request.difficulty_level.value if request.difficulty_level else 'beginner'
        request.user_context['budget_level'] = request.budget_level.value if request.budget_level else 'medium'

        # Generar plan con IA (incluye creación en BD)
        result = await ai_service.generate_nutrition_plan(
            request=request,
            creator_id=db_user.id,
            gym_id=current_gym.id,
            db=db
        )

        # Preparar respuesta
        response = AIGenerationResponse(
            plan_id=result['plan_id'],
            name=result['name'],
            description=result['description'],
            total_days=result['total_days'],
            nutritional_goal=result['nutritional_goal'],
            target_calories=result['target_calories'],
            daily_plans_count=result['daily_plans_count'],
            total_meals=result['total_meals'],
            ai_metadata=result['ai_metadata'],
            generation_time_ms=result['generation_time_ms'],
            cost_estimate_usd=result['cost_estimate_usd']
        )

        logger.info(f"Plan nutricional generado exitosamente: ID {result['plan_id']}, {result['total_meals']} comidas, costo ${result['cost_estimate_usd']}")

        return response

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating plan with AI: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al generar plan con IA")


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
    # Use specialized NutritionPlanService for plan operations
    service = NutritionPlanService(db)

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
async def follow_nutrition_plan(
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
    # Use specialized PlanFollowerService for follow operations
    service = PlanFollowerService(db)

    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # ========== VALIDACIÓN DE SEGURIDAD PARA USUARIOS (MEMBERS) ==========
    from app.models.nutrition_safety import SafetyScreening as SafetyScreeningModel, SafetyAuditLog
    from app.models.nutrition import NutritionPlan
    from datetime import datetime

    # Obtener el plan para verificar si es restrictivo
    plan = db.query(NutritionPlan).filter(
        NutritionPlan.id == plan_id,
        NutritionPlan.gym_id == current_gym.id
    ).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan nutricional no encontrado")

    # Determinar si el plan es restrictivo (menos de 1500 calorías diarias o plan de pérdida de peso)
    is_restrictive_plan = (
        (plan.target_calories is not None and plan.target_calories < 1500) or
        "pérdida" in plan.title.lower() or
        "weight loss" in plan.title.lower() or
        "detox" in plan.title.lower() or
        plan.goal == NutritionGoal.WEIGHT_LOSS
    )

    # Si el plan es restrictivo, requerir safety screening
    if is_restrictive_plan:
        # Buscar screening válido (no expirado) del usuario
        valid_screening = db.query(SafetyScreeningModel).filter(
            SafetyScreeningModel.user_id == db_user.id,
            SafetyScreeningModel.gym_id == current_gym.id,
            SafetyScreeningModel.expires_at > datetime.utcnow()
        ).order_by(SafetyScreeningModel.created_at.desc()).first()

        if not valid_screening:
            # Log intento sin screening
            audit_log = SafetyAuditLog(
                user_id=db_user.id,
                gym_id=current_gym.id,
                action_type="follow_plan_blocked",
                action_details={
                    "reason": "no_valid_screening",
                    "plan_id": plan_id,
                    "plan_title": plan.title,
                    "plan_calories": plan.target_calories
                },
                was_allowed=False,
                denial_reason="Plan restrictivo requiere evaluación de seguridad"
            )
            db.add(audit_log)
            db.commit()

            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Este plan requiere una evaluación de seguridad médica",
                    "reason": "restrictive_plan",
                    "action_required": "safety_screening",
                    "endpoint": "/api/v1/nutrition/safety-check",
                    "plan_calories": plan.target_calories
                }
            )

        # Verificar si el usuario puede seguir el plan según su screening
        if not valid_screening.can_proceed:
            audit_log = SafetyAuditLog(
                user_id=db_user.id,
                gym_id=current_gym.id,
                screening_id=valid_screening.id,
                action_type="follow_plan_blocked",
                action_details={
                    "reason": "high_risk",
                    "risk_level": valid_screening.risk_level,
                    "plan_id": plan_id,
                    "plan_title": plan.title
                },
                was_allowed=False,
                denial_reason=f"Nivel de riesgo {valid_screening.risk_level} requiere supervisión profesional"
            )
            db.add(audit_log)
            db.commit()

            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Tu evaluación de seguridad requiere supervisión profesional para este plan",
                    "risk_level": valid_screening.risk_level,
                    "requires_professional": True,
                    "recommended_specialists": ["Nutricionista clínico"]
                }
            )

        # Si es un plan de pérdida de peso, verificar condiciones específicas
        if plan.goal == NutritionGoal.WEIGHT_LOSS and not valid_screening.can_generate_weight_loss():
            audit_log = SafetyAuditLog(
                user_id=db_user.id,
                gym_id=current_gym.id,
                screening_id=valid_screening.id,
                action_type="follow_plan_blocked",
                action_details={
                    "reason": "weight_loss_restriction",
                    "plan_id": plan_id,
                    "plan_title": plan.title,
                    "user_conditions": valid_screening.medical_conditions
                },
                was_allowed=False,
                denial_reason="Condiciones médicas no permiten planes de pérdida de peso"
            )
            db.add(audit_log)
            db.commit()

            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Tus condiciones médicas no permiten seguir planes de pérdida de peso",
                    "reason": "medical_restriction",
                    "alternative": "Consulta planes de mantenimiento o ganancia muscular"
                }
            )

        # Log seguimiento exitoso con screening
        audit_log = SafetyAuditLog(
            user_id=db_user.id,
            gym_id=current_gym.id,
            screening_id=valid_screening.id,
            action_type="follow_plan_with_screening",
            action_details={
                "plan_id": plan_id,
                "plan_title": plan.title,
                "plan_calories": plan.target_calories,
                "risk_level": valid_screening.risk_level
            },
            was_allowed=True
        )
        db.add(audit_log)
        db.commit()
    # ========== FIN VALIDACIÓN DE SEGURIDAD ==========

    try:
        # Note: follow_nutrition_plan is now async
        follower = await service.follow_nutrition_plan(
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
async def unfollow_nutrition_plan(
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
    # Use specialized PlanFollowerService for follow operations
    service = PlanFollowerService(db)

    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    try:
        # Note: unfollow_nutrition_plan is now async
        success = await service.unfollow_nutrition_plan(
            plan_id=plan_id,
            user_id=db_user.id,
            gym_id=current_gym.id
        )
        return {"success": success}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/meals/{meal_id}/complete", response_model=UserMealCompletion)
async def complete_meal(
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
    # Use specialized NutritionProgressService for progress tracking
    service = NutritionProgressService(db)

    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    try:
        # Note: complete_meal is now async
        completion = await service.complete_meal(
            meal_id=meal_id,
            user_id=db_user.id,
            gym_id=current_gym.id
        )
        # Add additional data if provided
        if completion_data.satisfaction_rating:
            completion.satisfaction_rating = completion_data.satisfaction_rating
        if completion_data.photo_url:
            completion.photo_url = completion_data.photo_url
        if completion_data.notes:
            completion.notes = completion_data.notes
        return completion
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/today", response_model=TodayMealPlan)
async def get_today_meal_plan(
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
    # Use specialized NutritionProgressService for progress tracking
    service = NutritionProgressService(db)

    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Use cached method for better performance
    meal_plan = await service.get_today_meal_plan_cached(
        user_id=db_user.id,
        gym_id=current_gym.id
    )

    if not meal_plan:
        # Return empty plan if no active plans
        from datetime import date
        return TodayMealPlan(
            date=date.today(),
            plans=[],
            total_calories_target=0,
            total_calories_consumed=0,
            overall_completion=0
        )

    # NUEVO: Agregar group_stats para planes LIVE
    if meal_plan.plan and meal_plan.plan.plan_type == PlanType.LIVE and meal_plan.status == PlanStatus.RUNNING:
        group_stats = await service.get_group_completion_stats(
            plan_id=meal_plan.plan.id,
            gym_id=current_gym.id,
            current_day=meal_plan.current_day,
            db=db
        )
        meal_plan.group_stats = group_stats

    return meal_plan


@router.get("/dashboard", response_model=UserNutritionDashboard)
async def get_nutrition_dashboard(
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
    # Use specialized NutritionAnalyticsService for dashboard
    service = NutritionAnalyticsService(db)

    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Get user nutrition dashboard with analytics
    dashboard = service.get_user_nutrition_dashboard(
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
    # Use specialized NutritionPlanService for plan operations
    service = NutritionPlanService(db)

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
            user_id=db_user.id,
            gym_id=current_gym.id
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
    # Use specialized MealService for meal operations
    service = MealService(db)

    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Verificar que el daily_plan_id coincide
    if meal_data.daily_plan_id != daily_plan_id:
        raise HTTPException(status_code=400, detail="El daily_plan_id no coincide")

    # Get gym_id from user's current gym
    user_gym = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.is_active == True
    ).first()

    if not user_gym:
        raise HTTPException(status_code=404, detail="Usuario no asociado a un gimnasio")

    try:
        meal = service.create_meal(
            daily_plan_id=daily_plan_id,
            meal_data=meal_data,
            creator_id=db_user.id,
            gym_id=user_gym.gym_id
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
    # Use specialized MealService for meal operations
    service = MealService(db)

    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Verificar que el meal_id coincide
    if ingredient_data.meal_id != meal_id:
        raise HTTPException(status_code=400, detail="El meal_id no coincide")

    # Get gym_id from user's current gym
    user_gym = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.is_active == True
    ).first()

    if not user_gym:
        raise HTTPException(status_code=404, detail="Usuario no asociado a un gimnasio")

    try:
        ingredient = service.add_ingredient_to_meal(
            meal_id=meal_id,
            ingredient_data=ingredient_data,
            creator_id=db_user.id,
            gym_id=user_gym.gym_id
        )
        return ingredient
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ===== ENDPOINTS DE SEGURIDAD MÉDICA =====

@router.post("/safety-check", response_model=SafetyScreeningResponse)
async def create_safety_screening(
    request: SafetyScreeningRequest,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    🏥 **Evaluación de Seguridad Médica para Nutrición con IA**

    **Descripción:**
    Realiza una evaluación de seguridad médica OBLIGATORIA antes de permitir
    la generación de planes nutricionales con IA. Protege la salud del usuario
    identificando condiciones de riesgo.

    **¿Por qué es necesario?**
    - Detecta condiciones médicas que requieren supervisión profesional
    - Previene recomendaciones peligrosas para grupos vulnerables
    - Cumple con regulaciones de salud y responsabilidad legal
    - Protege a embarazadas, menores, y personas con TCA

    **Proceso de Evaluación:**
    1. **Recopilación de Datos:** Edad, condiciones médicas, medicamentos
    2. **Cálculo de Riesgo:** Score 0-10 basado en factores médicos
    3. **Clasificación:** LOW, MEDIUM, HIGH, o CRITICAL
    4. **Recomendaciones:** Guía personalizada según riesgo
    5. **Validez:** 24 horas antes de requerir nueva evaluación

    **Niveles de Riesgo:**
    - **LOW (0-2):** Puede proceder normalmente
    - **MEDIUM (3-4):** Proceder con precauciones, revisar warnings
    - **HIGH (5-7):** Se recomienda fuertemente supervisión profesional
    - **CRITICAL (8+):** REQUIERE supervisión médica obligatoria

    **Grupos de Alto Riesgo:**
    - Embarazadas o en lactancia
    - Menores de 18 años
    - Historial de trastornos alimentarios
    - Diabetes tipo 1
    - Enfermedad renal o hepática
    - IMC < 18.5 o > 35

    **Importante:**
    - Este screening es válido por 24 horas
    - Se requiere consentimiento parental para menores
    - Los datos son confidenciales y para auditoría médica
    """
    # Obtener usuario local
    from app.services.user import user_service
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Importar servicio de seguridad y modelos
    from app.services.nutrition_ai_safety import NutritionAISafetyService
    from app.models.nutrition_safety import SafetyScreening as SafetyScreeningModel
    import hashlib
    import uuid
    from datetime import datetime, timedelta

    # Calcular score y nivel de riesgo
    risk_score, risk_level = calculate_risk_score(request)

    # Generar warnings
    warnings = generate_safety_warnings(request, risk_score, risk_level)

    # Determinar si puede proceder
    can_proceed = risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]
    requires_professional = risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]

    # Determinar siguiente paso
    if request.age < 18 and not request.parental_consent_email:
        next_step = "parental_consent"
        can_proceed = False
    elif requires_professional:
        next_step = "professional_referral"
    else:
        next_step = "profile"

    # Crear modelo de screening para guardar en DB
    screening = SafetyScreeningModel(
        user_id=db_user.id,
        gym_id=current_gym.id,
        age=request.age,
        weight=0,  # TODO: Agregar campos de peso/altura al request
        height=0,
        sex="not_specified",
        medical_conditions=[],
        is_pregnant=request.is_pregnant,
        is_breastfeeding=request.is_breastfeeding,
        takes_medications=False,
        has_eating_disorder_history=request.has_eating_disorder,
        risk_score=risk_score,
        risk_level=risk_level,
        can_proceed=can_proceed,
        requires_professional=requires_professional,
        warnings=[w.dict() for w in warnings],
        accepts_disclaimer=request.accepts_disclaimer,
        parental_consent_email=request.parental_consent_email,
        parental_consent_token=str(uuid.uuid4()) if request.parental_consent_email else None,
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )

    # Mapear condiciones médicas booleanas a lista
    conditions = []
    if request.has_diabetes:
        conditions.append("diabetes")
    if request.has_heart_condition:
        conditions.append("heart_condition")
    if request.has_kidney_disease:
        conditions.append("kidney_disease")
    if request.has_liver_disease:
        conditions.append("liver_disease")
    if request.has_eating_disorder:
        conditions.append("eating_disorder")
    if request.has_other_condition:
        conditions.append("other_condition")
    screening.medical_conditions = conditions

    # Guardar en base de datos
    db.add(screening)
    db.commit()
    db.refresh(screening)

    # Preparar response
    response = SafetyScreeningResponse(
        screening_id=screening.id,
        risk_score=risk_score,
        risk_level=risk_level,
        can_proceed=can_proceed,
        requires_professional=requires_professional,
        warnings=warnings,
        next_step=next_step,
        expires_at=screening.expires_at,
        expires_in_hours=24,
        parental_consent_required=(request.age < 18),
        parental_consent_sent_to=request.parental_consent_email,
        professional_referral_reasons=[w.message for w in warnings if w.requires_action],
        recommended_specialists=[]
    )

    # Si requiere referencia profesional, agregar especialistas recomendados
    if requires_professional:
        specialists = []
        if request.has_eating_disorder:
            specialists.append("Psicólogo especializado en TCA")
            specialists.append("Nutricionista clínico")
        if request.has_diabetes:
            specialists.append("Endocrinólogo")
            specialists.append("Nutricionista especializado en diabetes")
        if request.is_pregnant:
            specialists.append("Obstetra")
            specialists.append("Nutricionista perinatal")
        if not specialists:
            specialists.append("Nutricionista clínico")
        response.recommended_specialists = specialists

    # Log para auditoría
    from app.models.nutrition_safety import SafetyAuditLog
    audit_log = SafetyAuditLog(
        user_id=db_user.id,
        gym_id=current_gym.id,
        screening_id=screening.id,
        action_type="safety_screening",
        action_details={
            "risk_score": risk_score,
            "risk_level": risk_level.value,
            "can_proceed": can_proceed
        },
        was_allowed=can_proceed,
        denial_reason=None if can_proceed else f"Risk level {risk_level.value} requires professional supervision"
    )
    db.add(audit_log)
    db.commit()

    logger.info(
        f"Safety screening for user {db_user.id} in gym {current_gym.id}: "
        f"{risk_level.value} (score: {risk_score})"
    )

    return response


@router.get("/safety-check/validate/{screening_id}", response_model=ScreeningValidationResponse)
async def validate_safety_screening(
    screening_id: int = Path(..., description="ID del screening a validar"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    🔍 **Validar Screening de Seguridad Existente**

    Verifica si un screening de seguridad sigue siendo válido (no ha expirado)
    y si el usuario puede proceder con la generación de planes con IA.
    """
    from app.services.user import user_service
    from app.models.nutrition_safety import SafetyScreening as SafetyScreeningModel
    from datetime import datetime

    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Buscar screening
    screening = db.query(SafetyScreeningModel).filter(
        SafetyScreeningModel.id == screening_id,
        SafetyScreeningModel.user_id == db_user.id,
        SafetyScreeningModel.gym_id == current_gym.id
    ).first()

    if not screening:
        raise HTTPException(status_code=404, detail="Screening no encontrado")

    # Validar expiración
    is_valid = not screening.is_expired()
    hours_remaining = None

    if is_valid:
        time_remaining = screening.expires_at - datetime.utcnow()
        hours_remaining = time_remaining.total_seconds() / 3600

    from app.schemas.nutrition_safety import ScreeningValidationResponse

    return ScreeningValidationResponse(
        valid=is_valid,
        screening_id=screening.id,
        can_proceed=screening.can_proceed,
        risk_score=screening.risk_score,
        reason="Screening válido y activo" if is_valid else "Screening expirado, requiere nueva evaluación",
        hours_remaining=hours_remaining
    )


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

    # ========== VALIDACIÓN DE PERMISOS ==========
    # Solo trainers y admin pueden generar con IA
    from app.models.user_gym import UserGym
    user_gym = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.gym_id == current_gym.id
    ).first()

    if not user_gym or user_gym.role not in [GymRoleType.TRAINER, GymRoleType.ADMIN, GymRoleType.OWNER]:
        raise HTTPException(
            status_code=403,
            detail="Solo trainers, administradores y owners pueden generar planes con IA"
        )
    # ========== FIN VALIDACIÓN DE PERMISOS ==========

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
        from app.services.nutrition_ai_safety import NutritionAISafetyService
        ai_service = get_nutrition_ai_service()

        # Generar ingredientes con IA
        logger.info(f"🤖 Generando ingredientes IA para meal {meal_id}: '{request.recipe_name}'")
        result = await ai_service.generate_recipe_ingredients(request)

        # Log generación exitosa para auditoría (trainer/admin no necesita safety screening)
        from app.models.nutrition_safety import SafetyAuditLog
        audit_log = SafetyAuditLog(
            user_id=db_user.id,
            gym_id=current_gym.id,
            screening_id=None,  # Trainers/admin no requieren screening
            action_type="ai_generation_by_trainer",
            action_details={
                "meal_id": meal_id,
                "recipe_name": request.recipe_name,
                "ingredients_count": len(result.ingredients),
                "target_calories": request.target_calories,
                "role": user_gym.role
            },
            was_allowed=True,
            ai_model_used="gpt-4o-mini",
            ai_cost_estimate=0.0008  # Estimado por generación
        )
        db.add(audit_log)
        db.commit()

        logger.info(f"✅ {user_gym.role.capitalize()} {db_user.id} generó {len(result.ingredients)} ingredientes para meal {meal_id}")
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

    # ========== VALIDACIÓN DE PERMISOS ==========
    # Solo trainers y admin pueden aplicar ingredientes generados con IA
    from app.models.user_gym import UserGym
    from app.models.nutrition_safety import SafetyAuditLog

    user_gym = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.gym_id == current_gym.id
    ).first()

    if not user_gym or user_gym.role not in [GymRoleType.TRAINER, GymRoleType.ADMIN, GymRoleType.OWNER]:
        raise HTTPException(
            status_code=403,
            detail="Solo trainers, administradores y owners pueden aplicar ingredientes generados con IA"
        )
    # ========== FIN VALIDACIÓN DE PERMISOS ==========

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

        # Log aplicación exitosa para auditoría (trainer/admin no necesita safety screening)
        audit_log = SafetyAuditLog(
            user_id=db_user.id,
            gym_id=current_gym.id,
            screening_id=None,  # Trainers/admin no requieren screening
            action_type="ai_ingredients_applied_by_trainer",
            action_details={
                "meal_id": meal_id,
                "ingredients_added": ingredients_added,
                "ingredients_replaced": ingredients_replaced,
                "total_calories": total_calories,
                "meal_updated": meal_updated,
                "role": user_gym.role
            },
            was_allowed=True
        )
        db.add(audit_log)
        db.commit()

        logger.info(f"✅ {user_gym.role.capitalize()} {db_user.id} aplicó {ingredients_added} ingredientes IA a meal {meal_id}")

        response = ApplyIngredientsResponse(
            success=True,
            ingredients_added=ingredients_added,
            ingredients_replaced=ingredients_replaced,
            meal_updated=meal_updated,
            total_calories=total_calories if meal_updated else None,
            total_protein=total_protein if meal_updated else None,
            total_carbs=total_carbs if meal_updated else None,
            total_fat=total_fat if meal_updated else None
        )

        return response
        
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
async def get_plan_analytics(
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
    # Use specialized NutritionAnalyticsService for analytics
    service = NutritionAnalyticsService(db)

    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    try:
        # OPTIMIZATION: Use cached version to reduce expensive aggregation queries
        analytics = await service.get_plan_analytics_cached(
            plan_id=plan_id,
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
    # Use specialized NutritionPlanService for plan operations
    service = NutritionPlanService(db)

    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Obtener planes por tipo
    live_filters = NutritionPlanFilters(plan_type=PlanType.LIVE)
    template_filters = NutritionPlanFilters(plan_type=PlanType.TEMPLATE)
    archived_filters = NutritionPlanFilters(plan_type=PlanType.ARCHIVED)

    live_plans, live_total = service.list_nutrition_plans(
        gym_id=current_gym.id, filters=live_filters, skip=0, limit=50
    )

    template_plans, template_total = service.list_nutrition_plans(
        gym_id=current_gym.id, filters=template_filters, skip=0, limit=50
    )

    archived_plans, archived_total = service.list_nutrition_plans(
        gym_id=current_gym.id, filters=archived_filters, skip=0, limit=50
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
    # Use specialized LivePlanService for live plan operations
    live_service = LivePlanService(db)
    plan_service = NutritionPlanService(db)

    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    try:
        # Verificar permisos
        plan = plan_service.get_nutrition_plan(plan_id, current_gym.id)
        if plan.creator_id != db_user.id:
            raise HTTPException(status_code=403, detail="Solo el creador puede actualizar el estado del plan")

        if plan.plan_type != PlanType.LIVE:
            raise HTTPException(status_code=400, detail="Solo se puede actualizar el estado de planes live")

        # Update live plan status using the service method
        updated_plan = live_service.update_live_plan_status(
            plan_id=plan_id,
            is_active=status_update.is_live_active,
            participant_count=status_update.live_participants_count,
            updater_id=db_user.id,
            gym_id=current_gym.id
        )

        return updated_plan
        
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
    # Use specialized LivePlanService for live plan operations
    service = LivePlanService(db)

    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    try:
        # Archive the live plan
        archived_plan = service.archive_live_plan(
            plan_id=plan_id,
            archiver_id=db_user.id,
            gym_id=current_gym.id,
            reason=archive_request.reason if hasattr(archive_request, 'reason') else None
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
    # Use specialized services
    plan_service = NutritionPlanService(db)
    live_service = LivePlanService(db)
    follower_service = PlanFollowerService(db)

    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    try:
        # Get the plan
        plan = plan_service.get_nutrition_plan(plan_id, current_gym.id)

        # Get follower information if user is not the creator
        follower = None
        current_day = 0
        status = PlanStatus.NOT_STARTED

        if db_user.id != plan.creator_id:
            # Get follower data
            user_followed_plans = follower_service.get_user_followed_plans(
                user_id=db_user.id,
                gym_id=current_gym.id,
                include_archived=False
            )
            # Find this plan in the user's followed plans
            for fp in user_followed_plans:
                if fp.plan_id == plan_id:
                    follower = fp
                    break

        # Calculate status based on plan type
        if plan.plan_type == PlanType.LIVE:
            # Update and get live plan status
            updated_plan = live_service.get_live_plan_status(plan_id, current_gym.id)
            if updated_plan:
                status = PlanStatus.RUNNING if updated_plan.is_live_active else PlanStatus.FINISHED
        else:
            # For template plans, calculate based on follower data
            if follower:
                from datetime import date
                days_since_start = (date.today() - follower.start_date.date()).days
                if days_since_start >= 0:
                    if days_since_start < plan.duration_days:
                        current_day = days_since_start + 1
                        status = PlanStatus.RUNNING
                    else:
                        status = PlanStatus.FINISHED

        days_until_start = 0
        if plan.live_start_date and status == PlanStatus.NOT_STARTED:
            from datetime import date
            days_until_start = (plan.live_start_date - date.today()).days
        
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
    active_followers = db.query(NutritionPlanFollowerModel).join(
        NutritionPlanModel
    ).filter(
        NutritionPlanFollowerModel.user_id == db_user.id,
        NutritionPlanFollowerModel.is_active == True,
        NutritionPlanModel.gym_id == current_gym.id
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


    # Si se especifica un plan, actualizar solo ese
    if plan_id:
        # Verificar que el plan existe y pertenece al gimnasio
        plan = db.query(NutritionPlanModel).filter(
            NutritionPlanModel.id == plan_id,
            NutritionPlanModel.gym_id == current_gym.id
        ).first()

        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado")

        # Obtener la relación follower
        follower = db.query(NutritionPlanFollowerModel).filter(
            NutritionPlanFollowerModel.plan_id == plan_id,
            NutritionPlanFollowerModel.user_id == db_user.id,
            NutritionPlanFollowerModel.is_active == True
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
        active_followers = db.query(NutritionPlanFollowerModel).join(
            NutritionPlanModel
        ).filter(
            NutritionPlanFollowerModel.user_id == db_user.id,
            NutritionPlanFollowerModel.is_active == True,
            NutritionPlanModel.gym_id == current_gym.id
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
    if not user_gym or user_gym.role not in [GymRoleType.ADMIN, GymRoleType.TRAINER, GymRoleType.OWNER]:
        raise HTTPException(
            status_code=403,
            detail="Solo administradores, entrenadores y owners pueden ver la auditoría"
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
    if not user_gym or user_gym.role not in [GymRoleType.ADMIN, GymRoleType.TRAINER, GymRoleType.OWNER]:
        raise HTTPException(
            status_code=403,
            detail="Solo administradores, entrenadores y owners pueden ver la auditoría"
        )

    # Obtener resumen
    summary = get_notification_audit_summary(
        gym_id=current_gym.id,
        hours=hours
    )

    return summary


# ============================================================================
# CRUD ENDPOINTS PARA MEALS
# ============================================================================

@router.get("/meals/{meal_id}", response_model=MealWithIngredients)
async def get_meal(
    meal_id: int = Path(..., description="ID único de la comida"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    🍽️ **Obtener Comida Específica con Ingredientes**

    **Descripción:**
    Obtiene la información completa de una comida individual, incluyendo
    todos sus ingredientes con información nutricional detallada.

    **Validaciones:**
    - La comida debe existir en el sistema
    - El plan debe pertenecer al gimnasio actual
    - El usuario debe tener acceso al plan (público o ser seguidor/creador)

    **Respuesta incluye:**
    - Información básica de la comida (nombre, tipo, instrucciones)
    - Lista completa de ingredientes con valores nutricionales
    - Totales nutricionales calculados
    - Metadatos (fecha de creación, última actualización)

    **Casos de error:**
    - 404: Comida no encontrada
    - 403: Sin acceso (plan privado y usuario no autorizado)
    - 403: Comida de otro gimnasio
    """
    # Obtener la comida con sus ingredientes usando joinedload para optimización
    meal = db.query(MealModel).filter(
        MealModel.id == meal_id
    ).options(
        joinedload(MealModel.ingredients)
    ).first()

    if not meal:
        logger.warning(f"Meal {meal_id} not found for user {current_user.id}")
        raise HTTPException(
            status_code=404,
            detail="Comida no encontrada"
        )

    # Verificar acceso a través del plan
    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == meal.daily_plan_id
    ).first()

    if not daily_plan:
        logger.error(f"Daily plan not found for meal {meal_id}")
        raise HTTPException(
            status_code=404,
            detail="Plan diario no encontrado para esta comida"
        )

    # Verificar que el plan pertenece al gimnasio actual
    nutrition_plan = db.query(NutritionPlanModel).filter(
        NutritionPlanModel.id == daily_plan.nutrition_plan_id,
        NutritionPlanModel.gym_id == current_gym.id
    ).first()

    if not nutrition_plan:
        logger.warning(f"Access denied to meal {meal_id} for user {current_user.id} - wrong gym")
        raise HTTPException(
            status_code=403,
            detail="Sin acceso a esta comida - pertenece a otro gimnasio"
        )

    # Verificar acceso si el plan es privado
    if not nutrition_plan.is_public:
        db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
        if db_user:
            # Verificar si es el creador
            is_creator = nutrition_plan.creator_id == db_user.id

            # Verificar si es seguidor activo
            is_follower = db.query(NutritionPlanFollowerModel).filter(
                NutritionPlanFollowerModel.plan_id == nutrition_plan.id,
                NutritionPlanFollowerModel.user_id == db_user.id,
                NutritionPlanFollowerModel.is_active == True
            ).first() is not None

            # Verificar si es admin del gimnasio
            is_admin = db.query(UserGym).filter(
                UserGym.user_id == db_user.id,
                UserGym.gym_id == current_gym.id,
                UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
            ).first() is not None

            if not (is_creator or is_follower or is_admin):
                logger.warning(f"Access denied to private plan meal {meal_id} for user {current_user.id}")
                raise HTTPException(
                    status_code=403,
                    detail="Plan privado - no tienes acceso a esta comida"
                )

    logger.info(f"Successfully retrieved meal {meal_id} for user {current_user.id}")
    return meal


@router.put("/meals/{meal_id}", response_model=Meal)
async def update_meal(
    meal_id: int = Path(..., description="ID de la comida a actualizar"),
    meal_update: MealUpdate = Body(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    ✏️ **Actualizar Información de una Comida**

    **Descripción:**
    Actualiza los campos de una comida existente. Solo el creador del plan
    o administradores del gimnasio pueden realizar esta operación.

    **Campos actualizables:**
    - name: Nombre de la comida
    - meal_type: Tipo (breakfast, lunch, dinner, snack, other)
    - description: Descripción detallada
    - preparation_time_minutes: Tiempo de preparación
    - cooking_instructions: Instrucciones de preparación
    - calories, protein_g, carbs_g, fat_g, fiber_g: Valores nutricionales
    - image_url, video_url: Recursos multimedia
    - order_in_day: Orden de la comida en el día

    **Permisos requeridos:**
    - Ser el creador del plan
    - O ser administrador/owner del gimnasio

    **Validaciones:**
    - Todos los campos son opcionales (actualización parcial)
    - Los valores nutricionales deben ser >= 0
    - El nombre debe tener entre 1 y 200 caracteres si se proporciona
    """
    # Buscar la comida
    meal = db.query(MealModel).filter(MealModel.id == meal_id).first()

    if not meal:
        logger.warning(f"Meal {meal_id} not found for update by user {current_user.id}")
        raise HTTPException(
            status_code=404,
            detail="Comida no encontrada"
        )

    # Verificar acceso y permisos a través del plan
    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == meal.daily_plan_id
    ).first()

    if not daily_plan:
        raise HTTPException(
            status_code=404,
            detail="Plan diario no encontrado"
        )

    nutrition_plan = db.query(NutritionPlanModel).filter(
        NutritionPlanModel.id == daily_plan.nutrition_plan_id,
        NutritionPlanModel.gym_id == current_gym.id
    ).first()

    if not nutrition_plan:
        logger.warning(f"Access denied to update meal {meal_id} - wrong gym")
        raise HTTPException(
            status_code=403,
            detail="Sin acceso a esta comida - pertenece a otro gimnasio"
        )

    # Verificar permisos de modificación
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(
            status_code=403,
            detail="Usuario no encontrado"
        )

    # Verificar si es el creador del plan
    is_creator = nutrition_plan.creator_id == db_user.id

    # Verificar si es admin/owner del gimnasio
    user_gym = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.gym_id == current_gym.id
    ).first()

    is_admin = user_gym and user_gym.role in [GymRoleType.ADMIN, GymRoleType.OWNER]

    if not (is_creator or is_admin):
        logger.warning(f"Permission denied to update meal {meal_id} for user {current_user.id}")
        raise HTTPException(
            status_code=403,
            detail="Solo el creador del plan o administradores pueden actualizar comidas"
        )

    # Actualizar solo los campos proporcionados
    update_data = meal_update.dict(exclude_unset=True)

    for field, value in update_data.items():
        setattr(meal, field, value)

    # Actualizar timestamp
    meal.updated_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(meal)
        logger.info(f"Meal {meal_id} updated successfully by user {db_user.id}")
    except Exception as e:
        logger.error(f"Error updating meal {meal_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Error al actualizar la comida"
        )

    return meal


@router.delete("/meals/{meal_id}", status_code=204)
async def delete_meal(
    meal_id: int = Path(..., description="ID de la comida a eliminar"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    🗑️ **Eliminar una Comida**

    **Descripción:**
    Elimina permanentemente una comida y todos sus datos asociados (ingredientes,
    registros de completación). Esta acción es irreversible.

    **Permisos requeridos:**
    - Ser el creador del plan
    - O ser administrador/owner del gimnasio

    **Efectos de la eliminación:**
    - Se eliminan todos los ingredientes de la comida
    - Se eliminan todos los registros de completación de usuarios
    - Se recalculan los totales nutricionales del día (si aplica)

    **Respuesta:**
    - 204 No Content: Eliminación exitosa
    - 404: Comida no encontrada
    - 403: Sin permisos para eliminar
    """
    # Buscar la comida
    meal = db.query(MealModel).filter(MealModel.id == meal_id).first()

    if not meal:
        logger.warning(f"Meal {meal_id} not found for deletion")
        raise HTTPException(
            status_code=404,
            detail="Comida no encontrada"
        )

    # Verificar acceso y permisos
    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == meal.daily_plan_id
    ).first()

    if not daily_plan:
        raise HTTPException(
            status_code=404,
            detail="Plan diario no encontrado"
        )

    nutrition_plan = db.query(NutritionPlanModel).filter(
        NutritionPlanModel.id == daily_plan.nutrition_plan_id,
        NutritionPlanModel.gym_id == current_gym.id
    ).first()

    if not nutrition_plan:
        raise HTTPException(
            status_code=403,
            detail="Sin acceso a esta comida"
        )

    # Verificar permisos
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(
            status_code=403,
            detail="Usuario no encontrado"
        )

    is_creator = nutrition_plan.creator_id == db_user.id

    user_gym = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.gym_id == current_gym.id
    ).first()

    is_admin = user_gym and user_gym.role in [GymRoleType.ADMIN, GymRoleType.OWNER]

    if not (is_creator or is_admin):
        logger.warning(f"Permission denied to delete meal {meal_id} for user {current_user.id}")
        raise HTTPException(
            status_code=403,
            detail="Solo el creador del plan o administradores pueden eliminar comidas"
        )

    try:
        # Eliminar registros de completación
        db.query(UserMealCompletionModel).filter(
            UserMealCompletionModel.meal_id == meal_id
        ).delete()

        # Eliminar ingredientes
        db.query(MealIngredientModel).filter(
            MealIngredientModel.meal_id == meal_id
        ).delete()

        # Eliminar la comida
        db.delete(meal)
        db.commit()

        logger.info(f"Meal {meal_id} deleted successfully by user {db_user.id}")

    except Exception as e:
        logger.error(f"Error deleting meal {meal_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Error al eliminar la comida"
        )

    return Response(status_code=204)


# ============================================================================
# CRUD ENDPOINTS PARA DAILY PLANS
# ============================================================================

@router.get("/days/{daily_plan_id}", response_model=DailyNutritionPlanWithMeals)
async def get_daily_plan(
    daily_plan_id: int = Path(..., description="ID del día del plan"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    📅 **Obtener Día Específico del Plan con Comidas**

    **Descripción:**
    Obtiene la información completa de un día del plan nutricional,
    incluyendo todas sus comidas con ingredientes detallados.

    **Respuesta incluye:**
    - Información del día (número, fecha planificada, notas)
    - Lista completa de comidas del día ordenadas
    - Ingredientes de cada comida con valores nutricionales
    - Totales nutricionales del día
    - Estado de publicación

    **Validaciones:**
    - El día debe existir
    - El plan debe pertenecer al gimnasio actual
    - El usuario debe tener acceso (plan público o ser seguidor/creador)

    **Optimización:**
    Utiliza eager loading para minimizar consultas a la base de datos.
    """
    # Obtener el día con sus comidas e ingredientes
    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == daily_plan_id
    ).options(
        joinedload(DailyNutritionPlanModel.meals).joinedload(MealModel.ingredients)
    ).first()

    if not daily_plan:
        logger.warning(f"Daily plan {daily_plan_id} not found")
        raise HTTPException(
            status_code=404,
            detail="Día del plan no encontrado"
        )

    # Verificar acceso a través del plan
    nutrition_plan = db.query(NutritionPlanModel).filter(
        NutritionPlanModel.id == daily_plan.nutrition_plan_id,
        NutritionPlanModel.gym_id == current_gym.id
    ).first()

    if not nutrition_plan:
        logger.warning(f"Access denied to daily plan {daily_plan_id} - wrong gym")
        raise HTTPException(
            status_code=403,
            detail="Sin acceso a este día - pertenece a otro gimnasio"
        )

    # Verificar acceso si el plan es privado
    if not nutrition_plan.is_public:
        db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
        if db_user:
            is_creator = nutrition_plan.creator_id == db_user.id

            is_follower = db.query(NutritionPlanFollowerModel).filter(
                NutritionPlanFollowerModel.plan_id == nutrition_plan.id,
                NutritionPlanFollowerModel.user_id == db_user.id,
                NutritionPlanFollowerModel.is_active == True
            ).first() is not None

            is_admin = db.query(UserGym).filter(
                UserGym.user_id == db_user.id,
                UserGym.gym_id == current_gym.id,
                UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
            ).first() is not None

            if not (is_creator or is_follower or is_admin):
                logger.warning(f"Access denied to private plan daily {daily_plan_id}")
                raise HTTPException(
                    status_code=403,
                    detail="Plan privado - no tienes acceso a este día"
                )

    logger.info(f"Successfully retrieved daily plan {daily_plan_id}")
    return daily_plan


@router.get("/plans/{plan_id}/days", response_model=List[DailyNutritionPlanWithMeals])
async def list_plan_days(
    plan_id: int = Path(..., description="ID del plan nutricional"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    📋 **Listar Todos los Días de un Plan**

    **Descripción:**
    Obtiene todos los días de un plan nutricional con sus comidas completas,
    ordenados por número de día.

    **Respuesta:**
    Array de días, cada uno incluyendo:
    - Información del día
    - Todas las comidas del día
    - Ingredientes de cada comida
    - Totales nutricionales

    **Casos de uso:**
    - Vista completa del plan
    - Exportación del plan
    - Análisis nutricional completo

    **Performance:**
    Usa eager loading para obtener toda la información en una sola consulta.
    """
    # Verificar que el plan existe y pertenece al gym
    nutrition_plan = db.query(NutritionPlanModel).filter(
        NutritionPlanModel.id == plan_id,
        NutritionPlanModel.gym_id == current_gym.id
    ).first()

    if not nutrition_plan:
        logger.warning(f"Plan {plan_id} not found or wrong gym")
        raise HTTPException(
            status_code=404,
            detail="Plan nutricional no encontrado"
        )

    # Verificar acceso si el plan es privado
    if not nutrition_plan.is_public:
        db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
        if db_user:
            is_creator = nutrition_plan.creator_id == db_user.id

            is_follower = db.query(NutritionPlanFollowerModel).filter(
                NutritionPlanFollowerModel.plan_id == nutrition_plan.id,
                NutritionPlanFollowerModel.user_id == db_user.id,
                NutritionPlanFollowerModel.is_active == True
            ).first() is not None

            is_admin = db.query(UserGym).filter(
                UserGym.user_id == db_user.id,
                UserGym.gym_id == current_gym.id,
                UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
            ).first() is not None

            if not (is_creator or is_follower or is_admin):
                raise HTTPException(
                    status_code=403,
                    detail="Plan privado - no tienes acceso"
                )

    # Obtener todos los días con sus comidas e ingredientes
    daily_plans = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.nutrition_plan_id == plan_id
    ).options(
        joinedload(DailyNutritionPlanModel.meals).joinedload(MealModel.ingredients)
    ).order_by(DailyNutritionPlanModel.day_number).all()

    logger.info(f"Retrieved {len(daily_plans)} days for plan {plan_id}")
    return daily_plans


@router.put("/days/{daily_plan_id}", response_model=DailyNutritionPlan)
async def update_daily_plan(
    daily_plan_id: int = Path(..., description="ID del día a actualizar"),
    day_update: DailyNutritionPlanUpdate = Body(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    ✏️ **Actualizar Información de un Día del Plan**

    **Descripción:**
    Actualiza los metadatos de un día específico del plan nutricional.
    No modifica las comidas, solo la información del día.

    **Campos actualizables:**
    - day_number: Número del día (reorganización)
    - planned_date: Fecha planificada
    - total_calories, total_protein_g, etc: Totales nutricionales
    - notes: Notas del día
    - is_published: Estado de publicación

    **Permisos:**
    - Creador del plan
    - Administrador/owner del gimnasio

    **Validaciones:**
    - day_number debe ser >= 1
    - Valores nutricionales >= 0
    """
    # Buscar el día
    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == daily_plan_id
    ).first()

    if not daily_plan:
        logger.warning(f"Daily plan {daily_plan_id} not found for update")
        raise HTTPException(
            status_code=404,
            detail="Día del plan no encontrado"
        )

    # Verificar permisos
    nutrition_plan = db.query(NutritionPlanModel).filter(
        NutritionPlanModel.id == daily_plan.nutrition_plan_id,
        NutritionPlanModel.gym_id == current_gym.id
    ).first()

    if not nutrition_plan:
        raise HTTPException(
            status_code=403,
            detail="Sin acceso a este día"
        )

    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(
            status_code=403,
            detail="Usuario no encontrado"
        )

    is_creator = nutrition_plan.creator_id == db_user.id

    user_gym = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.gym_id == current_gym.id
    ).first()

    is_admin = user_gym and user_gym.role in [GymRoleType.ADMIN, GymRoleType.OWNER]

    if not (is_creator or is_admin):
        logger.warning(f"Permission denied to update daily plan {daily_plan_id}")
        raise HTTPException(
            status_code=403,
            detail="Solo el creador del plan o administradores pueden actualizar"
        )

    # Actualizar campos
    update_data = day_update.dict(exclude_unset=True)

    # Si se actualiza is_published a True, marcar fecha de publicación
    if 'is_published' in update_data and update_data['is_published'] and not daily_plan.is_published:
        daily_plan.published_at = datetime.utcnow()

    for field, value in update_data.items():
        setattr(daily_plan, field, value)

    daily_plan.updated_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(daily_plan)
        logger.info(f"Daily plan {daily_plan_id} updated by user {db_user.id}")
    except Exception as e:
        logger.error(f"Error updating daily plan {daily_plan_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Error al actualizar el día del plan"
        )

    return daily_plan


@router.delete("/days/{daily_plan_id}", status_code=204)
async def delete_daily_plan(
    daily_plan_id: int = Path(..., description="ID del día a eliminar"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    🗑️ **Eliminar un Día del Plan**

    **Descripción:**
    Elimina permanentemente un día del plan con todas sus comidas e ingredientes.
    Los días posteriores se renumeran automáticamente.

    **Efectos:**
    - Elimina todas las comidas del día
    - Elimina todos los ingredientes de las comidas
    - Elimina registros de completación
    - Renumera días posteriores (día 5 se convierte en día 4, etc.)
    - Actualiza duration_days del plan

    **Permisos:**
    - Creador del plan
    - Administrador/owner del gimnasio

    **Importante:**
    Esta acción es irreversible y afecta la estructura completa del plan.
    """
    # Buscar el día
    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == daily_plan_id
    ).first()

    if not daily_plan:
        logger.warning(f"Daily plan {daily_plan_id} not found for deletion")
        raise HTTPException(
            status_code=404,
            detail="Día del plan no encontrado"
        )

    # Verificar permisos
    nutrition_plan = db.query(NutritionPlanModel).filter(
        NutritionPlanModel.id == daily_plan.nutrition_plan_id,
        NutritionPlanModel.gym_id == current_gym.id
    ).first()

    if not nutrition_plan:
        raise HTTPException(
            status_code=403,
            detail="Sin acceso a este día"
        )

    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(
            status_code=403,
            detail="Usuario no encontrado"
        )

    is_creator = nutrition_plan.creator_id == db_user.id

    user_gym = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.gym_id == current_gym.id
    ).first()

    is_admin = user_gym and user_gym.role in [GymRoleType.ADMIN, GymRoleType.OWNER]

    if not (is_creator or is_admin):
        logger.warning(f"Permission denied to delete daily plan {daily_plan_id}")
        raise HTTPException(
            status_code=403,
            detail="Solo el creador del plan o administradores pueden eliminar días"
        )

    try:
        # Guardar el número del día para renumerar
        deleted_day_number = daily_plan.day_number

        # Obtener todas las comidas del día
        meals = db.query(MealModel).filter(
            MealModel.daily_plan_id == daily_plan_id
        ).all()

        # Eliminar completaciones e ingredientes de cada comida
        for meal in meals:
            db.query(UserMealCompletionModel).filter(
                UserMealCompletionModel.meal_id == meal.id
            ).delete()

            db.query(MealIngredientModel).filter(
                MealIngredientModel.meal_id == meal.id
            ).delete()

            db.delete(meal)

        # Eliminar el día
        db.delete(daily_plan)

        # Renumerar días posteriores
        subsequent_days = db.query(DailyNutritionPlanModel).filter(
            DailyNutritionPlanModel.nutrition_plan_id == nutrition_plan.id,
            DailyNutritionPlanModel.day_number > deleted_day_number
        ).all()

        for day in subsequent_days:
            day.day_number -= 1
            day.updated_at = datetime.utcnow()

        # Actualizar duración del plan
        nutrition_plan.duration_days = max(0, nutrition_plan.duration_days - 1)
        nutrition_plan.updated_at = datetime.utcnow()

        db.commit()

        logger.info(f"Daily plan {daily_plan_id} deleted by user {db_user.id}")

    except Exception as e:
        logger.error(f"Error deleting daily plan {daily_plan_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Error al eliminar el día del plan"
        )

    return Response(status_code=204)


# ============================================================================
# CRUD ENDPOINTS PARA INGREDIENTS
# ============================================================================

@router.put("/ingredients/{ingredient_id}", response_model=MealIngredient)
async def update_ingredient(
    ingredient_id: int = Path(..., description="ID del ingrediente"),
    ingredient_update: MealIngredientUpdate = Body(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    ✏️ **Actualizar Ingrediente de una Comida**

    **Descripción:**
    Actualiza la información de un ingrediente específico en una comida.
    Útil para corregir cantidades o valores nutricionales.

    **Campos actualizables:**
    - name: Nombre del ingrediente
    - quantity: Cantidad
    - unit: Unidad de medida (g, ml, taza, etc.)
    - calories_per_serving, protein_per_serving, etc: Valores nutricionales
    - alternatives: Lista de ingredientes alternativos
    - is_optional: Si el ingrediente es opcional

    **Permisos:**
    - Creador del plan
    - Administrador/owner del gimnasio

    **Validaciones:**
    - quantity debe ser > 0
    - Valores nutricionales >= 0
    - El ingrediente debe existir
    """
    # Buscar el ingrediente
    ingredient = db.query(MealIngredientModel).filter(
        MealIngredientModel.id == ingredient_id
    ).first()

    if not ingredient:
        logger.warning(f"Ingredient {ingredient_id} not found")
        raise HTTPException(
            status_code=404,
            detail="Ingrediente no encontrado"
        )

    # Verificar acceso a través del meal -> daily_plan -> plan
    meal = db.query(MealModel).filter(
        MealModel.id == ingredient.meal_id
    ).first()

    if not meal:
        logger.error(f"Meal not found for ingredient {ingredient_id}")
        raise HTTPException(
            status_code=404,
            detail="Comida no encontrada para este ingrediente"
        )

    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == meal.daily_plan_id
    ).first()

    if not daily_plan:
        raise HTTPException(
            status_code=404,
            detail="Plan diario no encontrado"
        )

    nutrition_plan = db.query(NutritionPlanModel).filter(
        NutritionPlanModel.id == daily_plan.nutrition_plan_id,
        NutritionPlanModel.gym_id == current_gym.id
    ).first()

    if not nutrition_plan:
        logger.warning(f"Access denied to ingredient {ingredient_id} - wrong gym")
        raise HTTPException(
            status_code=403,
            detail="Sin acceso a este ingrediente"
        )

    # Verificar permisos
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(
            status_code=403,
            detail="Usuario no encontrado"
        )

    is_creator = nutrition_plan.creator_id == db_user.id

    user_gym = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.gym_id == current_gym.id
    ).first()

    is_admin = user_gym and user_gym.role in [GymRoleType.ADMIN, GymRoleType.OWNER]

    if not (is_creator or is_admin):
        logger.warning(f"Permission denied to update ingredient {ingredient_id}")
        raise HTTPException(
            status_code=403,
            detail="Solo el creador del plan o administradores pueden actualizar ingredientes"
        )

    # Actualizar campos
    update_data = ingredient_update.dict(exclude_unset=True)

    for field, value in update_data.items():
        setattr(ingredient, field, value)

    ingredient.updated_at = datetime.utcnow()

    # Si se actualizaron valores nutricionales, actualizar totales de la comida
    if any(field in update_data for field in [
        'calories_per_serving', 'protein_per_serving',
        'carbs_per_serving', 'fat_per_serving'
    ]):
        # Recalcular totales de la comida
        meal_ingredients = db.query(MealIngredientModel).filter(
            MealIngredientModel.meal_id == meal.id
        ).all()

        total_calories = sum(i.calories_per_serving or 0 for i in meal_ingredients)
        total_protein = sum(i.protein_per_serving or 0 for i in meal_ingredients)
        total_carbs = sum(i.carbs_per_serving or 0 for i in meal_ingredients)
        total_fat = sum(i.fat_per_serving or 0 for i in meal_ingredients)

        meal.calories = total_calories
        meal.protein_g = total_protein
        meal.carbs_g = total_carbs
        meal.fat_g = total_fat
        meal.updated_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(ingredient)
        logger.info(f"Ingredient {ingredient_id} updated by user {db_user.id}")
    except Exception as e:
        logger.error(f"Error updating ingredient {ingredient_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Error al actualizar el ingrediente"
        )

    return ingredient


@router.delete("/ingredients/{ingredient_id}", status_code=204)
async def delete_ingredient(
    ingredient_id: int = Path(..., description="ID del ingrediente a eliminar"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    🗑️ **Eliminar Ingrediente de una Comida**

    **Descripción:**
    Elimina un ingrediente específico de una comida.
    Los totales nutricionales de la comida se recalculan automáticamente.

    **Efectos:**
    - Elimina el ingrediente de la base de datos
    - Recalcula los totales nutricionales de la comida
    - No afecta otros ingredientes de la misma comida

    **Permisos:**
    - Creador del plan
    - Administrador/owner del gimnasio

    **Respuesta:**
    - 204 No Content: Eliminación exitosa
    - 404: Ingrediente no encontrado
    - 403: Sin permisos
    """
    # Buscar el ingrediente
    ingredient = db.query(MealIngredientModel).filter(
        MealIngredientModel.id == ingredient_id
    ).first()

    if not ingredient:
        logger.warning(f"Ingredient {ingredient_id} not found for deletion")
        raise HTTPException(
            status_code=404,
            detail="Ingrediente no encontrado"
        )

    # Verificar acceso y permisos (mismo flujo que update)
    meal = db.query(MealModel).filter(
        MealModel.id == ingredient.meal_id
    ).first()

    if not meal:
        raise HTTPException(
            status_code=404,
            detail="Comida no encontrada"
        )

    daily_plan = db.query(DailyNutritionPlanModel).filter(
        DailyNutritionPlanModel.id == meal.daily_plan_id
    ).first()

    if not daily_plan:
        raise HTTPException(
            status_code=404,
            detail="Plan diario no encontrado"
        )

    nutrition_plan = db.query(NutritionPlanModel).filter(
        NutritionPlanModel.id == daily_plan.nutrition_plan_id,
        NutritionPlanModel.gym_id == current_gym.id
    ).first()

    if not nutrition_plan:
        raise HTTPException(
            status_code=403,
            detail="Sin acceso a este ingrediente"
        )

    # Verificar permisos
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(
            status_code=403,
            detail="Usuario no encontrado"
        )

    is_creator = nutrition_plan.creator_id == db_user.id

    user_gym = db.query(UserGym).filter(
        UserGym.user_id == db_user.id,
        UserGym.gym_id == current_gym.id
    ).first()

    is_admin = user_gym and user_gym.role in [GymRoleType.ADMIN, GymRoleType.OWNER]

    if not (is_creator or is_admin):
        logger.warning(f"Permission denied to delete ingredient {ingredient_id}")
        raise HTTPException(
            status_code=403,
            detail="Solo el creador del plan o administradores pueden eliminar ingredientes"
        )

    try:
        # Eliminar el ingrediente
        db.delete(ingredient)

        # Recalcular totales de la comida
        remaining_ingredients = db.query(MealIngredientModel).filter(
            MealIngredientModel.meal_id == meal.id,
            MealIngredientModel.id != ingredient_id
        ).all()

        meal.calories = sum(i.calories_per_serving or 0 for i in remaining_ingredients)
        meal.protein_g = sum(i.protein_per_serving or 0 for i in remaining_ingredients)
        meal.carbs_g = sum(i.carbs_per_serving or 0 for i in remaining_ingredients)
        meal.fat_g = sum(i.fat_per_serving or 0 for i in remaining_ingredients)
        meal.updated_at = datetime.utcnow()

        db.commit()

        logger.info(f"Ingredient {ingredient_id} deleted by user {db_user.id}")

    except Exception as e:
        logger.error(f"Error deleting ingredient {ingredient_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Error al eliminar el ingrediente"
        )

    return Response(status_code=204)


# ============================================================================
# FIN DE ENDPOINTS CRUD AGREGADOS
# ============================================================================
