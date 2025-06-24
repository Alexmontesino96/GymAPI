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
stripe.api_key = settings.SECRET_KEY

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
            # Obtener el plan de membresía
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
                    'plan_id': str(plan_id),
                    'plan_name': plan.name
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
            logger.warning("STRIPE_WEBHOOK_SECRET no configurado, saltando verificación")
            return {"status": "webhook_secret_not_configured"}

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
            
        elif event_type == 'invoice.payment_failed':
            # Pago de suscripción fallido
            invoice = event['data']['object']
            logger.warning(f"Pago de suscripción fallido: {invoice['id']}")
            
        elif event_type == 'customer.subscription.deleted':
            # Suscripción cancelada
            subscription = event['data']['object']
            logger.info(f"Suscripción cancelada: {subscription['id']}")

        return {"status": "success", "event_type": event_type}

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