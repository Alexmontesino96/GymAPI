"""
Endpoints para gestión de Stripe Connect.

Este módulo proporciona endpoints para:
- Crear cuentas de Stripe Connect para gimnasios
- Generar links de onboarding
- Verificar estado de las cuentas
- Gestionar configuración de Stripe Connect
"""

from typing import Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth0_fastapi import Auth0User, auth
from app.core.tenant import verify_gym_admin_access
from app.schemas.gym import GymSchema
from app.services.stripe_connect_service import stripe_connect_service
from app.middleware.rate_limit import limiter
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/accounts", status_code=status.HTTP_201_CREATED)
async def create_stripe_account(
    request: Request,
    country: str = "US",
    account_type: str = "standard",
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
) -> Dict[str, Any]:
    """
    [ADMIN ONLY] Crear cuenta de Stripe Connect para el gimnasio.

    Este endpoint crea una nueva cuenta de Stripe Connect para el gimnasio actual.
    Solo los administradores pueden crear cuentas de Stripe.

    NOTA: Por defecto se crean cuentas Standard para dar control total al gym.
    Las cuentas Standard permiten:
    - Dashboard propio de Stripe (acceso directo a stripe.com)
    - Independencia de la plataforma
    - Capacidad de desconectarse si lo desean
    - Control total sobre su cuenta de Stripe
    
    Args:
        country: Código de país ISO (ej: "US", "ES", "MX")
        account_type: Tipo de cuenta ("express", "standard", "custom")
        db: Sesión de base de datos
        current_user: Usuario autenticado (Admin)
        current_gym: Gimnasio verificado
        
    Returns:
        dict: Información de la cuenta creada
        
    Raises:
        HTTPException: 400 si ya existe cuenta, 500 si error de Stripe
    """
    try:
        # Verificar si ya existe cuenta
        existing_account = stripe_connect_service.get_gym_stripe_account(db, current_gym.id)
        if existing_account and not existing_account.stripe_account_id.startswith("placeholder_"):
            return {
                "message": "El gimnasio ya tiene una cuenta de Stripe configurada",
                "account_id": existing_account.stripe_account_id,
                "account_type": existing_account.account_type,
                "country": existing_account.country,
                "onboarding_completed": existing_account.onboarding_completed,
                "charges_enabled": existing_account.charges_enabled,
                "payouts_enabled": existing_account.payouts_enabled,
                "status": "already_exists"
            }
        
        # Crear o actualizar cuenta de Stripe Connect
        gym_account = await stripe_connect_service.create_gym_stripe_account(
            db, current_gym.id, country, account_type
        )
        
        logger.info(f"Cuenta de Stripe {'actualizada' if existing_account else 'creada'} para gym {current_gym.id} por admin {current_user.id}")
        
        return {
            "message": f"Cuenta de Stripe {'actualizada' if existing_account else 'creada'} exitosamente",
            "account_id": gym_account.stripe_account_id,
            "account_type": gym_account.account_type,
            "country": gym_account.country,
            "onboarding_completed": gym_account.onboarding_completed,
            "charges_enabled": gym_account.charges_enabled,
            "payouts_enabled": gym_account.payouts_enabled,
            "status": "updated" if existing_account else "created"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error inesperado al crear cuenta de Stripe: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/accounts/status")
async def get_stripe_account_status(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
) -> Dict[str, Any]:
    """
    [ADMIN ONLY] Obtener estado de la cuenta de Stripe Connect.
    
    Args:
        db: Sesión de base de datos
        current_user: Usuario autenticado (Admin)
        current_gym: Gimnasio verificado
        
    Returns:
        dict: Estado completo de la cuenta
        
    Raises:
        HTTPException: 404 si no existe cuenta
    """
    try:
        # Obtener cuenta existente
        gym_account = stripe_connect_service.get_gym_stripe_account(db, current_gym.id)
        if not gym_account:
            raise HTTPException(
                status_code=404,
                detail="El gimnasio no tiene cuenta de Stripe configurada"
            )
        
        # Actualizar estado desde Stripe
        updated_account = await stripe_connect_service.update_gym_account_status(db, current_gym.id)
        
        return {
            "account_id": updated_account.stripe_account_id,
            "account_type": updated_account.account_type,
            "country": updated_account.country,
            "currency": updated_account.default_currency,
            "onboarding_completed": updated_account.onboarding_completed,
            "charges_enabled": updated_account.charges_enabled,
            "payouts_enabled": updated_account.payouts_enabled,
            "details_submitted": updated_account.details_submitted,
            "is_active": updated_account.is_active,
            "created_at": updated_account.created_at,
            "updated_at": updated_account.updated_at
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error obteniendo estado de cuenta: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/accounts/onboarding-link")
@limiter.limit("5 per minute")
async def create_onboarding_link(
    request: Request,
    refresh_url: str = None,
    return_url: str = None,
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
) -> Dict[str, Any]:
    """
    [ADMIN ONLY] Crear link de onboarding para configurar Stripe.
    
    Este endpoint genera un link seguro para que el gimnasio complete
    la configuración de su cuenta de Stripe Connect.
    
    Args:
        refresh_url: URL de refresh personalizada (opcional)
        return_url: URL de retorno personalizada (opcional)
        db: Sesión de base de datos
        current_user: Usuario autenticado (Admin)
        current_gym: Gimnasio verificado
        
    Returns:
        dict: URL de onboarding y información adicional
        
    Raises:
        HTTPException: 404 si no existe cuenta, 400 si ya completó onboarding
    """
    try:
        # Verificar que existe cuenta
        gym_account = stripe_connect_service.get_gym_stripe_account(db, current_gym.id)
        if not gym_account:
            raise HTTPException(
                status_code=404,
                detail="Debe crear una cuenta de Stripe primero"
            )
        
        # Verificar si ya completó onboarding
        if gym_account.onboarding_completed:
            raise HTTPException(
                status_code=400,
                detail="El gimnasio ya completó la configuración de Stripe"
            )
        
        # Crear link de onboarding
        onboarding_url = await stripe_connect_service.create_onboarding_link(
            db, current_gym.id, refresh_url, return_url
        )
        
        logger.info(f"Link de onboarding creado para gym {current_gym.id} por admin {current_user.id}")
        
        return {
            "message": "Link de onboarding creado exitosamente",
            "onboarding_url": onboarding_url,
            "expires_in_minutes": 60,
            "instructions": "Complete la configuración de Stripe siguiendo el link. El proceso toma 5-10 minutos."
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creando link de onboarding: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/accounts/connection-status")
async def get_connection_status(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
) -> Dict[str, Any]:
    """
    [ADMIN ONLY] Verificar estado de conexión de la cuenta de Stripe.

    Útil especialmente para Standard accounts que pueden desconectarse de la plataforma.
    Este endpoint verifica tanto el estado en BD como en Stripe directamente.

    Returns:
        dict: Estado detallado de la conexión incluyendo:
            - connected: bool - Si la cuenta está conectada y activa
            - account_id: str - ID de la cuenta en Stripe
            - account_type: str - Tipo de cuenta (express, standard, custom)
            - can_disconnect: bool - Si puede desconectarse (True para Standard)
            - direct_dashboard_access: bool - Si tiene acceso directo al dashboard
            - charges_enabled: bool - Si puede procesar pagos
            - payouts_enabled: bool - Si puede recibir transferencias
            - message: str - Mensaje descriptivo del estado
            - action_required: str (opcional) - Acción requerida si hay problema

    Examples:
        >>> # Cuenta conectada y funcionando
        {
            "connected": true,
            "account_id": "acct_xxx",
            "account_type": "standard",
            "can_disconnect": true,
            "direct_dashboard_access": true,
            "charges_enabled": true,
            "payouts_enabled": true,
            "message": "Cuenta conectada y funcionando"
        }

        >>> # Cuenta desconectada
        {
            "connected": false,
            "account_id": "acct_xxx",
            "account_type": "standard",
            "message": "Cuenta desconectada o inactiva",
            "action_required": "Reconectar cuenta o crear nueva"
        }
    """
    try:
        gym_account = stripe_connect_service.get_gym_stripe_account(db, current_gym.id)

        if not gym_account:
            return {
                "connected": False,
                "message": "No hay cuenta de Stripe configurada",
                "action_required": "Crear cuenta de Stripe Connect"
            }

        if not gym_account.is_active:
            return {
                "connected": False,
                "account_id": gym_account.stripe_account_id,
                "account_type": gym_account.account_type,
                "message": "Cuenta desconectada o inactiva",
                "action_required": "Reconectar cuenta o crear nueva"
            }

        # Verificar en Stripe si la cuenta sigue existiendo y accesible
        try:
            import stripe
            account = stripe.Account.retrieve(gym_account.stripe_account_id)

            return {
                "connected": True,
                "account_id": gym_account.stripe_account_id,
                "account_type": gym_account.account_type,
                "charges_enabled": gym_account.charges_enabled,
                "payouts_enabled": gym_account.payouts_enabled,
                "can_disconnect": gym_account.account_type == "standard",
                "direct_dashboard_access": gym_account.account_type == "standard",
                "message": "Cuenta conectada y funcionando",
                "onboarding_completed": gym_account.onboarding_completed,
                "details_submitted": gym_account.details_submitted
            }

        except stripe.error.PermissionError:
            # La cuenta fue desautorizada pero el webhook no se procesó
            # Auto-reparación: marcar como inactiva
            gym_account.is_active = False
            gym_account.charges_enabled = False
            gym_account.payouts_enabled = False
            db.commit()

            logger.warning(
                f"Cuenta {gym_account.stripe_account_id} desautorizada detectada en verificación. "
                f"Marcada como inactiva (gym {current_gym.id})"
            )

            return {
                "connected": False,
                "account_id": gym_account.stripe_account_id,
                "account_type": gym_account.account_type,
                "message": "Cuenta desconectada (sin acceso a Stripe)",
                "action_required": "Reconectar cuenta o crear nueva"
            }

    except Exception as e:
        logger.error(f"Error verificando conexión de Stripe: {str(e)}")
        raise HTTPException(status_code=500, detail="Error verificando estado de conexión")


@router.post("/accounts/dashboard-link")
@limiter.limit("10 per minute")
async def create_dashboard_link(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
) -> Dict[str, Any]:
    """
    [ADMIN ONLY] Crear link de acceso al dashboard de Stripe.

    Comportamiento según tipo de cuenta:

    **Standard Accounts**:
    - Tienen acceso directo a https://dashboard.stripe.com con sus credenciales
    - Este endpoint es opcional (retorna URL directa)
    - No requiere login link temporal

    **Express Accounts**:
    - Requieren login link temporal (válido 60 minutos)
    - No tienen acceso directo al dashboard
    - Este endpoint es necesario para acceder

    Requisitos:
    - El gym debe tener una cuenta de Stripe creada
    - La configuración inicial (onboarding) debe estar completada

    Args:
        request: Request object (para rate limiting)
        db: Sesión de base de datos
        current_user: Usuario autenticado (Admin)
        current_gym: Gimnasio verificado

    Returns:
        dict: URL del dashboard y metadata según tipo de cuenta

    Raises:
        HTTPException: 404 si no existe cuenta, 400 si no completó onboarding

    Examples:
        Standard Account:
        {
            "message": "Acceso directo al dashboard disponible",
            "dashboard_url": "https://dashboard.stripe.com",
            "direct_access": true,
            "account_type": "standard",
            "note": "Con Standard accounts puede acceder directamente a stripe.com",
            "instructions": "Acceda a https://dashboard.stripe.com con sus credenciales de Stripe"
        }

        Express Account:
        {
            "message": "Link de acceso al dashboard creado exitosamente",
            "dashboard_url": "https://connect.stripe.com/express/...",
            "direct_access": false,
            "account_type": "express",
            "expires_in_minutes": 60,
            "instructions": "El link es válido por 60 minutos"
        }
    """
    try:
        # Verificar que existe cuenta y obtener info
        gym_account = stripe_connect_service.get_gym_stripe_account(db, current_gym.id)
        if not gym_account:
            raise HTTPException(
                status_code=404,
                detail="El gimnasio no tiene cuenta de Stripe configurada. Cree una cuenta primero usando /accounts"
            )

        if not gym_account.is_active:
            raise HTTPException(
                status_code=400,
                detail="La cuenta de Stripe está desconectada. Use /accounts/connection-status para más información."
            )

        # Verificar si completó onboarding
        if not gym_account.onboarding_completed:
            raise HTTPException(
                status_code=400,
                detail="Debe completar la configuración inicial de Stripe antes de acceder al dashboard. Use /accounts/onboarding-link para completar la configuración."
            )

        # Standard accounts: Acceso directo al dashboard
        if gym_account.account_type == "standard":
            logger.info(
                f"Info de dashboard solicitada para Standard account (gym {current_gym.id}) "
                f"por admin {current_user.id} - acceso directo disponible"
            )

            return {
                "message": "Acceso directo al dashboard disponible (Standard Account)",
                "dashboard_url": "https://dashboard.stripe.com",
                "direct_access": True,
                "account_type": "standard",
                "account_id": gym_account.stripe_account_id,
                "created_at": datetime.now().isoformat(),
                "note": (
                    "Con Standard accounts tiene acceso directo a Stripe sin necesidad de "
                    "login links temporales. Puede acceder en cualquier momento con sus credenciales."
                ),
                "instructions": (
                    "1. Vaya a https://dashboard.stripe.com\n"
                    "2. Inicie sesión con sus credenciales de Stripe\n"
                    "3. Tendrá acceso completo a pagos, reportes, configuración y más"
                )
            }

        # Express/Custom accounts: Login link temporal
        dashboard_url = await stripe_connect_service.create_dashboard_login_link(
            db, current_gym.id
        )

        logger.info(
            f"Dashboard link creado para {gym_account.account_type} account "
            f"(gym {current_gym.id}) por admin {current_user.id}"
        )

        return {
            "message": "Link de acceso al dashboard creado exitosamente",
            "dashboard_url": dashboard_url,
            "direct_access": False,
            "account_type": gym_account.account_type,
            "created_at": datetime.now().isoformat(),
            "expires_in_minutes": 60,
            "account_id": gym_account.stripe_account_id,
            "instructions": "El link es válido por 60 minutos. Puede acceder a pagos, reportes, configuración y más."
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando dashboard link: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/customers/{user_id}")
async def get_user_stripe_info(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
) -> Dict[str, Any]:
    """
    [ADMIN ONLY] Obtener información de Stripe de un usuario específico.
    
    Args:
        user_id: ID del usuario
        db: Sesión de base de datos
        current_user: Usuario autenticado (Admin)
        current_gym: Gimnasio verificado
        
    Returns:
        dict: Información del customer y suscripciones
        
    Raises:
        HTTPException: 404 si no existe perfil de Stripe
    """
    try:
        # Obtener perfil de Stripe del usuario
        stripe_profile = stripe_connect_service.get_user_stripe_profile(db, user_id, current_gym.id)
        if not stripe_profile:
            raise HTTPException(
                status_code=404,
                detail=f"Usuario {user_id} no tiene perfil de Stripe en este gimnasio"
            )
        
        # Obtener subscription_id si existe
        subscription_id = await stripe_connect_service.get_subscription_for_user_gym(
            db, user_id, current_gym.id
        )
        
        return {
            "user_id": user_id,
            "gym_id": current_gym.id,
            "stripe_customer_id": stripe_profile.stripe_customer_id,
            "stripe_account_id": stripe_profile.stripe_account_id,
            "stripe_subscription_id": subscription_id,
            "email": stripe_profile.email,
            "is_active": stripe_profile.is_active,
            "created_at": stripe_profile.created_at,
            "last_sync_at": stripe_profile.last_sync_at
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo info de Stripe para user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/dashboard")
async def get_stripe_dashboard(
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(auth.get_user),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
) -> Dict[str, Any]:
    """
    [ADMIN ONLY] Obtener resumen del dashboard de Stripe.
    
    Args:
        db: Sesión de base de datos
        current_user: Usuario autenticado (Admin)
        current_gym: Gimnasio verificado
        
    Returns:
        dict: Resumen de configuración y estadísticas
    """
    try:
        from app.models.stripe_profile import UserGymStripeProfile
        
        # Obtener cuenta del gym
        gym_account = stripe_connect_service.get_gym_stripe_account(db, current_gym.id)
        
        # Estadísticas de customers
        total_customers = db.query(UserGymStripeProfile).filter(
            UserGymStripeProfile.gym_id == current_gym.id,
            UserGymStripeProfile.is_active == True
        ).count()
        
        active_subscriptions = db.query(UserGymStripeProfile).filter(
            UserGymStripeProfile.gym_id == current_gym.id,
            UserGymStripeProfile.is_active == True,
            UserGymStripeProfile.stripe_subscription_id.isnot(None)
        ).count()
        
        return {
            "stripe_configured": gym_account is not None,
            "onboarding_completed": gym_account.onboarding_completed if gym_account else False,
            "charges_enabled": gym_account.charges_enabled if gym_account else False,
            "payouts_enabled": gym_account.payouts_enabled if gym_account else False,
            "account_id": gym_account.stripe_account_id if gym_account else None,
            "total_customers": total_customers,
            "active_subscriptions": active_subscriptions,
            "needs_onboarding": gym_account and not gym_account.onboarding_completed,
            "ready_for_payments": gym_account and gym_account.onboarding_completed and gym_account.charges_enabled
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo dashboard de Stripe: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor") 