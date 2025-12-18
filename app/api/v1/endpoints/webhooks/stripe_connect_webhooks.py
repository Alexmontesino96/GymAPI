"""
Webhook handler para eventos de Stripe Connect.

Este módulo maneja eventos relacionados con cuentas de Stripe Connect,
especialmente crítico para Standard accounts que pueden desconectarse.

Eventos manejados:
- account.application.deauthorized: Cuando un gimnasio desconecta su cuenta
- account.updated: Cuando se actualiza información de la cuenta
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.session import get_db
from app.services.stripe_connect_service import stripe_connect_service
from app.core.config import get_settings
from app.middleware.rate_limit import limiter
from app.models.stripe_profile import GymStripeAccount
import stripe
import logging

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()


@router.post("/connect")
@limiter.limit("100 per minute")
async def stripe_connect_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook para manejar eventos de Stripe Connect.

    CRÍTICO para Standard accounts que pueden desconectarse de la plataforma.

    Eventos manejados:
    - account.application.deauthorized: Cuando un gym desconecta su cuenta
    - account.updated: Sincronizar cambios en la cuenta

    Returns:
        dict: Confirmación de recepción del evento
    """
    try:
        payload = await request.body()
        signature = request.headers.get('stripe-signature')

        if not signature:
            logger.error("Webhook de Stripe Connect sin firma")
            raise HTTPException(status_code=400, detail="Missing stripe-signature header")

        # Verificar firma con webhook secret de Connect
        # IMPORTANTE: Stripe Connect requiere un webhook endpoint separado
        connect_webhook_secret = settings.STRIPE_CONNECT_WEBHOOK_SECRET
        if not connect_webhook_secret:
            logger.error("STRIPE_CONNECT_WEBHOOK_SECRET no configurado - webhooks de Connect deshabilitados")
            raise HTTPException(
                status_code=500,
                detail="Webhook not configured. Set STRIPE_CONNECT_WEBHOOK_SECRET in environment variables."
            )

        # Construir evento verificando la firma
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, connect_webhook_secret
            )
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Firma de webhook inválida: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid signature")

        event_type = event['type']
        logger.info(f"📥 Evento de Stripe Connect recibido: {event_type}")

        # Despachar según tipo de evento
        if event_type == 'account.application.deauthorized':
            await _handle_account_deauthorized(db, event)

        elif event_type == 'account.updated':
            await _handle_account_updated(db, event)

        else:
            logger.warning(f"⚠️  Evento de Connect no manejado: {event_type}")

        return {"received": True, "event_type": event_type}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error procesando webhook de Connect: {str(e)}", exc_info=True)
        # Retornar 200 para evitar que Stripe reintente
        return {"received": True, "status": "error", "message": str(e)}


async def _handle_account_deauthorized(db: Session, event: dict):
    """
    Manejar desautorización de cuenta Standard.

    Cuando un gimnasio desconecta su cuenta de Stripe (solo posible con Standard):
    1. Marcar cuenta como inactiva en BD
    2. Desactivar procesamiento de pagos
    3. Registrar evento en logs
    4. (TODO) Notificar a administradores del gym

    Args:
        db: Sesión de base de datos
        event: Evento de Stripe
    """
    try:
        account_id = event['account']
        logger.warning(f"⚠️  Cuenta de Stripe desautorizada: {account_id}")

        # Buscar gym_account por stripe_account_id
        gym_account = db.query(GymStripeAccount).filter(
            GymStripeAccount.stripe_account_id == account_id,
            GymStripeAccount.is_active == True
        ).first()

        if not gym_account:
            logger.error(f"❌ No se encontró GymStripeAccount activa para account_id={account_id}")
            logger.info("ℹ️  Posiblemente la cuenta ya fue desactivada previamente")
            return

        # Marcar como inactiva
        gym_account.is_active = False
        gym_account.charges_enabled = False
        gym_account.payouts_enabled = False
        gym_account.updated_at = datetime.utcnow()

        db.commit()

        logger.warning(
            f"🚨 CUENTA DESCONECTADA - Gimnasio {gym_account.gym_id} desconectó su cuenta de Stripe. "
            f"Account ID: {account_id}. Pagos deshabilitados automáticamente."
        )

        # TODO: Implementar notificación a administradores del gym
        # from app.services.notification_service import notification_service
        # await notification_service.notify_gym_admins(
        #     gym_id=gym_account.gym_id,
        #     title="⚠️ Cuenta de Stripe Desconectada",
        #     message=(
        #         "Tu cuenta de Stripe ha sido desconectada de la plataforma. "
        #         "Los pagos están deshabilitados. Contacta a soporte para reconectar."
        #     ),
        #     priority="high"
        # )

    except Exception as e:
        logger.error(f"❌ Error manejando desautorización de cuenta: {str(e)}", exc_info=True)
        db.rollback()
        raise


async def _handle_account_updated(db: Session, event: dict):
    """
    Manejar actualización de cuenta Connect.

    Sincroniza cambios en la cuenta de Stripe con la BD local.
    Útil para detectar cambios en capabilities (charges_enabled, payouts_enabled).

    Args:
        db: Sesión de base de datos
        event: Evento de Stripe
    """
    try:
        account_id = event['account']
        account_data = event['data']['object']

        # Buscar cuenta en BD
        gym_account = db.query(GymStripeAccount).filter(
            GymStripeAccount.stripe_account_id == account_id,
            GymStripeAccount.is_active == True
        ).first()

        if not gym_account:
            logger.warning(
                f"ℹ️  Cuenta actualizada pero no encontrada en BD (o inactiva): {account_id}"
            )
            return

        # Actualizar estado desde Stripe
        old_charges = gym_account.charges_enabled
        old_payouts = gym_account.payouts_enabled

        gym_account.charges_enabled = account_data.get('charges_enabled', False)
        gym_account.payouts_enabled = account_data.get('payouts_enabled', False)
        gym_account.details_submitted = account_data.get('details_submitted', False)
        gym_account.updated_at = datetime.utcnow()

        # Detectar cambios importantes
        changes = []
        if old_charges != gym_account.charges_enabled:
            changes.append(f"charges_enabled: {old_charges} → {gym_account.charges_enabled}")
        if old_payouts != gym_account.payouts_enabled:
            changes.append(f"payouts_enabled: {old_payouts} → {gym_account.payouts_enabled}")

        db.commit()

        if changes:
            logger.info(
                f"✅ Cuenta actualizada: {account_id} (gym {gym_account.gym_id}) - "
                f"Cambios: {', '.join(changes)}"
            )
        else:
            logger.debug(f"ℹ️  Cuenta actualizada sin cambios relevantes: {account_id}")

    except Exception as e:
        logger.error(f"❌ Error manejando actualización de cuenta: {str(e)}", exc_info=True)
        db.rollback()
        raise
