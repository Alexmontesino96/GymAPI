"""
Endpoints para gestión de membresías y planes de membresía.

Este módulo proporciona todas las rutas relacionadas con la gestión de:
- Planes de membresía (creación, actualización, consulta)
- Estado de membresías de usuarios
- Compra de membresías (requiere módulo billing activo)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, delete

from app.db.session import get_async_db
from app.core.auth0_fastapi import Auth0User, auth
from app.core.tenant import verify_gym_access, verify_gym_admin_access, get_current_gym
from app.core.billing_dependencies import billing_module_required, billing_module_optional, get_billing_capabilities
from app.schemas.gym import GymSchema
from app.schemas.membership import (
    MembershipPlan,
    MembershipPlanCreate,
    MembershipPlanUpdate,
    MembershipPlanList,
    MembershipStatus,
    MembershipSummary,
    UserMembership,
    PurchaseMembershipRequest,
    PurchaseMembershipResponse,
    AdminPaymentLinkResponse,
    AdminCreatePaymentLinkRequest
)
from app.services.membership import membership_service
from app.services.stripe_service import StripeService
from app.services.user import user_service
from app.db.redis_client import get_redis_client
from app.middleware.rate_limit import limiter
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
router = APIRouter()

# Instanciar servicio de Stripe
stripe_service = StripeService(membership_service)


# === Endpoint de Capacidades de Billing ===

@router.get("/billing/capabilities")
async def get_billing_capabilities_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_access),
    capabilities: dict = Depends(get_billing_capabilities)
) -> dict:
    """
    Obtener las capacidades de billing disponibles para el gimnasio actual.
    
    Este endpoint permite al frontend saber qué funcionalidades de billing
    están disponibles basándose en si el módulo está activo o no.
    
    Args:
        request: Request HTTP
        db: Sesión de base de datos
        current_user: Usuario autenticado
        current_gym: Gimnasio verificado
        capabilities: Capacidades de billing (inyectadas por dependencia)
        
    Returns:
        dict: Capacidades disponibles y configuración del módulo
    """
    return {
        "gym_id": current_gym.id,
        "gym_name": current_gym.name,
        "billing_module": capabilities,
        "message": (
            "Módulo de facturación activo. Todas las funcionalidades de Stripe están disponibles."
            if capabilities["billing_enabled"]
            else "Módulo de facturación inactivo. Solo membresías manuales disponibles."
        ),
        "available_features": {
            "manual_memberships": True,  # Siempre disponible
            "stripe_checkout": capabilities["stripe_integration"],
            "subscription_management": capabilities["subscription_management"],
            "automated_billing": capabilities["automated_billing"],
            "payment_webhooks": capabilities["webhook_handling"],
            "revenue_analytics": capabilities["revenue_analytics"],
            "refund_processing": capabilities["refund_management"],
            "trial_periods": capabilities["trial_periods"],
            "promotional_codes": capabilities["promo_codes"]
        }
    }


# === Endpoints de Planes de Membresía (Admin) ===

@router.post("/plans", response_model=MembershipPlan, status_code=status.HTTP_201_CREATED)
async def create_membership_plan(
    request: Request,
    plan_data: MembershipPlanCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
) -> MembershipPlan:
    """
    [ADMIN ONLY] Crear un nuevo plan de membresía para el gimnasio actual.
    
    Este endpoint permite a los administradores crear planes de membresía
    con diferentes precios, duraciones y características.
    
    Args:
        plan_data: Datos del plan a crear
        db: Sesión de base de datos
        current_user: Usuario autenticado
        current_gym: Gimnasio verificado (Admin)
        
    Returns:
        MembershipPlan: Plan creado
        
    Raises:
        HTTPException: 403 si no es admin, 400 si datos inválidos
    """
    try:
        # Crear plan usando gym_id del middleware (más limpio)
        plan = await membership_service.create_membership_plan(db, current_gym.id, plan_data)
        logger.info(f"Plan creado por admin {current_user.id}: {plan.name} en gym {current_gym.id}")
        return plan
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/plans", response_model=MembershipPlanList)
async def list_membership_plans(
    request: Request,
    active_only: bool = Query(True, description="Solo planes activos"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=1000, description="Límite de registros"),
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_access)
) -> MembershipPlanList:
    """
    Obtener lista de planes de membresía del gimnasio actual.
    
    Este endpoint permite a cualquier miembro del gimnasio ver los planes
    disponibles para compra.
    
    Args:
        active_only: Si solo mostrar planes activos
        skip: Paginación - registros a omitir
        limit: Paginación - límite de registros
        db: Sesión de base de datos
        current_user: Usuario autenticado
        current_gym: Gimnasio verificado
        
    Returns:
        MembershipPlanList: Lista de planes con metadatos
    """
    plans = membership_service.get_membership_plans(
        db, 
        gym_id=current_gym.id, 
        active_only=active_only,
        skip=skip, 
        limit=limit
    )
    
    return MembershipPlanList(
        plans=plans,
        total=len(plans),
        gym_id=current_gym.id,
        gym_name=current_gym.name
    )


@router.get("/plans/{plan_id}", response_model=MembershipPlan)
async def get_membership_plan(
    request: Request,
    plan_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_access)
) -> MembershipPlan:
    """
    Obtener detalles de un plan específico.
    
    Args:
        plan_id: ID del plan
        db: Sesión de base de datos
        current_user: Usuario autenticado
        current_gym: Gimnasio verificado
        
    Returns:
        MembershipPlan: Detalles del plan
        
    Raises:
        HTTPException: 404 si el plan no existe o no pertenece al gym
    """
    plan = membership_service.get_membership_plan(db, plan_id)
    
    if not plan or plan.gym_id != current_gym.id:
        raise HTTPException(
            status_code=404, 
            detail="Plan de membresía no encontrado en este gimnasio"
        )
    
    return plan


# 🆕 NUEVO ENDPOINT: Estadísticas de Usuarios por Plan de Membresía
@router.get("/plans-stats")
async def get_membership_plans_stats(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
):
    """
    📊 **Estadísticas de usuarios por plan de membresía**
    
    Este endpoint proporciona estadísticas detalladas sobre la cantidad de usuarios
    asociados a cada plan de membresía y tipos de membresía en el gimnasio.
    
    **Información Proporcionada:**
    
    **Por cada plan:**
    - Información básica del plan (nombre, precio, duración)
    - Número de usuarios activos vinculados
    - IDs de usuarios asociados al plan
    - Tipos de membresía asociados
    - Ingresos estimados
    
    **Estadísticas generales:**
    - Total de usuarios activos por tipo de membresía
    - Usuarios con membresías expiradas
    - Usuarios con membresías de prueba
    - Distribución por tipo de pago
    
    **Casos de Uso:**
    - 📈 Dashboard administrativo
    - 💰 Análisis de ingresos por plan
    - 🎯 Identificación de planes más populares
    - 📊 Reportes de membresías
    - 👥 Lista de usuarios por plan específico
    
    Args:
        db: Sesión de base de datos
        current_user: Usuario administrador autenticado
        current_gym: Gimnasio verificado
        
    Returns:
        dict: Estadísticas completas de planes y usuarios
    """
    from app.models.membership import MembershipPlan
    from app.models.user_gym import UserGym
    from app.models.user import User
    from datetime import datetime

    # Obtener todos los planes del gimnasio
    result = await db.execute(select(MembershipPlan).where(
        MembershipPlan.gym_id == current_gym.id
    ))
    plans = result.scalars().all()
    
    # Estadísticas generales de usuarios en el gimnasio
    now = datetime.utcnow()
    
    # Usuarios activos por tipo de membresía
    result = await db.execute(select(func.count()).select_from(UserGym).where(
    UserGym.gym_id == current_gym.id
    ))
 total_users = result.scalar()
    
    # ✅ MIGRADO A ASYNC: count con filtros complejos
    result_active = await db.execute(
        select(func.count())
        .select_from(UserGym)
        .where(
            UserGym.gym_id == current_gym.id,
            UserGym.is_active == True,
            (UserGym.membership_expires_at.is_(None)) | (UserGym.membership_expires_at > now)
        )
    )
    active_users = result_active.scalar() or 0
    
    result = await db.execute(select(func.count()).select_from(UserGym).where(
        UserGym.gym_id == current_gym.id,
        UserGym.membership_expires_at < now
    ))
 expired_users = result.scalar()
    
    # Usuarios por tipo de membresía
    # ✅ MIGRADO A ASYNC: query con group_by y aggregates
    result_types = await db.execute(
        select(
            UserGym.membership_type,
            func.count(UserGym.id).label('count')
        )
        .where(
            UserGym.gym_id == current_gym.id,
            UserGym.is_active == True
        )
        .group_by(UserGym.membership_type)
    )
    membership_types = result_types.all()
    
    # Convertir a diccionario para fácil acceso
    membership_type_counts = {mt[0]: mt[1] for mt in membership_types}
    
    # Estadísticas por plan
    plans_stats = []
    total_estimated_monthly_revenue = 0
    
    for plan in plans:
        # Obtener usuarios vinculados a este plan usando asociación precisa
        plan_users = []
        plan_user_ids = set()
        
        # 🎯 ESTRATEGIA PRINCIPAL: Usar nueva tabla UserGymSubscription
        # Buscar usuarios con suscripciones activas usando la nueva arquitectura
        if plan.stripe_price_id:
            # 🆕 USAR TABLA DE SUSCRIPCIONES VINCULADAS
            from app.models.stripe_profile import UserGymStripeProfile
            from app.models.user_gym_subscription import UserGymSubscription
            
            # Buscar suscripciones activas para este plan específico
            # ✅ MIGRADO A ASYNC: joins múltiples entre 4 tablas
            result_subs = await db.execute(
                select(UserGymSubscription, UserGymStripeProfile, UserGym, User)
                .join(UserGymStripeProfile, UserGymSubscription.user_gym_stripe_profile_id == UserGymStripeProfile.id)
                .join(
                    UserGym, and_(
                        UserGymStripeProfile.user_id == UserGym.user_id,
                        UserGymStripeProfile.gym_id == UserGym.gym_id
                    )
                )
                .join(User, UserGym.user_id == User.id)
                .where(
                    UserGymStripeProfile.gym_id == current_gym.id,
                    UserGymSubscription.plan_id == plan.id,
                    UserGymSubscription.status == "active",
                    UserGymStripeProfile.is_active == True,
                    UserGym.is_active == True
                )
            )
            plan_subscriptions = result_subs.all()
            
            # Procesar suscripciones encontradas
            for subscription, stripe_profile, user_gym, user in plan_subscriptions:
                try:
                    # 🆕 VERIFICACIÓN OPCIONAL CON STRIPE (para validar estado)
                    stripe_status = "active"  # Por defecto asumir activo
                    
                    try:
                        import stripe
                        stripe_subscription = stripe.Subscription.retrieve(
                            subscription.stripe_subscription_id,
                            stripe_account=stripe_profile.stripe_account_id
                        )
                        stripe_status = stripe_subscription.status
                    except Exception as stripe_error:
                        logger.warning(f"Error verificando suscripción en Stripe {subscription.stripe_subscription_id}: {str(stripe_error)}")
                        # Continuar con datos locales
                    
                    # Solo incluir si está activa (localmente o en Stripe)
                    if subscription.status == "active" and stripe_status in ["active", "trialing"]:
                        plan_users.append({
                            "user_id": user.id,
                            "user_gym_id": user_gym.id,
                            "email": user.email,
                            "first_name": user.first_name,
                            "last_name": user.last_name,
                            "membership_type": user_gym.membership_type,
                            "expires_at": user_gym.membership_expires_at,
                            "stripe_subscription_id": subscription.stripe_subscription_id,
                            "stripe_customer_id": stripe_profile.stripe_customer_id,
                            "subscription_status": subscription.status,
                            "stripe_status": stripe_status,
                            "association_method": "user_gym_subscription_table"
                        })
                        plan_user_ids.add(user.id)
                        
                except Exception as e:
                    logger.warning(f"Error procesando suscripción {subscription.id}: {str(e)}")
                    continue
        
        # 🔍 ESTRATEGIA SECUNDARIA: Asociación por metadatos en notas
        # Solo si hay referencia explícita al plan en las notas
        if not plan_users:  # Solo si no encontramos usuarios por Stripe
            # ✅ MIGRADO A ASYNC: join con contains filter
            result_notes = await db.execute(
                select(UserGym, User)
                .join(User, UserGym.user_id == User.id)
                .where(
                    UserGym.gym_id == current_gym.id,
                    UserGym.is_active == True,
                    UserGym.notes.isnot(None),
                    UserGym.notes.contains(f"plan_id:{plan.id}")  # Referencia específica al plan
                )
            )
            notes_users = result_notes.all()
            
            for user_gym, user in notes_users:
                if user.id not in plan_user_ids:
                    plan_users.append({
                        "user_id": user.id,
                        "user_gym_id": user_gym.id,
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "membership_type": user_gym.membership_type,
                        "expires_at": user_gym.membership_expires_at,
                        "notes": user_gym.notes,
                        "association_method": "notes_reference"
                    })
                    plan_user_ids.add(user.id)
        
        # Calcular ingresos basados en usuarios reales encontrados
        actual_users_count = len(plan_users)
        monthly_revenue = 0
        
        if plan.billing_interval == 'month':
            monthly_revenue = (plan.price_cents / 100) * actual_users_count
        elif plan.billing_interval == 'year':
            monthly_revenue = (plan.price_cents / 100) * actual_users_count / 12
        elif plan.billing_interval == 'one_time':
            # Para one_time, calculamos ingresos mensuales promediados
            monthly_revenue = (plan.price_cents / 100) * actual_users_count / (plan.duration_days / 30)
        
        total_estimated_monthly_revenue += monthly_revenue
        
        # Extraer solo los IDs para una respuesta más limpia
        user_ids_only = [user["user_id"] for user in plan_users]
        
        plan_stats = {
            "plan": {
                "id": plan.id,
                "name": plan.name,
                "description": plan.description,
                "price_amount": plan.price_cents / 100,
                "currency": plan.currency,
                "billing_interval": plan.billing_interval,
                "duration_days": plan.duration_days,
                "is_active": plan.is_active,
                "created_at": plan.created_at
            },
            "users_count": actual_users_count,
            "user_ids": user_ids_only,
            "users_details": plan_users,  # Información detallada de usuarios
            "estimated_monthly_revenue": round(monthly_revenue, 2)
        }
        
        plans_stats.append(plan_stats)
    
    # Usuarios recientes (últimos 30 días)
    # ✅ MIGRADO A ASYNC: count con filtro de fecha
    result_recent = await db.execute(
        select(func.count())
        .select_from(UserGym)
        .where(
            UserGym.gym_id == current_gym.id,
            UserGym.created_at >= now - timedelta(days=30)
        )
    )
    recent_users = result_recent.scalar() or 0
    
    # Usuarios con membresías próximas a expirar (próximos 7 días)
    # ✅ MIGRADO A ASYNC: count con filtros de rango de fechas
    result_expiring = await db.execute(
        select(func.count())
        .select_from(UserGym)
        .where(
            UserGym.gym_id == current_gym.id,
            UserGym.is_active == True,
            UserGym.membership_expires_at > now,
            UserGym.membership_expires_at <= now + timedelta(days=7)
        )
    )
    expiring_soon = result_expiring.scalar() or 0
    
    return {
        "summary": {
            "total_users": total_users,
            "active_users": active_users,
            "expired_users": expired_users,
            "recent_users_30_days": recent_users,
            "expiring_soon_7_days": expiring_soon,
            "estimated_monthly_revenue": round(total_estimated_monthly_revenue, 2),
            "currency": plans[0].currency if plans else "EUR"
        },
        "membership_types": {
            "free": membership_type_counts.get('free', 0),
            "paid": membership_type_counts.get('paid', 0),
            "trial": membership_type_counts.get('trial', 0)
        },
        "plans_statistics": plans_stats,
        "analysis": {
            "most_popular_plan": max(plans_stats, key=lambda x: x["users_count"]) if plans_stats else None,
            "highest_revenue_plan": max(plans_stats, key=lambda x: x["estimated_monthly_revenue"]) if plans_stats else None,
            "total_active_plans": sum(1 for p in plans if p.is_active),
            "total_inactive_plans": sum(1 for p in plans if not p.is_active)
        },
        "generated_at": datetime.utcnow()
    }


@router.put("/plans/{plan_id}", response_model=MembershipPlan)
async def update_membership_plan(
    request: Request,
    plan_id: int,
    plan_update: MembershipPlanUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
) -> MembershipPlan:
    """
    [ADMIN ONLY] Actualizar un plan de membresía.
    
    Args:
        plan_id: ID del plan a actualizar
        plan_update: Datos a actualizar
        db: Sesión de base de datos
        current_user: Usuario autenticado (Admin)
        current_gym: Gimnasio verificado
        
    Returns:
        MembershipPlan: Plan actualizado
        
    Raises:
        HTTPException: 404 si no se encuentra, 403 si no es admin
    """
    # Verificar que el plan pertenece al gym actual
    existing_plan = membership_service.get_membership_plan(db, plan_id)
    if not existing_plan or existing_plan.gym_id != current_gym.id:
        raise HTTPException(
            status_code=404,
            detail="Plan no encontrado en este gimnasio"
        )
    
    updated_plan = await membership_service.update_membership_plan(db, plan_id, plan_update)
    if not updated_plan:
        raise HTTPException(status_code=404, detail="Error al actualizar plan")
    
    logger.info(f"Plan {plan_id} actualizado por admin {current_user.id}")
    return updated_plan


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_membership_plan(
    request: Request,
    plan_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
):
    """
    [ADMIN ONLY] Eliminar (desactivar) un plan de membresía.
    
    Args:
        plan_id: ID del plan a eliminar
        db: Sesión de base de datos
        current_user: Usuario autenticado (Admin)
        current_gym: Gimnasio verificado
        
    Raises:
        HTTPException: 404 si no se encuentra, 403 si no es admin
    """
    # Verificar que el plan pertenece al gym actual
    existing_plan = membership_service.get_membership_plan(db, plan_id)
    if not existing_plan or existing_plan.gym_id != current_gym.id:
        raise HTTPException(
            status_code=404,
            detail="Plan no encontrado en este gimnasio"
        )
    
    success = await membership_service.delete_membership_plan(db, plan_id)
    if not success:
        raise HTTPException(status_code=404, detail="Error al eliminar plan")
    
    logger.info(f"Plan {plan_id} eliminado por admin {current_user.id}")


# === Endpoints de Sincronización con Stripe ===

@router.post("/plans/{plan_id}/sync-stripe", status_code=status.HTTP_200_OK)
async def sync_plan_with_stripe(
    request: Request,
    plan_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    _: None = Depends(billing_module_required)
) -> dict:
    """
    [ADMIN ONLY] Sincronizar manualmente un plan específico con Stripe.
    
    Args:
        plan_id: ID del plan a sincronizar
        db: Sesión de base de datos
        current_user: Usuario autenticado (Admin)
        current_gym: Gimnasio verificado
        
    Returns:
        dict: Resultado de la sincronización
        
    Raises:
        HTTPException: 404 si no se encuentra el plan
    """
    # Verificar que el plan pertenece al gym actual
    existing_plan = membership_service.get_membership_plan(db, plan_id)
    if not existing_plan or existing_plan.gym_id != current_gym.id:
        raise HTTPException(
            status_code=404,
            detail="Plan no encontrado en este gimnasio"
        )
    
    success = await membership_service.sync_plan_with_stripe_manual(db, plan_id)
    
    if success:
        logger.info(f"Plan {plan_id} sincronizado manualmente con Stripe por admin {current_user.id}")
        return {
            "message": "Plan sincronizado exitosamente con Stripe",
            "plan_id": plan_id,
            "stripe_product_id": existing_plan.stripe_product_id,
            "stripe_price_id": existing_plan.stripe_price_id
        }
    else:
        logger.error(f"Falló sincronización manual del plan {plan_id} por admin {current_user.id}")
        raise HTTPException(
            status_code=500,
            detail="Error al sincronizar con Stripe. Ver logs para detalles."
        )


@router.post("/sync-all-stripe", status_code=status.HTTP_200_OK)
async def sync_all_plans_with_stripe(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    _: None = Depends(billing_module_required)
) -> dict:
    """
    [ADMIN ONLY] Sincronizar todos los planes del gimnasio con Stripe.
    
    Args:
        db: Sesión de base de datos
        current_user: Usuario autenticado (Admin)
        current_gym: Gimnasio verificado
        
    Returns:
        dict: Resumen de la sincronización masiva
    """
    result = await membership_service.sync_all_plans_with_stripe(db, current_gym.id)
    
    logger.info(f"Sincronización masiva ejecutada por admin {current_user.id}: {result['synced']}/{result['total']}")
    
    return {
        "message": f"Sincronización completada: {result['synced']}/{result['total']} planes",
        "total_plans": result['total'],
        "synced_successfully": result['synced'],
        "failed": result['failed'],
        "details": result['details']
    }


# === Endpoints de Estado de Membresía (Usuario) ===

@router.get("/my-status", response_model=MembershipStatus)
async def get_my_membership_status(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_access)
) -> MembershipStatus:
    """
    Obtener el estado de membresía del usuario actual en el gimnasio actual.
    
    Args:
        db: Sesión de base de datos
        current_user: Usuario autenticado
        current_gym: Gimnasio verificado
        
    Returns:
        MembershipStatus: Estado detallado de la membresía
    """
    # Obtener usuario local
    local_user = await user_service.get_user_by_auth0_id_cached(
        db, current_user.id, None  # No necesitamos redis para esta consulta simple
    )
    
    if not local_user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado en el sistema local"
        )
    
    status_info = membership_service.get_membership_status(
        db, local_user.id, current_gym.id
    )
    
    return status_info


@router.get("/user/{user_id}/status", response_model=MembershipStatus)
async def get_user_membership_status(
    request: Request,
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
) -> MembershipStatus:
    """
    [ADMIN ONLY] Obtener estado de membresía de un usuario específico.
    
    Args:
        user_id: ID del usuario a consultar
        db: Sesión de base de datos
        current_user: Usuario autenticado (Admin)
        current_gym: Gimnasio verificado
        
    Returns:
        MembershipStatus: Estado de la membresía del usuario
    """
    status_info = membership_service.get_membership_status(
        db, user_id, current_gym.id
    )
    
    return status_info


# === Endpoints de Resumen (Admin) ===

@router.get("/summary", response_model=MembershipSummary)
async def get_membership_summary(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
) -> MembershipSummary:
    """
    [ADMIN ONLY] Obtener resumen de membresías del gimnasio.
    
    Args:
        db: Sesión de base de datos
        current_user: Usuario autenticado (Admin)
        current_gym: Gimnasio verificado
        
    Returns:
        MembershipSummary: Estadísticas del gimnasio
    """
    summary = membership_service.get_gym_membership_summary(db, current_gym.id)
    
    logger.info(f"Resumen consultado por admin {current_user.id} para gym {current_gym.id}")
    return summary


# === Endpoints de Compra de Membresías (Stripe) ===

@router.post("/purchase", response_model=PurchaseMembershipResponse)
@limiter.limit("5 per minute")
async def purchase_membership(
    request: Request,
    purchase_data: PurchaseMembershipRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_access),
    _: None = Depends(billing_module_required)
) -> PurchaseMembershipResponse:
    """
    Iniciar compra de membresía con Stripe.
    
    Este endpoint crea una sesión de checkout de Stripe para que el usuario
    pueda completar el pago de forma segura.
    
    Args:
        purchase_data: Datos de compra (plan_id, URLs opcionales)
        db: Sesión de base de datos
        current_user: Usuario autenticado
        current_gym: Gimnasio verificado
        
    Returns:
        PurchaseMembershipResponse: URL de checkout y detalles del plan
        
    Raises:
        HTTPException: 404 si el plan no existe, 400 si hay error de Stripe
    """
    try:
        # Log del request recibido
        logger.info(f"📥 Solicitud de compra recibida - Plan ID: {purchase_data.plan_id}, Usuario: {current_user.id}, Gym: {current_gym.id}")
        
        # Verificar que el plan existe y pertenece al gimnasio actual
        logger.info(f"🔍 Validando plan {purchase_data.plan_id} para gym {current_gym.id}")
        plan = membership_service.get_membership_plan(db, purchase_data.plan_id)
        
        if not plan:
            logger.error(f"❌ Plan {purchase_data.plan_id} no encontrado en la base de datos")
            
            # Obtener planes disponibles para sugerir al usuario
            available_plans = membership_service.get_membership_plans(
                db, gym_id=current_gym.id, active_only=True, skip=0, limit=10
            )
            available_ids = [p.id for p in available_plans]
            
            detail_msg = f"El plan de membresía con ID {purchase_data.plan_id} no existe."
            if available_ids:
                detail_msg += f" Planes disponibles: {available_ids}"
            else:
                detail_msg += " No hay planes activos disponibles en este gimnasio."
                
            raise HTTPException(status_code=404, detail=detail_msg)
            
        if plan.gym_id != current_gym.id:
            logger.error(f"❌ Plan {purchase_data.plan_id} pertenece a gym {plan.gym_id}, no a {current_gym.id}")
            raise HTTPException(
                status_code=403,
                detail=f"El plan '{plan.name}' no está disponible en este gimnasio. Contacta al administrador."
            )
        
        logger.info(f"✅ Plan encontrado: {plan.name} - Activo: {plan.is_active}")
        
        if not plan.is_active:
            logger.error(f"❌ Plan {purchase_data.plan_id} está inactivo")
            raise HTTPException(
                status_code=400,
                detail=f"El plan '{plan.name}' está temporalmente desactivado. Selecciona otro plan o contacta al gimnasio."
            )
            
        # Verificar que el plan tenga configuración de Stripe
        if not plan.stripe_price_id:
            logger.error(f"❌ Plan {purchase_data.plan_id} no tiene configuración de Stripe")
            raise HTTPException(
                status_code=503,
                detail=f"El plan '{plan.name}' no está configurado para pagos. Contacta al administrador del gimnasio."
            )

        # Obtener usuario local para usar su ID numérico
        logger.info(f"🔍 Buscando usuario local para auth0_id: {current_user.id}")
        redis_client = get_redis_client()
        local_user = await user_service.get_user_by_auth0_id_cached(
            db, current_user.id, redis_client
        )
        
        if not local_user:
            logger.error(f"❌ Usuario {current_user.id} no encontrado en sistema local")
            raise HTTPException(
                status_code=404,
                detail="Usuario no encontrado en el sistema local"
            )
            
        logger.info(f"✅ Usuario local encontrado: ID {local_user.id}")

        # Crear sesión de checkout con Stripe
        logger.info(f"🔍 Creando checkout session - User: {local_user.id}, Gym: {current_gym.id}, Plan: {purchase_data.plan_id}")
        checkout_data = await stripe_service.create_checkout_session(
            db=db,
            user_id=str(local_user.id),  # Stripe necesita string
            gym_id=current_gym.id,
            plan_id=purchase_data.plan_id,
            success_url=purchase_data.success_url,
            cancel_url=purchase_data.cancel_url
        )
        
        logger.info(f"Checkout iniciado para usuario {current_user.id} en gym {current_gym.id}, plan {purchase_data.plan_id}")
        
        return PurchaseMembershipResponse(
            checkout_url=checkout_data['checkout_url'],
            session_id=checkout_data['checkout_session_id'],
            plan_name=checkout_data['plan_name'],
            price_amount=checkout_data['price'],
            currency=checkout_data['currency']
        )
        
    except ValueError as e:
        logger.error(f"❌ ValueError en compra: {str(e)}")
        # Los ValueError de Stripe suelen ser problemas de configuración
        if "stripe" in str(e).lower():
            raise HTTPException(
                status_code=503, 
                detail=f"Error de configuración de pagos: {str(e)}"
            )
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        # Re-raise HTTPExceptions para mantener el status code original
        raise
    except Exception as e:
        logger.error(f"❌ Error inesperado en compra: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="Error interno del servidor. Si el problema persiste, contacta al soporte técnico."
        )


@router.post("/admin/create-payment-link", response_model=AdminPaymentLinkResponse)
@limiter.limit("10 per minute")
async def admin_create_payment_link(
    request: Request,
    payment_data: AdminCreatePaymentLinkRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    _: None = Depends(billing_module_required)
) -> AdminPaymentLinkResponse:
    """
    Crear link de pago administrativo para un usuario específico.
    
    Este endpoint permite a los administradores crear links de pago
    personalizados para usuarios específicos. Útil para ventas directas,
    pagos manuales o cuando un usuario necesita ayuda con el proceso.
    
    Args:
        payment_data: Datos del link de pago (user_id, plan_id, URLs opcionales, notas)
        db: Sesión de base de datos
        current_user: Administrador autenticado
        current_gym: Gimnasio verificado
        
    Returns:
        AdminPaymentLinkResponse: URL de checkout y detalles completos
        
    Raises:
        HTTPException: 404 si el usuario/plan no existe, 400 si hay error de Stripe
    """
    try:
        # Log del request recibido
        logger.info(f"📥 Solicitud ADMIN de link de pago - Plan ID: {payment_data.plan_id}, Usuario: {payment_data.user_id}, Admin: {current_user.id}")
        
        # Verificar que el plan existe y pertenece al gimnasio actual
        logger.info(f"🔍 Validando plan {payment_data.plan_id} para gym {current_gym.id}")
        plan = membership_service.get_membership_plan(db, payment_data.plan_id)
        
        if not plan:
            logger.error(f"❌ Plan {payment_data.plan_id} no encontrado en la base de datos")
            raise HTTPException(
                status_code=404,
                detail=f"El plan de membresía con ID {payment_data.plan_id} no existe."
            )
            
        if plan.gym_id != current_gym.id:
            logger.error(f"❌ Plan {payment_data.plan_id} pertenece a gym {plan.gym_id}, no a {current_gym.id}")
            raise HTTPException(
                status_code=403,
                detail=f"El plan '{plan.name}' no está disponible en este gimnasio."
            )
        
        if not plan.is_active:
            logger.error(f"❌ Plan {payment_data.plan_id} está inactivo")
            raise HTTPException(
                status_code=400,
                detail=f"El plan '{plan.name}' está temporalmente desactivado."
            )
            
        # Verificar que el plan tenga configuración de Stripe
        if not plan.stripe_price_id:
            logger.error(f"❌ Plan {payment_data.plan_id} no tiene configuración de Stripe")
            raise HTTPException(
                status_code=503,
                detail=f"El plan '{plan.name}' no está configurado para pagos. Contacta al administrador del gimnasio."
            )

        # Verificar que el usuario existe en el sistema
        logger.info(f"🔍 Validando usuario {payment_data.user_id}")
        from app.models.user import User
        result = await db.execute(select(User).where(User.id == payment_data.user_id))
    target_user = result.scalar_one_or_none()
        
        if not target_user:
            logger.error(f"❌ Usuario {payment_data.user_id} no encontrado")
            raise HTTPException(
                status_code=404,
                detail=f"El usuario con ID {payment_data.user_id} no existe."
            )

        # Verificar que el usuario tiene acceso al gimnasio (opcional - puede ser para invitar nuevos usuarios)
        from app.models.user_gym import UserGym
        result = await db.execute(select(UserGym).where(
            UserGym.user_id == payment_data.user_id,
            UserGym.gym_id == current_gym.id
        ))
    user_gym_relation = result.scalar_one_or_none()
        
        if not user_gym_relation:
            logger.info(f"ℹ️ Usuario {payment_data.user_id} no está registrado en gym {current_gym.id} - creando link para nuevo miembro")
        
        logger.info(f"✅ Usuario encontrado: {target_user.email}")
        
        # Crear sesión de checkout administrativa con Stripe
        logger.info(f"🔍 Creando checkout session ADMIN - User: {payment_data.user_id}, Gym: {current_gym.id}, Plan: {payment_data.plan_id}")
        checkout_data = await stripe_service.create_admin_checkout_session(
            db=db,
            user_id=str(payment_data.user_id),
            gym_id=current_gym.id,
            plan_id=payment_data.plan_id,
            admin_email=current_user.email,
            notes=payment_data.notes,
            expires_in_hours=payment_data.expires_in_hours or 24,
            success_url=payment_data.success_url,
            cancel_url=payment_data.cancel_url
        )
        
        logger.info(f"✅ Link de pago administrativo creado por {current_user.email} para usuario {target_user.email}")
        
        return AdminPaymentLinkResponse(
            checkout_url=checkout_data['checkout_url'],
            session_id=checkout_data['checkout_session_id'],
            plan_name=checkout_data['plan_name'],
            price_amount=checkout_data['price'],
            currency=checkout_data['currency'],
            user_email=checkout_data['user_email'],
            user_name=checkout_data['user_name'],
            expires_at=checkout_data['expires_at'],
            notes=checkout_data['notes'],
            created_by_admin=checkout_data['created_by_admin']
        )
        
    except ValueError as e:
        logger.error(f"❌ ValueError en creación admin: {str(e)}")
        if "stripe" in str(e).lower():
            raise HTTPException(
                status_code=503, 
                detail=f"Error de configuración de pagos: {str(e)}"
            )
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        # Re-raise HTTPExceptions para mantener el status code original
        raise
    except Exception as e:
        logger.error(f"❌ Error inesperado en creación admin: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="Error interno del servidor. Si el problema persiste, contacta al soporte técnico."
        )


@router.post("/purchase/success")
async def handle_purchase_success(
    request: Request,
    session_id: str = Query(..., description="ID de sesión de Stripe"),
    db: AsyncSession = Depends(get_async_db)
) -> PurchaseMembershipResponse:
    """
    Manejar confirmación de pago exitoso desde Stripe.
    
    Este endpoint se llama cuando el usuario regresa de Stripe después
    de completar un pago exitoso.
    
    Args:
        session_id: ID de la sesión de checkout de Stripe
        db: Sesión de base de datos
        
    Returns:
        PurchaseMembershipResponse: Confirmación de activación de membresía
    """
    try:
        result = await stripe_service.handle_successful_payment(db, session_id)
        logger.info(f"Pago procesado exitosamente: {session_id}")
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al procesar pago exitoso: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/webhooks/stripe")
@limiter.limit("100 per minute")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Webhook para manejar eventos de Stripe.
    
    Este endpoint recibe notificaciones de Stripe sobre eventos como:
    - Pagos completados
    - Suscripciones canceladas
    - Pagos fallidos
    
    Args:
        request: Request con payload y headers de Stripe
        db: Sesión de base de datos
        
    Returns:
        dict: Confirmación de recepción
    """
    try:
        # Obtener payload y signature del header
        payload = await request.body()
        signature = request.headers.get('stripe-signature')
        
        if not signature:
            raise HTTPException(
                status_code=400, 
                detail="Falta signature de Stripe"
            )
        
        # Procesar el webhook
        result = await stripe_service.handle_webhook(payload, signature)
        
        logger.info(f"Webhook de Stripe procesado: {result.get('event_type', 'unknown')}")
        return {"received": True, "status": result.get("status", "processed")}
        
    except ValueError as e:
        logger.error(f"Error en webhook de Stripe: {str(e)}")
        # Devolver 200 para que Stripe no reintente
        return {
            "received": True,
            "status": "error",
            "error": "validation_error",
            "message": str(e)
        }
    except Exception as e:
        logger.error(f"Error inesperado en webhook: {str(e)}")
        # Devolver 200 para que Stripe no reintente indefinidamente
        return {
            "received": True,
            "status": "error", 
            "error": "processing_error",
            "message": "Error interno procesando webhook"
        }


