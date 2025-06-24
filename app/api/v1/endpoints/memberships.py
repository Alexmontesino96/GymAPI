"""
Endpoints para gestión de membresías y planes de membresía.

Este módulo proporciona todas las rutas relacionadas con la gestión de:
- Planes de membresía (creación, actualización, consulta)
- Estado de membresías de usuarios
- Compra de membresías (se integrará con Stripe en Fase 2)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth0_fastapi import Auth0User, auth
from app.core.tenant import verify_gym_access, verify_gym_admin_access, get_current_gym
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
    PurchaseMembershipResponse
)
from app.services.membership import membership_service
from app.services.stripe_service import StripeService
from app.services.user import user_service
from app.db.redis_client import get_redis_client
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Instanciar servicio de Stripe
stripe_service = StripeService(membership_service)


# === Endpoints de Planes de Membresía (Admin) ===

@router.post("/plans", response_model=MembershipPlan, status_code=status.HTTP_201_CREATED)
async def create_membership_plan(
    request: Request,
    plan_data: MembershipPlanCreate,
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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


@router.put("/plans/{plan_id}", response_model=MembershipPlan)
async def update_membership_plan(
    request: Request,
    plan_id: int,
    plan_update: MembershipPlanUpdate,
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
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
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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
async def purchase_membership(
    request: Request,
    purchase_data: PurchaseMembershipRequest,
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_access)
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
        # Verificar que el plan pertenece al gimnasio actual
        plan = membership_service.get_membership_plan(db, purchase_data.plan_id)
        if not plan or plan.gym_id != current_gym.id:
            raise HTTPException(
                status_code=404,
                detail="Plan de membresía no encontrado en este gimnasio"
            )
        
        if not plan.is_active:
            raise HTTPException(
                status_code=400,
                detail="Este plan de membresía no está disponible"
            )

        # Obtener usuario local para usar su ID numérico
        redis_client = get_redis_client()
        local_user = await user_service.get_user_by_auth0_id_cached(
            db, current_user.id, redis_client
        )
        
        if not local_user:
            raise HTTPException(
                status_code=404,
                detail="Usuario no encontrado en el sistema local"
            )

        # Crear sesión de checkout con Stripe
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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error inesperado en compra: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/purchase/success")
async def handle_purchase_success(
    request: Request,
    session_id: str = Query(..., description="ID de sesión de Stripe"),
    db: Session = Depends(get_db)
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
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error inesperado en webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor") 