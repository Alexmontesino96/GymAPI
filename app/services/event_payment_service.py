"""
Servicio para manejar pagos de eventos.

Este servicio gestiona:
- Creación de Payment Intents para eventos de pago
- Procesamiento de pagos exitosos
- Cálculo y procesamiento de reembolsos según políticas
- Créditos en lugar de reembolsos
- Validación de que Stripe esté habilitado
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from decimal import Decimal
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.event import Event, EventParticipation, RefundPolicyType, PaymentStatusType
from app.models.stripe_profile import GymStripeAccount, UserGymStripeProfile
from app.models.user import User
from app.models.gym import Gym
from app.core.config import get_settings
from app.services.module import module_service
from app.services.stripe_service import stripe_service

import stripe

logger = logging.getLogger(__name__)
settings = get_settings()


class EventPaymentService:
    """Servicio para gestionar pagos de eventos."""

    def __init__(self):
        """Inicializar el servicio con la configuración de Stripe."""
        # Configurar Stripe API key de forma lazy
        try:
            config = get_settings()
            # La configuración usa STRIPE_SECRET_KEY, no STRIPE_API_KEY
            if hasattr(config, 'STRIPE_SECRET_KEY') and config.STRIPE_SECRET_KEY:
                stripe.api_key = config.STRIPE_SECRET_KEY
            else:
                logger.warning("STRIPE_SECRET_KEY no configurada")
        except Exception as e:
            logger.warning(f"No se pudo configurar Stripe: {e}")

    async def verify_stripe_enabled(self, db: Session, gym_id: int) -> bool:
        """
        Verificar que Stripe esté habilitado para el gimnasio.

        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio

        Returns:
            True si Stripe está habilitado y configurado
        """
        # Verificar módulo de billing activo
        billing_enabled = module_service.get_gym_module_status(db, gym_id, "billing")
        if not billing_enabled:
            logger.warning(f"Módulo billing no habilitado para gym {gym_id}")
            return False

        # Verificar cuenta de Stripe Connect
        stripe_account = db.query(GymStripeAccount).filter(
            GymStripeAccount.gym_id == gym_id
        ).first()

        if not stripe_account or not stripe_account.charges_enabled:
            logger.warning(f"Cuenta Stripe no configurada o no habilitada para gym {gym_id}")
            return False

        return True

    async def create_payment_intent_for_event(
        self,
        db: Session,
        event: Event,
        user: User,
        gym_id: int
    ) -> Dict[str, Any]:
        """
        Crear un Payment Intent para el pago de un evento.

        Args:
            db: Sesión de base de datos
            event: Evento a pagar
            user: Usuario que realiza el pago
            gym_id: ID del gimnasio

        Returns:
            Diccionario con client_secret y payment_intent_id
        """
        try:
            # Validar que Stripe esté habilitado
            if not await self.verify_stripe_enabled(db, gym_id):
                raise ValueError("Stripe no está habilitado para este gimnasio")

            # Verificar que el evento sea de pago
            if not event.is_paid or event.price_cents is None:
                raise ValueError("El evento no requiere pago")

            # Obtener cuenta de Stripe Connect del gym
            stripe_account = db.query(GymStripeAccount).filter(
                GymStripeAccount.gym_id == gym_id
            ).first()

            # Buscar o crear customer de Stripe para el usuario
            stripe_profile = await self._get_or_create_stripe_customer(
                db, user, gym_id, stripe_account.stripe_account_id
            )

            # Crear Payment Intent con Stripe Connect
            payment_intent = stripe.PaymentIntent.create(
                amount=event.price_cents,
                currency=event.currency.lower(),
                customer=stripe_profile.stripe_customer_id,
                metadata={
                    "event_id": str(event.id),
                    "user_id": str(user.id),
                    "gym_id": str(gym_id),
                    "event_title": event.title
                },
                description=f"Pago para evento: {event.title}",
                stripe_account=stripe_account.stripe_account_id,
                # Configuración para captura automática
                capture_method="automatic",
                # Permitir guardar método de pago para futuros pagos
                setup_future_usage="on_session"
            )

            logger.info(f"Payment Intent creado: {payment_intent.id} para evento {event.id}")

            return {
                "client_secret": payment_intent.client_secret,
                "payment_intent_id": payment_intent.id,
                "amount": event.price_cents,
                "currency": event.currency
            }

        except stripe.error.StripeError as e:
            logger.error(f"Error de Stripe creando Payment Intent: {e}")
            raise ValueError(f"Error procesando pago: {str(e)}")
        except Exception as e:
            logger.error(f"Error creando Payment Intent para evento {event.id}: {e}")
            raise

    async def _get_or_create_stripe_customer(
        self,
        db: Session,
        user: User,
        gym_id: int,
        stripe_account_id: str
    ) -> UserGymStripeProfile:
        """
        Obtener o crear un customer de Stripe para el usuario.

        Args:
            db: Sesión de base de datos
            user: Usuario
            gym_id: ID del gimnasio
            stripe_account_id: ID de la cuenta de Stripe Connect

        Returns:
            UserGymStripeProfile con el customer_id
        """
        # Buscar perfil existente
        stripe_profile = db.query(UserGymStripeProfile).filter(
            and_(
                UserGymStripeProfile.user_id == user.id,
                UserGymStripeProfile.gym_id == gym_id
            )
        ).first()

        if stripe_profile:
            return stripe_profile

        # Crear nuevo customer en Stripe
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip() or user.email,
                metadata={
                    "user_id": str(user.id),
                    "gym_id": str(gym_id)
                },
                stripe_account=stripe_account_id
            )

            # Guardar en BD
            stripe_profile = UserGymStripeProfile(
                user_id=user.id,
                gym_id=gym_id,
                stripe_customer_id=customer.id,
                stripe_account_id=stripe_account_id,
                email=user.email,
                customer_created_at=datetime.utcnow()
            )
            db.add(stripe_profile)
            db.commit()

            logger.info(f"Customer Stripe creado: {customer.id} para usuario {user.id}")
            return stripe_profile

        except stripe.error.StripeError as e:
            logger.error(f"Error creando customer en Stripe: {e}")
            raise ValueError(f"Error creando perfil de pago: {str(e)}")

    async def confirm_event_payment(
        self,
        db: Session,
        participation: EventParticipation,
        payment_intent_id: str
    ) -> EventParticipation:
        """
        Confirmar el pago exitoso de un evento.

        Args:
            db: Sesión de base de datos
            participation: Participación a actualizar
            payment_intent_id: ID del Payment Intent de Stripe

        Returns:
            Participación actualizada
        """
        try:
            # Obtener Payment Intent de Stripe
            event = db.query(Event).filter(Event.id == participation.event_id).first()
            stripe_account = db.query(GymStripeAccount).filter(
                GymStripeAccount.gym_id == event.gym_id
            ).first()

            payment_intent = stripe.PaymentIntent.retrieve(
                payment_intent_id,
                stripe_account=stripe_account.stripe_account_id
            )

            # Verificar que el pago fue exitoso
            if payment_intent.status != "succeeded":
                raise ValueError(f"Pago no completado. Estado: {payment_intent.status}")

            # Actualizar participación
            participation.payment_status = PaymentStatusType.PAID
            participation.stripe_payment_intent_id = payment_intent_id
            participation.amount_paid_cents = payment_intent.amount
            participation.payment_date = datetime.utcnow()

            db.commit()
            db.refresh(participation)

            logger.info(f"Pago confirmado para participación {participation.id}")
            return participation

        except stripe.error.StripeError as e:
            logger.error(f"Error verificando Payment Intent: {e}")
            raise ValueError(f"Error verificando pago: {str(e)}")
        except Exception as e:
            logger.error(f"Error confirmando pago: {e}")
            raise

    async def calculate_refund_amount(
        self,
        event: Event,
        amount_paid: int,
        cancellation_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calcular el monto de reembolso según la política del evento.

        Args:
            event: Evento con política de reembolso
            amount_paid: Monto pagado en centavos
            cancellation_time: Momento de cancelación (default: ahora)

        Returns:
            Diccionario con monto y tipo de reembolso
        """
        if not event.refund_policy:
            return {"amount": 0, "type": "NO_REFUND", "reason": "Sin política de reembolso"}

        if not cancellation_time:
            cancellation_time = datetime.utcnow()

        # Calcular horas hasta el evento
        hours_until_event = (event.start_time - cancellation_time).total_seconds() / 3600

        # Verificar si está dentro del plazo para reembolso
        if event.refund_deadline_hours and hours_until_event < event.refund_deadline_hours:
            return {
                "amount": 0,
                "type": "NO_REFUND",
                "reason": f"Fuera del plazo de reembolso ({event.refund_deadline_hours}h antes del evento)"
            }

        # Aplicar política de reembolso
        if event.refund_policy == RefundPolicyType.NO_REFUND:
            return {"amount": 0, "type": "NO_REFUND", "reason": "Política sin reembolso"}

        elif event.refund_policy == RefundPolicyType.FULL_REFUND:
            return {
                "amount": amount_paid,
                "type": "FULL_REFUND",
                "reason": "Reembolso completo según política"
            }

        elif event.refund_policy == RefundPolicyType.PARTIAL_REFUND:
            percentage = event.partial_refund_percentage or 50
            refund_amount = int(amount_paid * percentage / 100)
            return {
                "amount": refund_amount,
                "type": "PARTIAL_REFUND",
                "percentage": percentage,
                "reason": f"Reembolso parcial del {percentage}%"
            }

        elif event.refund_policy == RefundPolicyType.CREDIT:
            return {
                "amount": amount_paid,
                "type": "CREDIT",
                "reason": "Crédito para futuros eventos"
            }

        return {"amount": 0, "type": "NO_REFUND", "reason": "Política no reconocida"}

    async def process_event_refund(
        self,
        db: Session,
        participation: EventParticipation,
        event: Event,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Procesar el reembolso de una participación en evento.

        Args:
            db: Sesión de base de datos
            participation: Participación a reembolsar
            event: Evento asociado
            reason: Razón del reembolso

        Returns:
            Diccionario con detalles del reembolso
        """
        try:
            # Verificar que haya un pago previo
            if participation.payment_status != PaymentStatusType.PAID:
                raise ValueError("No hay pago registrado para esta participación")

            if not participation.stripe_payment_intent_id:
                raise ValueError("No hay información de pago de Stripe")

            # Calcular monto de reembolso
            refund_info = await self.calculate_refund_amount(
                event,
                participation.amount_paid_cents or 0
            )

            if refund_info["type"] == "NO_REFUND":
                logger.info(f"Sin reembolso para participación {participation.id}: {refund_info['reason']}")
                return refund_info

            # Si es crédito, procesarlo diferente
            if refund_info["type"] == "CREDIT":
                return await self._process_event_credit(
                    db,
                    participation,
                    refund_info["amount"]
                )

            # Procesar reembolso en Stripe
            stripe_account = db.query(GymStripeAccount).filter(
                GymStripeAccount.gym_id == event.gym_id
            ).first()

            refund = stripe.Refund.create(
                payment_intent=participation.stripe_payment_intent_id,
                amount=refund_info["amount"],
                reason="requested_by_customer",
                metadata={
                    "event_id": str(event.id),
                    "participation_id": str(participation.id),
                    "refund_reason": reason or refund_info["reason"]
                },
                stripe_account=stripe_account.stripe_account_id
            )

            # Actualizar participación
            participation.payment_status = PaymentStatusType.REFUNDED
            participation.refund_date = datetime.utcnow()
            participation.refund_amount_cents = refund_info["amount"]

            db.commit()

            logger.info(f"Reembolso procesado: {refund.id} por {refund_info['amount']} centavos")

            return {
                "refund_id": refund.id,
                "amount": refund_info["amount"],
                "type": refund_info["type"],
                "status": "PROCESSED",
                "reason": refund_info.get("reason")
            }

        except stripe.error.StripeError as e:
            logger.error(f"Error procesando reembolso en Stripe: {e}")
            raise ValueError(f"Error procesando reembolso: {str(e)}")
        except Exception as e:
            logger.error(f"Error procesando reembolso: {e}")
            raise

    async def _process_event_credit(
        self,
        db: Session,
        participation: EventParticipation,
        credit_amount: int
    ) -> Dict[str, Any]:
        """
        Procesar crédito en lugar de reembolso.

        Args:
            db: Sesión de base de datos
            participation: Participación
            credit_amount: Monto del crédito

        Returns:
            Información del crédito procesado
        """
        # TODO: Implementar sistema de créditos
        # Por ahora, solo marcamos como CREDITED
        participation.payment_status = PaymentStatusType.CREDITED
        participation.refund_date = datetime.utcnow()
        participation.refund_amount_cents = credit_amount

        db.commit()

        logger.info(f"Crédito otorgado para participación {participation.id}: {credit_amount} centavos")

        return {
            "amount": credit_amount,
            "type": "CREDIT",
            "status": "PROCESSED",
            "reason": "Crédito para futuros eventos"
        }

    async def handle_waitlist_payment_opportunity(
        self,
        db: Session,
        participation: EventParticipation,
        event: Event
    ) -> Dict[str, Any]:
        """
        Manejar oportunidad de pago para alguien en lista de espera.

        Args:
            db: Sesión de base de datos
            participation: Participación en lista de espera
            event: Evento

        Returns:
            Información del Payment Intent con fecha límite
        """
        try:
            # Establecer fecha límite de pago (24 horas)
            payment_expiry = datetime.utcnow() + timedelta(hours=24)
            participation.payment_expiry = payment_expiry

            # Obtener usuario
            user = db.query(User).filter(User.id == participation.member_id).first()

            # Crear Payment Intent
            payment_info = await self.create_payment_intent_for_event(
                db, event, user, event.gym_id
            )

            # Actualizar participación con el payment intent
            participation.stripe_payment_intent_id = payment_info["payment_intent_id"]
            db.commit()

            # Agregar fecha límite a la respuesta
            payment_info["payment_deadline"] = payment_expiry

            logger.info(
                f"Oportunidad de pago creada para participación {participation.id} "
                f"con límite {payment_expiry}"
            )

            return payment_info

        except Exception as e:
            logger.error(f"Error creando oportunidad de pago: {e}")
            raise

    async def expire_pending_payments(self, db: Session) -> List[int]:
        """
        Expirar pagos pendientes que han pasado su fecha límite.
        Esto se ejecutaría como un job programado.

        Args:
            db: Sesión de base de datos

        Returns:
            Lista de IDs de participaciones expiradas
        """
        try:
            now = datetime.utcnow()

            # Buscar participaciones con pago pendiente y fecha expirada
            expired_participations = db.query(EventParticipation).filter(
                and_(
                    EventParticipation.payment_status == PaymentStatusType.PENDING,
                    EventParticipation.payment_expiry is not None,
                    EventParticipation.payment_expiry < now
                )
            ).all()

            expired_ids = []
            for participation in expired_participations:
                # Cancelar Payment Intent en Stripe si existe
                if participation.stripe_payment_intent_id:
                    try:
                        stripe.PaymentIntent.cancel(participation.stripe_payment_intent_id)
                    except stripe.error.StripeError as e:
                        logger.warning(f"Error cancelando Payment Intent {participation.stripe_payment_intent_id}: {e}")

                # Marcar como expirado
                participation.payment_status = PaymentStatusType.EXPIRED
                expired_ids.append(participation.id)

            db.commit()

            logger.info(f"Expirados {len(expired_ids)} pagos pendientes")
            return expired_ids

        except Exception as e:
            logger.error(f"Error expirando pagos pendientes: {e}")
            raise


# Instancia global del servicio
event_payment_service = EventPaymentService()