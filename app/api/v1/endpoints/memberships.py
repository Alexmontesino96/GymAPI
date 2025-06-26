"""
Endpoints para gestión de membresías y planes de membresía.

Este módulo proporciona todas las rutas relacionadas con la gestión de:
- Planes de membresía (creación, actualización, consulta)
- Estado de membresías de usuarios
- Compra de membresías (se integrará con Stripe en Fase 2)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, Path
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
from datetime import datetime

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
async def purchase_membership_with_trial(
    request: Request,
    purchase_data: PurchaseMembershipRequest,
    trial_days: int = Query(7, description="Días de prueba gratuita", ge=1, le=30),
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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
        # Verificar que el cliente pertenezca al gimnasio actual
        from app.models.user_gym import UserGym
        
        customer_membership = db.query(UserGym).filter(
            UserGym.stripe_customer_id == customer_id,
            UserGym.gym_id == current_gym.id
        ).first()
        
        if not customer_membership:
            raise HTTPException(
                status_code=403, 
                detail="Cliente no pertenece a este gimnasio"
            )
        
        payment_methods = await stripe_service.get_customer_payment_methods(customer_id)
        
        return {
            "customer_id": customer_id,
            "payment_methods": payment_methods,
            "user_id": customer_membership.user_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo métodos de pago: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/subscriptions/{subscription_id}/status")
async def get_subscription_status(
    subscription_id: str = Path(..., description="ID de la suscripción en Stripe"),
    db: Session = Depends(get_db),
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
        # Verificar que la suscripción pertenezca al gimnasio actual
        from app.models.user_gym import UserGym
        
        subscription_membership = db.query(UserGym).filter(
            UserGym.stripe_subscription_id == subscription_id,
            UserGym.gym_id == current_gym.id
        ).first()
        
        if not subscription_membership:
            raise HTTPException(
                status_code=403, 
                detail="Suscripción no pertenece a este gimnasio"
            )
        
        import stripe
        
        subscription = stripe.Subscription.retrieve(subscription_id)
        
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
            "user_id": subscription_membership.user_id
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
    db: Session = Depends(get_db),
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
        # Verificar que la suscripción pertenezca al gimnasio actual
        from app.models.user_gym import UserGym
        
        subscription_membership = db.query(UserGym).filter(
            UserGym.stripe_subscription_id == subscription_id,
            UserGym.gym_id == current_gym.id
        ).first()
        
        if not subscription_membership:
            raise HTTPException(
                status_code=403, 
                detail="Suscripción no pertenece a este gimnasio"
            )
        
        if immediately:
            success = await stripe_service.cancel_subscription(subscription_id)
        else:
            # Cancelar al final del período
            import stripe
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            success = True
        
        if success:
            logger.info(f"Suscripción {subscription_id} cancelada por admin {current_user.id}")
            
            return {
                "message": "Suscripción cancelada exitosamente",
                "subscription_id": subscription_id,
                "immediately": immediately,
                "user_id": subscription_membership.user_id
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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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