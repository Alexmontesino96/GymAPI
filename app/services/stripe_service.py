import stripe
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models.membership import MembershipPlan
from app.models.user_gym import UserGym
from app.schemas.membership import PurchaseMembershipResponse
from app.services.membership import MembershipService
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Configurar Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Validación de configuración de Stripe (sin exponer claves)
if not settings.STRIPE_SECRET_KEY:
    logger.error("❌ STRIPE_SECRET_KEY no está configurada")
elif "your_sec" in str(settings.STRIPE_SECRET_KEY).lower() or "placeholder" in str(settings.STRIPE_SECRET_KEY).lower():
    logger.error("❌ STRIPE_SECRET_KEY parece ser un placeholder - verificar configuración")
else:
    logger.info("✅ STRIPE_SECRET_KEY configurada correctamente")

class StripeService:
    def __init__(self, membership_service: MembershipService):
        self.membership_service = membership_service

    async def create_checkout_session(
        self,
        db: Session,
        user_id: str,
        gym_id: int,
        plan_id: int,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Crear una sesión de checkout de Stripe"""
        try:
            # Obtener el plan de membresía con información del gimnasio
            from app.models.gym import Gym
            
            plan = db.query(MembershipPlan).filter(
                MembershipPlan.id == plan_id,
                MembershipPlan.gym_id == gym_id,
                MembershipPlan.is_active == True
            ).first()
            
            if not plan:
                raise ValueError("Plan de membresía no encontrado")

            # Verificar si el plan tiene precio en Stripe
            if not plan.stripe_price_id:
                raise ValueError("El plan no tiene configurado un precio en Stripe")
            
            # Obtener información del gimnasio para metadatos
            gym = db.query(Gym).filter(Gym.id == gym_id).first()
            if not gym:
                raise ValueError("Gimnasio no encontrado")

            # URLs de éxito y cancelación
            success_url = success_url or settings.STRIPE_SUCCESS_URL
            cancel_url = cancel_url or settings.STRIPE_CANCEL_URL

            # Crear la sesión de checkout
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': plan.stripe_price_id,
                    'quantity': 1,
                }],
                mode='subscription' if plan.billing_interval != 'one_time' else 'payment',
                success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=cancel_url,
                metadata={
                    'user_id': user_id,
                    'gym_id': str(gym_id),
                    'gym_name': gym.name,
                    'plan_id': str(plan_id),
                    'plan_name': plan.name,
                    'plan_price': str(plan.price_cents),
                    'currency': plan.currency,
                    'billing_interval': plan.billing_interval,
                    'platform': 'gymapi'
                },
                allow_promotion_codes=True,
            )

            logger.info(f"Sesión de checkout creada: {checkout_session.id} para usuario {user_id}")
            
            return {
                'checkout_session_id': checkout_session.id,
                'checkout_url': checkout_session.url,
                'plan_name': plan.name,
                'price': plan.price_cents / 100,  # Convertir a euros/dólares
                'currency': plan.currency
            }

        except stripe.error.StripeError as e:
            logger.error(f"Error de Stripe al crear checkout: {str(e)}")
            raise ValueError(f"Error al procesar el pago: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al crear checkout: {str(e)}")
            raise

    async def handle_successful_payment(
        self,
        db: Session,
        session_id: str
    ) -> PurchaseMembershipResponse:
        """Manejar un pago exitoso desde Stripe"""
        try:
            # Obtener la sesión de checkout
            session = stripe.checkout.Session.retrieve(session_id)
            
            if session.payment_status != 'paid':
                raise ValueError("El pago no fue completado")

            # Extraer metadatos
            metadata = session.metadata
            user_id = metadata.get('user_id')
            gym_id = int(metadata.get('gym_id'))
            plan_id = int(metadata.get('plan_id'))

            if not all([user_id, gym_id, plan_id]):
                raise ValueError("Metadatos incompletos en la sesión de Stripe")

            # Obtener información adicional si es suscripción
            stripe_customer_id = session.customer
            stripe_subscription_id = session.subscription if session.mode == 'subscription' else None

            # Activar la membresía usando el servicio existente
            membership = await self.membership_service.activate_membership(
                db=db,
                user_id=user_id,
                gym_id=gym_id,
                plan_id=plan_id,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id
            )

            logger.info(f"Membresía activada exitosamente para usuario {user_id} en gym {gym_id}")

            return PurchaseMembershipResponse(
                success=True,
                message="Membresía activada exitosamente",
                membership_expires_at=membership.membership_expires_at,
                stripe_session_id=session_id
            )

        except stripe.error.StripeError as e:
            logger.error(f"Error de Stripe al procesar pago exitoso: {str(e)}")
            raise ValueError(f"Error al verificar el pago: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al procesar pago exitoso: {str(e)}")
            raise

    async def handle_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """Manejar webhooks de Stripe"""
        if not settings.STRIPE_WEBHOOK_SECRET:
            logger.error("STRIPE_WEBHOOK_SECRET no configurado - webhook rechazado por seguridad")
            raise ValueError("Configuración de webhook secret faltante - contacte al administrador")

        try:
            # Verificar la firma del webhook
            event = stripe.Webhook.construct_event(
                payload, signature, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            logger.error(f"Payload inválido en webhook: {str(e)}")
            raise ValueError("Payload inválido")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Firma inválida en webhook: {str(e)}")
            raise ValueError("Firma inválida")

        # Manejar diferentes tipos de eventos
        event_type = event['type']
        logger.info(f"Procesando webhook de Stripe: {event_type}")

        if event_type == 'checkout.session.completed':
            # Pago completado
            session = event['data']['object']
            logger.info(f"Checkout completado: {session['id']}")
            
        elif event_type == 'invoice.payment_succeeded':
            # Pago de suscripción exitoso
            invoice = event['data']['object']
            logger.info(f"Pago de suscripción exitoso: {invoice['id']}")
            # TODO: Extender fecha de membresía
            
        elif event_type == 'invoice.payment_failed':
            # Pago de suscripción fallido
            invoice = event['data']['object']
            logger.warning(f"Pago de suscripción fallido: {invoice['id']}")
            # TODO: Notificar al usuario y suspender acceso
            
        elif event_type == 'customer.subscription.deleted':
            # Suscripción cancelada
            subscription = event['data']['object']
            logger.info(f"Suscripción cancelada: {subscription['id']}")
            # TODO: Desactivar membresía
            
        # 🆕 NUEVOS EVENTOS CRÍTICOS
        elif event_type == 'customer.subscription.updated':
            # Suscripción actualizada (cambio de plan, pausa, etc.)
            subscription = event['data']['object']
            logger.info(f"Suscripción actualizada: {subscription['id']}")
            await self._handle_subscription_updated(subscription)
            
        elif event_type == 'customer.subscription.trial_will_end':
            # Período de prueba terminará pronto
            subscription = event['data']['object']
            logger.info(f"Período de prueba terminará: {subscription['id']}")
            await self._handle_trial_ending(subscription)
            
        elif event_type == 'invoice.payment_action_required':
            # Pago requiere acción del cliente (3D Secure, etc.)
            invoice = event['data']['object']
            logger.warning(f"Pago requiere acción: {invoice['id']}")
            await self._handle_payment_action_required(invoice)
            
        elif event_type == 'invoice.upcoming':
            # Próxima factura (recordatorio)
            invoice = event['data']['object']
            logger.info(f"Próxima factura: {invoice['id']}")
            await self._handle_upcoming_invoice(invoice)
            
        elif event_type == 'charge.dispute.created':
            # Nueva disputa/chargeback
            dispute = event['data']['object']
            logger.warning(f"Nueva disputa: {dispute['id']}")
            await self._handle_dispute_created(dispute)
            
        elif event_type == 'payment_intent.payment_failed':
            # Fallo específico de payment intent
            payment_intent = event['data']['object']
            logger.error(f"Payment intent falló: {payment_intent['id']}")
            await self._handle_payment_intent_failed(payment_intent)
            
        else:
            logger.warning(f"Evento no manejado: {event_type}")

        return {"status": "success", "event_type": event_type}

    # 🆕 MÉTODOS PARA MANEJAR EVENTOS ESPECÍFICOS
    
    async def _handle_subscription_updated(self, subscription: Dict[str, Any]) -> None:
        """Manejar actualización de suscripción"""
        try:
            subscription_id = subscription['id']
            status = subscription['status']
            customer_id = subscription.get('customer')
            
            # Validación de datos
            if not subscription_id or not status:
                raise ValueError("Datos incompletos en webhook de suscripción")
            
            # Buscar membresía local
            from app.models.user_gym import UserGym
            from app.db.session import SessionLocal
            from datetime import datetime
            
            db = SessionLocal()
            try:
                user_gym = db.query(UserGym).filter(
                    UserGym.stripe_subscription_id == subscription_id
                ).first()
                
                if not user_gym:
                    logger.warning(f"Membresía local no encontrada para suscripción {subscription_id}")
                    return
                
                # Actualizar estado según el status de Stripe
                status_mapping = {
                    'active': True,
                    'past_due': True,  # Mantener activo pero marcar como moroso
                    'canceled': False,
                    'unpaid': False,
                    'incomplete': False,
                    'incomplete_expired': False,
                    'trialing': True,
                    'paused': False
                }
                
                old_status = user_gym.is_active
                user_gym.is_active = status_mapping.get(status, user_gym.is_active)
                
                # Agregar nota con el cambio
                status_note = f"Stripe status: {status}"
                if status == 'past_due':
                    status_note += " - Pago vencido"
                elif status == 'canceled':
                    status_note += " - Suscripción cancelada"
                elif status == 'paused':
                    status_note += " - Suscripción pausada"
                
                user_gym.notes = f"{status_note} - {datetime.now().isoformat()}"
                
                # Actualizar fecha de expiración si está en período de prueba
                if status == 'trialing' and subscription.get('trial_end'):
                    from datetime import datetime
                    trial_end_timestamp = subscription['trial_end']
                    user_gym.membership_expires_at = datetime.fromtimestamp(trial_end_timestamp)
                
                db.commit()
                
                # Enviar notificaciones según el cambio de estado
                if old_status != user_gym.is_active:
                    if status == 'past_due':
                        await self._notify_payment_overdue(user_gym)
                    elif status == 'canceled':
                        await self._notify_subscription_canceled(user_gym)
                    elif status == 'active' and not old_status:
                        await self._notify_subscription_reactivated(user_gym)
                
                logger.info(f"Membresía actualizada: user {user_gym.user_id}, gym {user_gym.gym_id}, status: {status}")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error manejando actualización de suscripción: {str(e)}")
            # Alertar a administradores sobre el fallo del webhook
            await self._alert_webhook_failure('subscription_updated', subscription_id, str(e))
    
    async def _handle_trial_ending(self, subscription: Dict[str, Any]) -> None:
        """Manejar fin próximo de período de prueba"""
        try:
            subscription_id = subscription['id']
            trial_end = subscription['trial_end']
            customer_id = subscription.get('customer')
            
            if not subscription_id or not trial_end:
                raise ValueError("Datos incompletos en webhook de fin de prueba")
            
            # Buscar membresía local
            from app.models.user_gym import UserGym
            from app.db.session import SessionLocal
            from datetime import datetime
            
            db = SessionLocal()
            try:
                user_gym = db.query(UserGym).filter(
                    UserGym.stripe_subscription_id == subscription_id
                ).first()
                
                if not user_gym:
                    logger.warning(f"Membresía local no encontrada para suscripción {subscription_id}")
                    return
                
                # Actualizar nota sobre fin de prueba
                trial_end_date = datetime.fromtimestamp(trial_end)
                user_gym.notes = f"Período de prueba terminará: {trial_end_date.isoformat()}"
                db.commit()
                
                # Enviar notificación al usuario
                await self._notify_trial_ending(user_gym, trial_end_date)
                
                logger.info(f"Notificación de fin de prueba enviada: user {user_gym.user_id}, gym {user_gym.gym_id}")
                
            finally:
                db.close()
            
        except Exception as e:
            logger.error(f"Error manejando fin de prueba: {str(e)}")
            await self._alert_webhook_failure('trial_ending', subscription_id, str(e))
    
    async def _handle_payment_action_required(self, invoice: Dict[str, Any]) -> None:
        """Manejar pago que requiere acción del cliente"""
        try:
            invoice_id = invoice['id']
            payment_intent = invoice.get('payment_intent')
            customer_id = invoice.get('customer')
            
            # Obtener información del cliente y membresía
            if customer_id:
                from app.models.user_gym import UserGym
                from app.db.session import SessionLocal
                
                db = SessionLocal()
                try:
                    user_gym = db.query(UserGym).filter(
                        UserGym.stripe_customer_id == customer_id
                    ).first()
                    
                    if user_gym:
                        # Notificar al usuario que debe completar la autenticación
                        await self._notify_payment_action_required(user_gym, invoice_id, payment_intent)
                        
                        # Enviar link para completar el pago
                        await self._send_payment_completion_link(user_gym, payment_intent)
                finally:
                    db.close()
            
            logger.warning(f"Factura {invoice_id} requiere acción del cliente")
            
        except Exception as e:
            logger.error(f"Error manejando acción requerida: {str(e)}")
            await self._alert_webhook_failure('payment_action_required', invoice_id, str(e))
    
    async def _handle_upcoming_invoice(self, invoice: Dict[str, Any]) -> None:
        """Manejar próxima factura (recordatorio)"""
        try:
            invoice_id = invoice['id']
            amount = invoice['amount_due']
            period_end = invoice['period_end']
            customer_id = invoice.get('customer')
            
            # Obtener información del cliente y membresía
            if customer_id:
                from app.models.user_gym import UserGym
                from app.db.session import SessionLocal
                
                db = SessionLocal()
                try:
                    user_gym = db.query(UserGym).filter(
                        UserGym.stripe_customer_id == customer_id
                    ).first()
                    
                    if user_gym:
                        # Enviar recordatorio de próximo pago
                        await self._notify_upcoming_payment(user_gym, amount, period_end)
                        
                        # Verificar método de pago válido
                        await self._verify_payment_method(user_gym, customer_id)
                finally:
                    db.close()
            
            logger.info(f"Próxima factura {invoice_id} por {amount} el {period_end}")
            
        except Exception as e:
            logger.error(f"Error manejando próxima factura: {str(e)}")
            await self._alert_webhook_failure('upcoming_invoice', invoice_id, str(e))
    
    async def _handle_dispute_created(self, dispute: Dict[str, Any]) -> None:
        """Manejar nueva disputa/chargeback"""
        try:
            dispute_id = dispute['id']
            amount = dispute['amount']
            reason = dispute['reason']
            charge_id = dispute.get('charge')
            
            # Obtener información del charge y gimnasio afectado
            gym_id = None
            customer_id = None
            
            if charge_id:
                try:
                    import stripe
                    charge = stripe.Charge.retrieve(charge_id)
                    gym_id = charge.metadata.get('gym_id')
                    customer_id = charge.customer
                except Exception as charge_error:
                    logger.error(f"Error obteniendo charge {charge_id}: {charge_error}")
            
            # Notificar a administradores
            await self._notify_dispute_to_admins(dispute_id, amount, reason, gym_id)
            
            # Preparar documentación para responder
            await self._prepare_dispute_documentation(dispute_id, charge_id, gym_id)
            
            # Suspender acceso si es necesario (para disputas de alto riesgo)
            if reason in ['fraudulent', 'unauthorized'] and customer_id:
                await self._suspend_access_if_needed(customer_id, dispute_id)
            
            logger.warning(f"Nueva disputa {dispute_id}: {reason} por {amount}")
            
        except Exception as e:
            logger.error(f"Error manejando disputa: {str(e)}")
            await self._alert_webhook_failure('dispute_created', dispute_id, str(e))
    
    async def _handle_payment_intent_failed(self, payment_intent: Dict[str, Any]) -> None:
        """Manejar fallo de payment intent"""
        try:
            payment_intent_id = payment_intent['id']
            last_payment_error = payment_intent.get('last_payment_error', {})
            decline_code = last_payment_error.get('decline_code')
            customer_id = payment_intent.get('customer')
            
            # Analizar razón del fallo
            failure_reason = self._analyze_payment_failure(decline_code, last_payment_error)
            
            # Obtener información del cliente
            if customer_id:
                from app.models.user_gym import UserGym
                from app.db.session import SessionLocal
                
                db = SessionLocal()
                try:
                    user_gym = db.query(UserGym).filter(
                        UserGym.stripe_customer_id == customer_id
                    ).first()
                    
                    if user_gym:
                        # Sugerir acciones al usuario
                        await self._notify_payment_failed(user_gym, failure_reason, decline_code)
                        
                        # Implementar retry inteligente
                        await self._schedule_intelligent_retry(user_gym, payment_intent_id, failure_reason)
                finally:
                    db.close()
            
            logger.error(f"Payment intent {payment_intent_id} falló: {decline_code}")
            
        except Exception as e:
            logger.error(f"Error manejando fallo de payment intent: {str(e)}")
            await self._alert_webhook_failure('payment_intent_failed', payment_intent_id, str(e))

    async def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancelar una suscripción en Stripe"""
        try:
            stripe.Subscription.delete(subscription_id)
            logger.info(f"Suscripción cancelada: {subscription_id}")
            return True
        except stripe.error.StripeError as e:
            logger.error(f"Error al cancelar suscripción: {str(e)}")
            return False

    async def get_customer_subscriptions(self, customer_id: str) -> List[Dict[str, Any]]:
        """Obtener las suscripciones activas de un cliente"""
        try:
            subscriptions = stripe.Subscription.list(
                customer=customer_id,
                status='active'
            )
            return [sub for sub in subscriptions.data]
        except stripe.error.StripeError as e:
            logger.error(f"Error al obtener suscripciones: {str(e)}")
            return []

    # 🆕 FUNCIONALIDADES DE REEMBOLSOS
    
    async def create_refund(
        self, 
        charge_id: str, 
        amount: Optional[int] = None,
        reason: str = "requested_by_customer",
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Crear un reembolso para un pago.
        
        Args:
            charge_id: ID del charge a reembolsar
            amount: Cantidad a reembolsar en centavos (None = reembolso completo)
            reason: Razón del reembolso
            metadata: Metadatos adicionales
            
        Returns:
            dict: Información del reembolso creado
        """
        try:
            refund_data = {
                'charge': charge_id,
                'reason': reason,
                'metadata': metadata or {}
            }
            
            if amount:
                refund_data['amount'] = amount
            
            refund = stripe.Refund.create(**refund_data)
            
            logger.info(f"Reembolso creado: {refund.id} para charge {charge_id}")
            
            return {
                'refund_id': refund.id,
                'amount': refund.amount,
                'status': refund.status,
                'created': refund.created
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Error al crear reembolso: {str(e)}")
            raise ValueError(f"Error al procesar reembolso: {str(e)}")
    
    async def get_refunds_for_charge(self, charge_id: str) -> List[Dict[str, Any]]:
        """Obtener todos los reembolsos para un cargo específico"""
        try:
            refunds = stripe.Refund.list(charge=charge_id)
            return [
                {
                    'id': refund.id,
                    'amount': refund.amount,
                    'status': refund.status,
                    'reason': refund.reason,
                    'created': refund.created
                }
                for refund in refunds.data
            ]
        except stripe.error.StripeError as e:
            logger.error(f"Error al obtener reembolsos: {str(e)}")
            return []
    
    # 🆕 GESTIÓN DE CLIENTES
    
    async def create_or_update_customer(
        self,
        user_id: int,
        email: str,
        name: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Crear o actualizar un cliente en Stripe.
        
        Args:
            user_id: ID interno del usuario
            email: Email del cliente
            name: Nombre del cliente
            metadata: Metadatos adicionales
            
        Returns:
            str: ID del cliente en Stripe
        """
        try:
            customer_data = {
                'email': email,
                'name': name,
                'metadata': {
                    'internal_user_id': str(user_id),
                    **(metadata or {})
                }
            }
            
            # Buscar cliente existente por email
            existing_customers = stripe.Customer.list(email=email, limit=1)
            
            if existing_customers.data:
                # Actualizar cliente existente
                customer = stripe.Customer.modify(
                    existing_customers.data[0].id,
                    **customer_data
                )
                logger.info(f"Cliente actualizado: {customer.id}")
            else:
                # Crear nuevo cliente
                customer = stripe.Customer.create(**customer_data)
                logger.info(f"Cliente creado: {customer.id}")
            
            return customer.id
            
        except stripe.error.StripeError as e:
            logger.error(f"Error al crear/actualizar cliente: {str(e)}")
            raise ValueError(f"Error al gestionar cliente: {str(e)}")
    
    async def get_customer_payment_methods(self, customer_id: str) -> List[Dict[str, Any]]:
        """Obtener métodos de pago de un cliente"""
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type='card'
            )
            
            return [
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
            
        except stripe.error.StripeError as e:
            logger.error(f"Error al obtener métodos de pago: {str(e)}")
            return []
    
    # 🆕 PERÍODOS DE PRUEBA
    
    async def create_checkout_session_with_trial(
        self,
        db: Session,
        user_id: str,
        gym_id: int,
        plan_id: int,
        trial_days: int = 7,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Crear sesión de checkout con período de prueba.
        
        Args:
            trial_days: Días de prueba gratuita
        """
        try:
            # Obtener el plan de membresía
            plan = db.query(MembershipPlan).filter(
                MembershipPlan.id == plan_id,
                MembershipPlan.gym_id == gym_id,
                MembershipPlan.is_active == True
            ).first()
            
            if not plan:
                raise ValueError("Plan de membresía no encontrado")

            if not plan.stripe_price_id:
                raise ValueError("El plan no tiene configurado un precio en Stripe")

            # Solo para suscripciones
            if plan.billing_interval == 'one_time':
                raise ValueError("Los períodos de prueba solo aplican a suscripciones")

            success_url = success_url or settings.STRIPE_SUCCESS_URL
            cancel_url = cancel_url or settings.STRIPE_CANCEL_URL

            # Crear sesión con período de prueba
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': plan.stripe_price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=cancel_url,
                subscription_data={
                    'trial_period_days': trial_days,
                    'metadata': {
                        'gym_id': str(gym_id),
                        'plan_id': str(plan_id),
                        'trial_days': str(trial_days)
                    }
                },
                metadata={
                    'user_id': user_id,
                    'gym_id': str(gym_id),
                    'plan_id': str(plan_id),
                    'plan_name': plan.name,
                    'trial_days': str(trial_days)
                },
                allow_promotion_codes=True,
            )

            logger.info(f"Checkout con prueba creado: {checkout_session.id} ({trial_days} días)")
            
            return {
                'checkout_session_id': checkout_session.id,
                'checkout_url': checkout_session.url,
                'plan_name': plan.name,
                'price': plan.price_cents / 100,
                'currency': plan.currency,
                'trial_days': trial_days
            }

        except stripe.error.StripeError as e:
            logger.error(f"Error al crear checkout con prueba: {str(e)}")
            raise ValueError(f"Error al procesar el pago: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al crear checkout con prueba: {str(e)}")
            raise

    # === Sincronización Plan Local ↔ Stripe ===

    async def create_stripe_product_for_plan(
        self, 
        db: Session, 
        plan: MembershipPlan
    ) -> Dict[str, str]:
        """
        Crear producto y precio en Stripe para un plan local.
        
        Args:
            db: Sesión de base de datos
            plan: Plan de membresía local
            
        Returns:
            dict: {'product_id': str, 'price_id': str}
            
        Raises:
            ValueError: Si hay error en Stripe
        """
        try:
            # Crear producto en Stripe
            product = stripe.Product.create(
                name=plan.name,
                description=plan.description or f"Plan de membresía {plan.name}",
                metadata={
                    'gym_id': str(plan.gym_id),
                    'local_plan_id': str(plan.id),
                    'created_by': 'gym_api'
                }
            )
            
            logger.info(f"Producto Stripe creado: {product.id} para plan {plan.id}")
            
            # Crear precio en Stripe
            price_data = {
                'unit_amount': plan.price_cents,
                'currency': plan.currency.lower(),
                'product': product.id,
                'metadata': {
                    'gym_id': str(plan.gym_id),
                    'local_plan_id': str(plan.id),
                    'billing_interval': plan.billing_interval
                }
            }
            
            # Configurar recurrencia si aplica
            if plan.billing_interval in ['month', 'year']:
                price_data['recurring'] = {'interval': plan.billing_interval}
            
            price = stripe.Price.create(**price_data)
            
            logger.info(f"Precio Stripe creado: {price.id} para plan {plan.id}")
            
            # Actualizar plan local con IDs de Stripe
            plan.stripe_product_id = product.id
            plan.stripe_price_id = price.id
            db.commit()
            db.refresh(plan)
            
            return {
                'product_id': product.id,
                'price_id': price.id
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Error de Stripe al crear producto para plan {plan.id}: {str(e)}")
            raise ValueError(f"Error al crear producto en Stripe: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al crear producto Stripe: {str(e)}")
            raise

    async def update_stripe_product_for_plan(
        self, 
        db: Session, 
        plan: MembershipPlan
    ) -> bool:
        """
        Actualizar producto existente en Stripe cuando se modifica un plan local.
        
        Args:
            db: Sesión de base de datos
            plan: Plan modificado
            
        Returns:
            bool: True si se actualizó correctamente
        """
        try:
            if not plan.stripe_product_id:
                logger.warning(f"Plan {plan.id} no tiene producto en Stripe. Creando...")
                await self.create_stripe_product_for_plan(db, plan)
                return True
            
            # Actualizar producto en Stripe
            stripe.Product.modify(
                plan.stripe_product_id,
                name=plan.name,
                description=plan.description or f"Plan de membresía {plan.name}",
                active=plan.is_active,
                metadata={
                    'gym_id': str(plan.gym_id),
                    'local_plan_id': str(plan.id),
                    'updated_by': 'gym_api'
                }
            )
            
            logger.info(f"Producto Stripe {plan.stripe_product_id} actualizado para plan {plan.id}")
            
            # Si cambió el precio, crear nuevo Price (Stripe no permite modificar precios)
            if plan.stripe_price_id:
                try:
                    existing_price = stripe.Price.retrieve(plan.stripe_price_id)
                    
                    # Verificar si cambió el precio
                    if (existing_price.unit_amount != plan.price_cents or 
                        existing_price.currency != plan.currency.lower()):
                        
                        logger.info(f"Precio cambió para plan {plan.id}, creando nuevo precio en Stripe")
                        
                        # Desactivar precio anterior
                        stripe.Price.modify(plan.stripe_price_id, active=False)
                        
                        # Crear nuevo precio
                        price_data = {
                            'unit_amount': plan.price_cents,
                            'currency': plan.currency.lower(),
                            'product': plan.stripe_product_id,
                            'metadata': {
                                'gym_id': str(plan.gym_id),
                                'local_plan_id': str(plan.id),
                                'billing_interval': plan.billing_interval
                            }
                        }
                        
                        if plan.billing_interval in ['month', 'year']:
                            price_data['recurring'] = {'interval': plan.billing_interval}
                        
                        new_price = stripe.Price.create(**price_data)
                        
                        # Actualizar plan local con nuevo price_id
                        plan.stripe_price_id = new_price.id
                        db.commit()
                        
                        logger.info(f"Nuevo precio Stripe creado: {new_price.id} para plan {plan.id}")
                        
                except stripe.error.StripeError as price_error:
                    logger.error(f"Error al actualizar precio Stripe: {str(price_error)}")
                    # Continúa aunque falle el precio, el producto se actualizó
            
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Error de Stripe al actualizar producto para plan {plan.id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado al actualizar producto Stripe: {str(e)}")
            return False

    async def deactivate_stripe_product_for_plan(
        self, 
        plan: MembershipPlan
    ) -> bool:
        """
        Desactivar producto en Stripe cuando se desactiva un plan local.
        
        Args:
            plan: Plan desactivado
            
        Returns:
            bool: True si se desactivó correctamente
        """
        try:
            if not plan.stripe_product_id:
                logger.warning(f"Plan {plan.id} no tiene producto en Stripe")
                return True
            
            # Desactivar producto en Stripe
            stripe.Product.modify(
                plan.stripe_product_id,
                active=False,
                metadata={
                    'deactivated_by': 'gym_api',
                    'deactivated_at': datetime.now().isoformat()
                }
            )
            
            # Desactivar precio si existe
            if plan.stripe_price_id:
                stripe.Price.modify(plan.stripe_price_id, active=False)
            
            logger.info(f"Producto Stripe {plan.stripe_product_id} desactivado para plan {plan.id}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Error de Stripe al desactivar producto para plan {plan.id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado al desactivar producto Stripe: {str(e)}")
            return False

    async def sync_plan_with_stripe(
        self, 
        db: Session, 
        plan_id: int
    ) -> bool:
        """
        Sincronizar un plan específico con Stripe.
        
        Args:
            db: Sesión de base de datos
            plan_id: ID del plan a sincronizar
            
        Returns:
            bool: True si se sincronizó correctamente
        """
        try:
            plan = db.query(MembershipPlan).filter(MembershipPlan.id == plan_id).first()
            if not plan:
                logger.error(f"Plan {plan_id} no encontrado")
                return False
            
            if plan.is_active:
                if plan.stripe_product_id:
                    # Actualizar producto existente
                    return await self.update_stripe_product_for_plan(db, plan)
                else:
                    # Crear nuevo producto
                    result = await self.create_stripe_product_for_plan(db, plan)
                    return bool(result)
            else:
                # Desactivar producto
                return await self.deactivate_stripe_product_for_plan(plan)
                
        except Exception as e:
            logger.error(f"Error al sincronizar plan {plan_id} con Stripe: {str(e)}")
            return False

# 🆕 MÉTODOS DE NOTIFICACIÓN Y ALERTAS

    async def _notify_payment_overdue(self, user_gym) -> None:
        """Notificar al usuario sobre pago vencido"""
        try:
            from app.services.notification import notification_service
            from app.models.user import User
            from app.db.session import SessionLocal
            
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_gym.user_id).first()
                if user and user.onesignal_player_id:
                    await notification_service.send_notification(
                        player_id=user.onesignal_player_id,
                        title="Pago Vencido",
                        message="Tu pago de membresía está vencido. Por favor actualiza tu método de pago.",
                        data={
                            "type": "payment_overdue",
                            "gym_id": str(user_gym.gym_id),
                            "subscription_id": user_gym.stripe_subscription_id
                        }
                    )
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error enviando notificación de pago vencido: {str(e)}")
    
    async def _notify_subscription_canceled(self, user_gym) -> None:
        """Notificar al usuario sobre cancelación de suscripción"""
        try:
            from app.services.notification import notification_service
            from app.models.user import User
            from app.db.session import SessionLocal
            
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_gym.user_id).first()
                if user and user.onesignal_player_id:
                    await notification_service.send_notification(
                        player_id=user.onesignal_player_id,
                        title="Suscripción Cancelada",
                        message="Tu suscripción ha sido cancelada. Esperamos verte pronto de vuelta.",
                        data={
                            "type": "subscription_canceled",
                            "gym_id": str(user_gym.gym_id)
                        }
                    )
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error enviando notificación de cancelación: {str(e)}")
    
    async def _notify_subscription_reactivated(self, user_gym) -> None:
        """Notificar al usuario sobre reactivación de suscripción"""
        try:
            from app.services.notification import notification_service
            from app.models.user import User
            from app.db.session import SessionLocal
            
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_gym.user_id).first()
                if user and user.onesignal_player_id:
                    await notification_service.send_notification(
                        player_id=user.onesignal_player_id,
                        title="¡Bienvenido de Vuelta!",
                        message="Tu suscripción ha sido reactivada. ¡Disfruta del gimnasio!",
                        data={
                            "type": "subscription_reactivated",
                            "gym_id": str(user_gym.gym_id)
                        }
                    )
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error enviando notificación de reactivación: {str(e)}")
    
    async def _notify_trial_ending(self, user_gym, trial_end_date) -> None:
        """Notificar al usuario sobre fin próximo de período de prueba"""
        try:
            from app.services.notification import notification_service
            from app.models.user import User
            from app.db.session import SessionLocal
            
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_gym.user_id).first()
                if user and user.onesignal_player_id:
                    await notification_service.send_notification(
                        player_id=user.onesignal_player_id,
                        title="Período de Prueba Terminando",
                        message=f"Tu período de prueba termina el {trial_end_date.strftime('%d/%m/%Y')}. ¡No pierdas el acceso!",
                        data={
                            "type": "trial_ending",
                            "gym_id": str(user_gym.gym_id),
                            "trial_end": trial_end_date.isoformat()
                        }
                    )
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error enviando notificación de fin de prueba: {str(e)}")
    
    async def _alert_webhook_failure(self, event_type: str, resource_id: str, error_message: str) -> None:
        """Alertar a administradores sobre fallos en webhooks"""
        try:
            from app.services.notification import notification_service
            from app.models.user import User
            from app.models.user_gym import UserGym, GymRoleType
            from app.db.session import SessionLocal
            
            db = SessionLocal()
            try:
                # Buscar administradores del sistema (owners/admins de todos los gimnasios)
                admin_users = db.query(User).join(UserGym).filter(
                    UserGym.role.in_([GymRoleType.OWNER, GymRoleType.ADMIN])
                ).distinct().all()
                
                for admin in admin_users:
                    if admin.onesignal_player_id:
                        await notification_service.send_notification(
                            player_id=admin.onesignal_player_id,
                            title="Error en Webhook de Stripe",
                            message=f"Fallo procesando {event_type} para {resource_id}",
                            data={
                                "type": "webhook_failure",
                                "event_type": event_type,
                                "resource_id": resource_id,
                                "error": error_message
                            }
                        )
                        
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error enviando alerta de webhook: {str(e)}")

    # 🆕 MÉTODOS ADICIONALES DE NOTIFICACIÓN PARA TODOs COMPLETADOS
    
    async def _notify_payment_action_required(self, user_gym, invoice_id: str, payment_intent_id: str) -> None:
        """Notificar al usuario que debe completar la autenticación del pago"""
        try:
            from app.services.notification import notification_service
            from app.models.user import User
            from app.db.session import SessionLocal
            
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_gym.user_id).first()
                if user and user.onesignal_player_id:
                    await notification_service.send_notification(
                        player_id=user.onesignal_player_id,
                        title="Acción Requerida en tu Pago",
                        message="Tu pago requiere autenticación adicional. Por favor completa el proceso.",
                        data={
                            "type": "payment_action_required",
                            "gym_id": str(user_gym.gym_id),
                            "invoice_id": invoice_id,
                            "payment_intent_id": payment_intent_id
                        }
                    )
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error enviando notificación de acción requerida: {str(e)}")
    
    async def _send_payment_completion_link(self, user_gym, payment_intent_id: str) -> None:
        """Enviar link para completar el pago"""
        try:
            # En una implementación real, aquí crearías un link personalizado
            # que redirija al usuario a la página de confirmación de pago
            completion_url = f"{get_settings().FRONTEND_URL}/payment/complete?pi={payment_intent_id}"
            
            from app.services.notification import notification_service
            from app.models.user import User
            from app.db.session import SessionLocal
            
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_gym.user_id).first()
                if user and user.onesignal_player_id:
                    await notification_service.send_notification(
                        player_id=user.onesignal_player_id,
                        title="Completa tu Pago",
                        message="Toca aquí para completar tu pago pendiente",
                        data={
                            "type": "payment_completion_link",
                            "gym_id": str(user_gym.gym_id),
                            "completion_url": completion_url,
                            "payment_intent_id": payment_intent_id
                        }
                    )
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error enviando link de completar pago: {str(e)}")
    
    async def _notify_upcoming_payment(self, user_gym, amount: int, period_end: int) -> None:
        """Enviar recordatorio de próximo pago"""
        try:
            from datetime import datetime
            from app.services.notification import notification_service
            from app.models.user import User
            from app.db.session import SessionLocal
            
            # Convertir timestamp a fecha legible
            end_date = datetime.fromtimestamp(period_end)
            amount_eur = amount / 100  # Convertir de centavos a euros
            
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_gym.user_id).first()
                if user and user.onesignal_player_id:
                    await notification_service.send_notification(
                        player_id=user.onesignal_player_id,
                        title="Próximo Pago de Membresía",
                        message=f"Tu próximo pago de €{amount_eur:.2f} será procesado el {end_date.strftime('%d/%m/%Y')}",
                        data={
                            "type": "upcoming_payment",
                            "gym_id": str(user_gym.gym_id),
                            "amount": amount,
                            "period_end": end_date.isoformat()
                        }
                    )
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error enviando recordatorio de próximo pago: {str(e)}")
    
    async def _verify_payment_method(self, user_gym, customer_id: str) -> None:
        """Verificar que el método de pago del cliente sea válido"""
        try:
            import stripe
            from datetime import datetime
            
            # Obtener métodos de pago del cliente
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type="card"
            )
            
            valid_methods = [pm for pm in payment_methods.data if pm.card.get('exp_year', 0) > datetime.now().year or 
                          (pm.card.get('exp_year', 0) == datetime.now().year and pm.card.get('exp_month', 0) >= datetime.now().month)]
            
            if not valid_methods:
                # No hay métodos de pago válidos
                from app.services.notification import notification_service
                from app.models.user import User
                from app.db.session import SessionLocal
                
                db = SessionLocal()
                try:
                    user = db.query(User).filter(User.id == user_gym.user_id).first()
                    if user and user.onesignal_player_id:
                        await notification_service.send_notification(
                            player_id=user.onesignal_player_id,
                            title="Actualiza tu Método de Pago",
                            message="Tu tarjeta está próxima a vencer o no es válida. Por favor actualiza tu método de pago.",
                            data={
                                "type": "payment_method_invalid",
                                "gym_id": str(user_gym.gym_id),
                                "customer_id": customer_id
                            }
                        )
                finally:
                    db.close()
                    
        except Exception as e:
            logger.error(f"Error verificando método de pago: {str(e)}")
    
    async def _notify_dispute_to_admins(self, dispute_id: str, amount: int, reason: str, gym_id: Optional[str]) -> None:
        """Notificar a administradores sobre nueva disputa"""
        try:
            from app.services.notification import notification_service
            from app.models.user import User
            from app.models.user_gym import UserGym, GymRoleType
            from app.db.session import SessionLocal
            
            amount_eur = amount / 100
            
            db = SessionLocal()
            try:
                # Buscar administradores del gimnasio específico o todos si no se especifica
                query = db.query(User).join(UserGym).filter(
                    UserGym.role.in_([GymRoleType.OWNER, GymRoleType.ADMIN])
                )
                
                if gym_id:
                    query = query.filter(UserGym.gym_id == int(gym_id))
                
                admin_users = query.distinct().all()
                
                for admin in admin_users:
                    if admin.onesignal_player_id:
                        await notification_service.send_notification(
                            player_id=admin.onesignal_player_id,
                            title="🚨 Nueva Disputa de Pago",
                            message=f"Disputa por €{amount_eur:.2f} - Razón: {reason}",
                            data={
                                "type": "dispute_created",
                                "dispute_id": dispute_id,
                                "amount": amount,
                                "reason": reason,
                                "gym_id": gym_id or "unknown"
                            }
                        )
                        
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error notificando disputa a admins: {str(e)}")
    
    async def _prepare_dispute_documentation(self, dispute_id: str, charge_id: Optional[str], gym_id: Optional[str]) -> None:
        """Preparar documentación para responder a la disputa"""
        try:
            # En una implementación real, aquí generarías automáticamente
            # la documentación necesaria para responder a la disputa
            
            documentation = {
                "dispute_id": dispute_id,
                "charge_id": charge_id,
                "gym_id": gym_id,
                "timestamp": datetime.now().isoformat(),
                "status": "pending_review",
                "documents_needed": [
                    "customer_communication",
                    "service_documentation", 
                    "receipt",
                    "terms_of_service"
                ]
            }
            
            # Aquí podrías guardar esto en una tabla de disputas para seguimiento
            logger.info(f"Documentación preparada para disputa {dispute_id}: {documentation}")
            
        except Exception as e:
            logger.error(f"Error preparando documentación de disputa: {str(e)}")
    
    async def _suspend_access_if_needed(self, customer_id: str, dispute_id: str) -> None:
        """Suspender acceso del usuario si la disputa es de alto riesgo"""
        try:
            from app.models.user_gym import UserGym
            from app.db.session import SessionLocal
            
            db = SessionLocal()
            try:
                # Buscar la membresía del cliente
                user_gym = db.query(UserGym).filter(
                    UserGym.stripe_customer_id == customer_id
                ).first()
                
                if user_gym:
                    # Marcar como suspendido temporalmente
                    user_gym.is_suspended = True
                    user_gym.suspension_reason = f"Disputa fraudulenta: {dispute_id}"
                    db.commit()
                    
                    # Notificar al usuario
                    from app.services.notification import notification_service
                    from app.models.user import User
                    
                    user = db.query(User).filter(User.id == user_gym.user_id).first()
                    if user and user.onesignal_player_id:
                        await notification_service.send_notification(
                            player_id=user.onesignal_player_id,
                            title="Acceso Temporalmente Suspendido",
                            message="Tu acceso ha sido suspendido temporalmente debido a una disputa de pago. Contacta con soporte.",
                            data={
                                "type": "access_suspended",
                                "gym_id": str(user_gym.gym_id),
                                "dispute_id": dispute_id
                            }
                        )
                        
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error suspendiendo acceso: {str(e)}")
    
    def _analyze_payment_failure(self, decline_code: Optional[str], last_payment_error: Dict[str, Any]) -> str:
        """Analizar la razón del fallo de pago y devolver mensaje amigable"""
        try:
            if not decline_code:
                return "Error desconocido en el pago"
            
            failure_reasons = {
                "insufficient_funds": "Fondos insuficientes en tu cuenta",
                "card_declined": "Tu tarjeta fue rechazada por el banco",
                "expired_card": "Tu tarjeta ha expirado",
                "incorrect_cvc": "El código CVC es incorrecto",
                "processing_error": "Error temporal del procesador de pagos",
                "invalid_expiry_month": "El mes de expiración es inválido",
                "invalid_expiry_year": "El año de expiración es inválido",
                "invalid_number": "El número de tarjeta es inválido",
                "lost_card": "La tarjeta fue reportada como perdida",
                "stolen_card": "La tarjeta fue reportada como robada",
                "generic_decline": "El pago fue rechazado por tu banco"
            }
            
            return failure_reasons.get(decline_code, f"Error de pago: {decline_code}")
            
        except Exception as e:
            logger.error(f"Error analizando fallo de pago: {str(e)}")
            return "Error desconocido en el pago"
    
    async def _notify_payment_failed(self, user_gym, failure_reason: str, decline_code: Optional[str]) -> None:
        """Notificar al usuario sobre fallo de pago con sugerencias"""
        try:
            from app.services.notification import notification_service
            from app.models.user import User
            from app.db.session import SessionLocal
            
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_gym.user_id).first()
                if user and user.onesignal_player_id:
                    await notification_service.send_notification(
                        player_id=user.onesignal_player_id,
                        title="Pago No Procesado",
                        message=f"{failure_reason}. Por favor verifica tu método de pago.",
                        data={
                            "type": "payment_failed",
                            "gym_id": str(user_gym.gym_id),
                            "failure_reason": failure_reason,
                            "decline_code": decline_code or "unknown"
                        }
                    )
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error enviando notificación de pago fallido: {str(e)}")
    
    async def _schedule_intelligent_retry(self, user_gym, payment_intent_id: str, failure_reason: str) -> None:
        """Programar reintento inteligente basado en el tipo de fallo"""
        try:
            # Determinar estrategia de reintento basada en el tipo de fallo
            retry_strategies = {
                "insufficient_funds": 72,  # 3 días
                "card_declined": 24,       # 1 día  
                "processing_error": 1,     # 1 hora
                "generic_decline": 48      # 2 días
            }
            
            # Determinar horas para el próximo intento
            retry_hours = retry_strategies.get("generic_decline", 24)  # Default 24 horas
            
            for reason_key in retry_strategies:
                if reason_key in failure_reason.lower():
                    retry_hours = retry_strategies[reason_key]
                    break
            
            # En una implementación real, aquí programarías una tarea en segundo plano
            # para reintentar el pago después del tiempo especificado
            
            logger.info(f"Reintento programado para payment_intent {payment_intent_id} en {retry_hours} horas")
            
            # Notificar al usuario sobre el reintento programado
            from app.services.notification import notification_service
            from app.models.user import User
            from app.db.session import SessionLocal
            
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_gym.user_id).first()
                if user and user.onesignal_player_id:
                    await notification_service.send_notification(
                        player_id=user.onesignal_player_id,
                        title="Reintento de Pago Programado",
                        message=f"Reintentaremos procesar tu pago en {retry_hours} horas.",
                        data={
                            "type": "payment_retry_scheduled",
                            "gym_id": str(user_gym.gym_id),
                            "retry_hours": retry_hours,
                            "payment_intent_id": payment_intent_id
                        }
                    )
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error programando reintento inteligente: {str(e)}") 