# 🆕 ENDPOINTS PARA FUNCIONALIDADES AVANZADAS

@router.post("/purchase/trial", response_model=PurchaseMembershipResponse)
@limiter.limit("3 per minute")
async def purchase_membership_with_trial(
    request: Request,
    purchase_data: PurchaseMembershipRequest,
    trial_days: int = Query(7, description="Días de prueba gratuita", ge=1, le=30),
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_access)
) -> PurchaseMembershipResponse:
    """
    Iniciar compra de membresía con período de prueba.
    
    Este endpoint crea una sesión de checkout con período de prueba gratuito.
    Solo aplica a planes de suscripción (mensual/anual).
    """
    try:
        # Obtener usuario local
        redis_client = get_redis_client()
        local_user = await user_service.get_user_by_auth0_id_cached(
            db, current_user.id, redis_client
        )
        
        if not local_user:
            raise HTTPException(
                status_code=404,
                detail="Usuario no encontrado en el sistema local"
            )

        # Crear sesión de checkout con prueba
        checkout_data = await stripe_service.create_checkout_session_with_trial(
            db=db,
            user_id=str(local_user.id),
            gym_id=current_gym.id,
            plan_id=purchase_data.plan_id,
            trial_days=trial_days,
            success_url=purchase_data.success_url,
            cancel_url=purchase_data.cancel_url
        )
        
        return PurchaseMembershipResponse(
            checkout_url=checkout_data['checkout_url'],
            session_id=checkout_data['checkout_session_id'],
            plan_name=checkout_data['plan_name'],
            price_amount=checkout_data['price'],
            currency=checkout_data['currency'],
            message=f"Período de prueba de {trial_days} días incluido"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error en compra con prueba: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/refunds", status_code=status.HTTP_201_CREATED)
async def create_refund(
    request: Request,
    charge_id: str = Query(..., description="ID del charge a reembolsar"),
    amount: Optional[int] = Query(None, description="Cantidad en centavos (None = reembolso completo)"),
    reason: str = Query("requested_by_customer", description="Razón del reembolso"),
    db: AsyncSession = Depends(get_async_db),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    current_user: Auth0User = Depends(auth.get_user)
):
    """
    Crear un reembolso para un pago (solo administradores).
    
    Args:
        charge_id: ID del charge en Stripe
        amount: Cantidad a reembolsar en centavos (opcional)
        reason: Razón del reembolso
        
    Returns:
        dict: Información del reembolso creado
    """
    try:
        refund_data = await stripe_service.create_refund(
            charge_id=charge_id,
            amount=amount,
            reason=reason,
            metadata={
                'gym_id': str(current_gym.id),
                'admin_user': current_user.id,
                'requested_at': datetime.now().isoformat()
            }
        )
        
        logger.info(f"Reembolso creado por admin {current_user.id} en gym {current_gym.id}")
        
        return {
            "message": "Reembolso creado exitosamente",
            "refund": refund_data
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creando reembolso: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/customers/{customer_id}/payment-methods")
async def get_customer_payment_methods(
    customer_id: str = Path(..., description="ID del cliente en Stripe"),
    db: AsyncSession = Depends(get_async_db),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    current_user: Auth0User = Depends(auth.get_user)
):
    """
    Obtener métodos de pago de un cliente (solo administradores).
    
    Args:
        customer_id: ID del cliente en Stripe
        
    Returns:
        List: Métodos de pago del cliente
    """
    try:
        # 🆕 Verificar que el cliente pertenezca al gimnasio actual usando nueva arquitectura
        from app.models.stripe_profile import UserGymStripeProfile
        from app.models.user_gym import UserGym
        
        # ✅ MIGRADO A ASYNC: join con and_() condition
        result_customer = await db.execute(
            select(UserGymStripeProfile, UserGym)
            .join(
                UserGym, and_(
                    UserGymStripeProfile.user_id == UserGym.user_id,
                    UserGymStripeProfile.gym_id == UserGym.gym_id
                )
            )
            .where(
                UserGymStripeProfile.stripe_customer_id == customer_id,
                UserGymStripeProfile.gym_id == current_gym.id
            )
        )
        customer_record = result_customer.first()
        
        if not customer_record:
            raise HTTPException(
                status_code=403, 
                detail="Cliente no pertenece a este gimnasio"
            )
        
        stripe_profile, user_gym = customer_record
        
        # 🆕 Obtener métodos de pago usando la cuenta del gym
        import stripe
        payment_methods = stripe.PaymentMethod.list(
            customer=customer_id,
            type='card',
            stripe_account=stripe_profile.stripe_account_id
        )
        
        formatted_methods = [
            {
                'id': pm.id,
                'type': pm.type,
                'card': {
                    'brand': pm.card.brand,
                    'last4': pm.card.last4,
                    'exp_month': pm.card.exp_month,
                    'exp_year': pm.card.exp_year
                } if pm.card else None,
                'created': pm.created
            }
            for pm in payment_methods.data
        ]
        
        return {
            "customer_id": customer_id,
            "payment_methods": formatted_methods,
            "user_id": user_gym.user_id,
            "stripe_account_id": stripe_profile.stripe_account_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo métodos de pago: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/subscriptions/{subscription_id}/status")
async def get_subscription_status(
    subscription_id: str = Path(..., description="ID de la suscripción en Stripe"),
    db: AsyncSession = Depends(get_async_db),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    current_user: Auth0User = Depends(auth.get_user)
):
    """
    Obtener estado detallado de una suscripción (solo administradores).
    
    Args:
        subscription_id: ID de la suscripción en Stripe
        
    Returns:
        dict: Estado y detalles de la suscripción
    """
    try:
        # 🆕 Verificar que la suscripción pertenezca al gimnasio actual usando nueva arquitectura
        from app.models.user_gym_subscription import UserGymSubscription
        from app.models.stripe_profile import UserGymStripeProfile
        from app.models.user_gym import UserGym
        
        # ✅ MIGRADO A ASYNC: joins múltiples entre 3 tablas
        result_sub = await db.execute(
            select(UserGymSubscription, UserGymStripeProfile, UserGym)
            .join(UserGymStripeProfile, UserGymSubscription.user_gym_stripe_profile_id == UserGymStripeProfile.id)
            .join(
                UserGym, and_(
                    UserGymStripeProfile.user_id == UserGym.user_id,
                    UserGymStripeProfile.gym_id == UserGym.gym_id
                )
            )
            .where(
                UserGymSubscription.stripe_subscription_id == subscription_id,
                UserGymStripeProfile.gym_id == current_gym.id
            )
        )
        subscription_record = result_sub.first()
        
        if not subscription_record:
            raise HTTPException(
                status_code=403, 
                detail="Suscripción no pertenece a este gimnasio"
            )
        
        subscription_data, stripe_profile, user_gym = subscription_record
        
        import stripe
        
        # 🆕 Obtener suscripción desde la cuenta del gym
        subscription = stripe.Subscription.retrieve(
            subscription_id,
            stripe_account=stripe_profile.stripe_account_id
        )
        
        return {
            "subscription_id": subscription.id,
            "status": subscription.status,
            "current_period_start": subscription.current_period_start,
            "current_period_end": subscription.current_period_end,
            "trial_start": subscription.trial_start,
            "trial_end": subscription.trial_end,
            "cancel_at": subscription.cancel_at,
            "canceled_at": subscription.canceled_at,
            "customer": subscription.customer,
            "latest_invoice": subscription.latest_invoice,
            "user_id": user_gym.user_id,
            "plan_id": subscription_data.plan_id,
            "local_status": subscription_data.status
        }
        
    except HTTPException:
        raise
    except stripe.error.StripeError as e:
        logger.error(f"Error obteniendo suscripción: {str(e)}")
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/subscriptions/{subscription_id}/cancel")
async def cancel_subscription_endpoint(
    subscription_id: str = Path(..., description="ID de la suscripción en Stripe"),
    immediately: bool = Query(False, description="Cancelar inmediatamente o al final del período"),
    db: AsyncSession = Depends(get_async_db),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    current_user: Auth0User = Depends(auth.get_user)
):
    """
    Cancelar una suscripción (solo administradores).
    
    Args:
        subscription_id: ID de la suscripción en Stripe
        immediately: Si cancelar inmediatamente o al final del período
        
    Returns:
        dict: Confirmación de cancelación
    """
    try:
        # 🆕 Verificar que la suscripción pertenezca al gimnasio actual usando nueva arquitectura
        from app.models.user_gym_subscription import UserGymSubscription
        from app.models.stripe_profile import UserGymStripeProfile
        from app.models.user_gym import UserGym
        
        # ✅ MIGRADO A ASYNC: joins múltiples entre 3 tablas
        result_sub = await db.execute(
            select(UserGymSubscription, UserGymStripeProfile, UserGym)
            .join(UserGymStripeProfile, UserGymSubscription.user_gym_stripe_profile_id == UserGymStripeProfile.id)
            .join(
                UserGym, and_(
                    UserGymStripeProfile.user_id == UserGym.user_id,
                    UserGymStripeProfile.gym_id == UserGym.gym_id
                )
            )
            .where(
                UserGymSubscription.stripe_subscription_id == subscription_id,
                UserGymStripeProfile.gym_id == current_gym.id
            )
        )
        subscription_record = result_sub.first()
        
        if not subscription_record:
            raise HTTPException(
                status_code=403, 
                detail="Suscripción no pertenece a este gimnasio"
            )
        
        subscription_data, stripe_profile, user_gym = subscription_record
        
        if immediately:
            # 🆕 Cancelar inmediatamente usando cuenta del gym
            import stripe
            stripe.Subscription.delete(
                subscription_id,
                stripe_account=stripe_profile.stripe_account_id
            )
            success = True
        else:
            # 🆕 Cancelar al final del período usando cuenta del gym
            import stripe
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True,
                stripe_account=stripe_profile.stripe_account_id
            )
            success = True
        
        if success:
            # 🆕 Actualizar estado local
            subscription_data.status = "canceled" if immediately else "pending_cancel"
            subscription_data.canceled_at = datetime.now() if immediately else None
            await db.commit()
            
            logger.info(f"Suscripción {subscription_id} cancelada por admin {current_user.id}")
            
            return {
                "message": "Suscripción cancelada exitosamente",
                "subscription_id": subscription_id,
                "immediately": immediately,
                "user_id": user_gym.user_id,
                "local_status": subscription_data.status
            }
        else:
            raise HTTPException(status_code=400, detail="No se pudo cancelar la suscripción")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelando suscripción: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


# 🆕 ENDPOINTS PARA GESTIÓN DE INGRESOS POR GIMNASIO

@router.get("/revenue/gym-summary")
async def get_gym_revenue_summary(
    request: Request,
    start_date: Optional[str] = Query(None, description="Fecha de inicio (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha de fin (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_async_db),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    current_user: Auth0User = Depends(auth.get_user)
):
    """
    Obtener resumen de ingresos del gimnasio actual (solo administradores).
    
    Args:
        start_date: Fecha de inicio en formato YYYY-MM-DD (opcional)
        end_date: Fecha de fin en formato YYYY-MM-DD (opcional)
        
    Returns:
        dict: Resumen detallado de ingresos del gimnasio
    """
    try:
        from app.services.gym_revenue import gym_revenue_service
        from datetime import datetime
        
        # Convertir fechas de string a datetime si se proporcionan
        parsed_start_date = None
        parsed_end_date = None
        
        if start_date:
            parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Obtener resumen de ingresos
        revenue_summary = await gym_revenue_service.get_gym_revenue_summary(
            db, current_gym.id, parsed_start_date, parsed_end_date
        )
        
        logger.info(f"Resumen de ingresos solicitado por admin {current_user.id} para gym {current_gym.id}")
        
        return revenue_summary
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error obteniendo resumen de ingresos: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/revenue/platform-summary")
async def get_platform_revenue_summary(
    request: Request,
    start_date: Optional[str] = Query(None, description="Fecha de inicio (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha de fin (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(auth.get_user)
):
    """
    Obtener resumen de ingresos de toda la plataforma (solo super-administradores).
    
    Args:
        start_date: Fecha de inicio en formato YYYY-MM-DD (opcional)
        end_date: Fecha de fin en formato YYYY-MM-DD (opcional)
        
    Returns:
        dict: Resumen de ingresos de toda la plataforma
    """
    try:
        # Verificar que sea super-administrador
        if not current_user.permissions or "platform:admin" not in current_user.permissions:
            raise HTTPException(
                status_code=403, 
                detail="Acceso restringido a super-administradores"
            )
        
        from app.services.gym_revenue import gym_revenue_service
        from datetime import datetime
        
        # Convertir fechas de string a datetime si se proporcionan
        parsed_start_date = None
        parsed_end_date = None
        
        if start_date:
            parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Obtener resumen de la plataforma
        platform_summary = await gym_revenue_service.get_platform_revenue_summary(
            db, parsed_start_date, parsed_end_date
        )
        
        logger.info(f"Resumen de plataforma solicitado por super-admin {current_user.id}")
        
        return platform_summary
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error obteniendo resumen de plataforma: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/revenue/payout-calculation")
async def calculate_gym_payout(
    request: Request,
    start_date: str = Query(..., description="Fecha de inicio (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Fecha de fin (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_async_db),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    current_user: Auth0User = Depends(auth.get_user)
):
    """
    Calcular el pago que debe recibir el gimnasio (solo administradores).
    
    Args:
        start_date: Fecha de inicio en formato YYYY-MM-DD
        end_date: Fecha de fin en formato YYYY-MM-DD
        
    Returns:
        dict: Detalles del pago calculado
    """
    try:
        from app.services.gym_revenue import gym_revenue_service
        from datetime import datetime
        
        # Convertir fechas
        parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d")
        parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Validar que el rango de fechas sea razonable
        if (parsed_end_date - parsed_start_date).days > 365:
            raise HTTPException(
                status_code=400, 
                detail="El rango de fechas no puede ser mayor a 365 días"
            )
        
        if parsed_start_date > parsed_end_date:
            raise HTTPException(
                status_code=400, 
                detail="La fecha de inicio debe ser anterior a la fecha de fin"
            )
        
        # Calcular payout
        payout_details = await gym_revenue_service.calculate_gym_payout(
            db, current_gym.id, parsed_start_date, parsed_end_date
        )
        
        logger.info(f"Cálculo de payout solicitado por admin {current_user.id} para gym {current_gym.id}")
        
        return payout_details
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculando payout: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor") 