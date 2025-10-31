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

from app.models.event import Event, EventParticipation, RefundPolicyType, PaymentStatusType, EventParticipationStatus
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

            logger.info(
                f"[Stripe Account] Usando cuenta de Stripe Connect del gym {gym_id}: "
                f"{stripe_account.stripe_account_id}"
            )

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

    async def get_or_create_payment_intent_for_event(
        self,
        db: Session,
        event: Event,
        user: User,
        gym_id: int,
        participation: EventParticipation
    ) -> Dict[str, Any]:
        """
        Obtener o crear un Payment Intent para un evento (función idempotente).

        Verifica si ya existe un Payment Intent válido antes de crear uno nuevo.
        Esto previene la creación de Payment Intents duplicados.

        Args:
            db: Sesión de base de datos
            event: Evento a pagar
            user: Usuario que realiza el pago
            gym_id: ID del gimnasio
            participation: Participación asociada

        Returns:
            Diccionario con client_secret y payment_intent_id
        """
        try:
            # Obtener cuenta de Stripe Connect
            stripe_account = db.query(GymStripeAccount).filter(
                GymStripeAccount.gym_id == gym_id
            ).first()

            if not stripe_account:
                raise ValueError("Cuenta de Stripe no configurada")

            logger.info(
                f"[Stripe Account] Verificando Payment Intent para gym {gym_id} "
                f"con cuenta: {stripe_account.stripe_account_id}"
            )

            # Verificar si ya existe un Payment Intent
            if participation.stripe_payment_intent_id:
                logger.info(
                    f"[Idempotencia] Participación {participation.id} ya tiene Payment Intent: "
                    f"{participation.stripe_payment_intent_id}"
                )

                try:
                    # Intentar recuperar Payment Intent existente
                    existing_pi = stripe.PaymentIntent.retrieve(
                        participation.stripe_payment_intent_id,
                        stripe_account=stripe_account.stripe_account_id
                    )

                    logger.info(
                        f"[Idempotencia] Payment Intent {existing_pi.id} encontrado con estado: {existing_pi.status}"
                    )

                    # Verificar si es reutilizable
                    if existing_pi.status in ['requires_payment_method', 'requires_confirmation', 'requires_action', 'processing']:
                        # Payment Intent todavía es válido, reutilizarlo
                        logger.info(
                            f"[Idempotencia] Reutilizando Payment Intent {existing_pi.id} "
                            f"para participación {participation.id}"
                        )

                        # Validar consistencia del client_secret
                        pi_id_from_secret = existing_pi.client_secret.split('_secret_')[0] if existing_pi.client_secret else None
                        if pi_id_from_secret != existing_pi.id:
                            logger.error(
                                f"[Validación] ¡INCONSISTENCIA! Payment Intent ID {existing_pi.id} "
                                f"no coincide con ID extraído del client_secret: {pi_id_from_secret}"
                            )

                        return {
                            "client_secret": existing_pi.client_secret,
                            "payment_intent_id": existing_pi.id,
                            "amount": event.price_cents,
                            "currency": event.currency,
                            "reused": True
                        }

                    elif existing_pi.status == 'succeeded':
                        # Ya fue pagado, no crear nuevo
                        logger.warning(
                            f"[Idempotencia] Payment Intent {existing_pi.id} ya fue pagado. "
                            f"Participación {participation.id} debería estar en estado PAID"
                        )
                        return {
                            "client_secret": existing_pi.client_secret,
                            "payment_intent_id": existing_pi.id,
                            "amount": existing_pi.amount,
                            "currency": existing_pi.currency,
                            "reused": True,
                            "already_paid": True
                        }

                    else:  # canceled, requires_payment_method con fallo, etc.
                        logger.info(
                            f"[Idempotencia] Payment Intent {existing_pi.id} tiene estado "
                            f"{existing_pi.status}, creando uno nuevo"
                        )
                        # Continuar para crear uno nuevo

                except stripe.error.InvalidRequestError as e:
                    logger.warning(
                        f"[Idempotencia] Payment Intent {participation.stripe_payment_intent_id} "
                        f"no encontrado en Stripe: {e}. Creando uno nuevo"
                    )
                    # Continuar para crear uno nuevo

                except stripe.error.StripeError as e:
                    logger.error(f"[Idempotencia] Error verificando Payment Intent: {e}")
                    # En caso de error, continuar para crear uno nuevo

            # Si llegamos aquí, necesitamos crear un nuevo Payment Intent
            logger.info(
                f"[Creación] Creando nuevo Payment Intent para participación {participation.id}, "
                f"evento {event.id}, usuario {user.id}"
            )

            payment_info = await self.create_payment_intent_for_event(
                db=db,
                event=event,
                user=user,
                gym_id=gym_id
            )

            # Validar consistencia del client_secret
            pi_id_from_secret = payment_info["client_secret"].split('_secret_')[0] if payment_info.get("client_secret") else None
            if pi_id_from_secret != payment_info["payment_intent_id"]:
                logger.error(
                    f"[Validación] ¡INCONSISTENCIA! Payment Intent ID {payment_info['payment_intent_id']} "
                    f"no coincide con ID extraído del client_secret: {pi_id_from_secret}"
                )
            else:
                logger.info(
                    f"[Validación] ✅ Payment Intent ID y client_secret son consistentes: {payment_info['payment_intent_id']}"
                )

            # Log completo para debugging
            logger.info(
                f"[Creación] Payment Intent creado exitosamente:\n"
                f"  - Participación ID: {participation.id}\n"
                f"  - Payment Intent ID: {payment_info['payment_intent_id']}\n"
                f"  - Client Secret: {payment_info['client_secret'][:50]}...\n"
                f"  - Monto: {payment_info['amount']} {payment_info['currency']}"
            )

            payment_info["reused"] = False
            return payment_info

        except Exception as e:
            logger.error(
                f"[Error] Error en get_or_create_payment_intent_for_event para "
                f"participación {participation.id}: {e}"
            )
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
        payment_intent_id: Optional[str] = None
    ) -> EventParticipation:
        """
        Confirmar el pago exitoso de un evento con estrategia robusta de 3 niveles.

        ESTRATEGIA DE FALLBACK:
        NIVEL 1: Polling a BD (esperar que webhook actualice) - 80% de casos
        NIVEL 2: Fallback directo con payment_intent_id - 15% de casos
        NIVEL 3: Búsqueda por metadata (recuperación total) - 5% de casos

        Args:
            db: Sesión de base de datos
            participation: Participación a actualizar
            payment_intent_id: ID del Payment Intent de Stripe (opcional)

        Returns:
            Participación actualizada
        """
        import asyncio

        try:
            # Obtener datos necesarios
            event = db.query(Event).filter(Event.id == participation.event_id).first()
            stripe_account = db.query(GymStripeAccount).filter(
                GymStripeAccount.gym_id == participation.gym_id
            ).first()

            if not stripe_account:
                raise ValueError("Cuenta de Stripe no configurada")

            # ========================================
            # NIVEL 1: POLLING - Esperar que webhook actualice
            # ========================================
            max_retries = 5
            retry_delay = 1.0

            logger.info(
                f"[Confirmación] Iniciando verificación para participación {participation.id}. "
                f"Payment Intent ID proporcionado: {payment_intent_id or 'None'}"
            )

            for attempt in range(max_retries):
                db.refresh(participation)

                if participation.payment_status == PaymentStatusType.PAID:
                    logger.info(
                        f"[Nivel 1] ✅ Pago confirmado por webhook en intento {attempt + 1}/{max_retries}"
                    )
                    return participation

                if attempt < max_retries - 1:
                    logger.info(
                        f"[Nivel 1] Intento {attempt + 1}/{max_retries}: payment_status={participation.payment_status}. "
                        f"Esperando {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)

            logger.warning(
                f"[Nivel 1] Webhook no actualizó en {max_retries * retry_delay}s. "
                f"Pasando a fallback de Stripe API..."
            )

            # ========================================
            # NIVEL 2: FALLBACK DIRECTO - Usar payment_intent_id conocido
            # ========================================

            # Determinar qué payment_intent_id usar
            pi_id_to_use = payment_intent_id or participation.stripe_payment_intent_id

            if pi_id_to_use:
                logger.info(
                    f"[Nivel 2] Intentando retrieve directo con Payment Intent: {pi_id_to_use} "
                    f"(fuente: {'parámetro' if payment_intent_id else 'BD'})"
                )

                try:
                    payment_intent = stripe.PaymentIntent.retrieve(
                        pi_id_to_use,
                        stripe_account=stripe_account.stripe_account_id
                    )

                    if payment_intent.status == "succeeded":
                        logger.info(f"[Nivel 2] ✅ Payment Intent {pi_id_to_use} confirmado")
                        return await self._process_successful_payment(
                            db, participation, event, payment_intent
                        )
                    else:
                        logger.warning(
                            f"[Nivel 2] Payment Intent {pi_id_to_use} tiene estado {payment_intent.status}, "
                            f"no 'succeeded'"
                        )
                        # Continuar a Nivel 3

                except stripe.error.InvalidRequestError as e:
                    logger.warning(
                        f"[Nivel 2] Payment Intent {pi_id_to_use} no encontrado: {e}. "
                        f"Pasando a búsqueda por metadata..."
                    )
                    # Continuar a Nivel 3

                except stripe.error.StripeError as e:
                    logger.error(f"[Nivel 2] Error de Stripe: {e}")
                    # Continuar a Nivel 3
            else:
                logger.warning(
                    f"[Nivel 2] No hay payment_intent_id disponible (parámetro: {payment_intent_id}, "
                    f"BD: {participation.stripe_payment_intent_id}). "
                    f"Pasando directamente a búsqueda por metadata..."
                )

            # ========================================
            # NIVEL 3: BÚSQUEDA POR METADATA - Último recurso robusto
            # ========================================

            logger.warning(
                f"[Nivel 3 - Fallback Metadata] Buscando Payment Intent por metadata: "
                f"event_id={event.id}, user_id={participation.member_id}, gym_id={participation.gym_id}"
            )

            try:
                # Construir query para Stripe Search API
                search_query = (
                    f"metadata['event_id']:'{event.id}' AND "
                    f"metadata['user_id']:'{participation.member_id}' AND "
                    f"metadata['gym_id']:'{participation.gym_id}' AND "
                    f"status:'succeeded'"
                )

                logger.info(f"[Nivel 3] Query de búsqueda: {search_query}")

                result = stripe.PaymentIntent.search(
                    query=search_query,
                    stripe_account=stripe_account.stripe_account_id,
                    limit=10  # Máximo razonable
                )

                if not result.data:
                    # No se encontró ningún Payment Intent
                    raise ValueError(
                        f"No se encontró ningún pago exitoso para evento {event.id}, "
                        f"usuario {participation.member_id}. El pago puede estar aún procesándose. "
                        f"Espera unos segundos e intenta de nuevo. "
                        f"Si el problema persiste, contacta a soporte con ID de participación: {participation.id}"
                    )

                # Filtrar y ordenar Payment Intents exitosos
                succeeded_intents = [pi for pi in result.data if pi.status == 'succeeded']

                if not succeeded_intents:
                    raise ValueError(
                        f"Se encontraron {len(result.data)} Payment Intent(s) pero ninguno con status 'succeeded'. "
                        f"El pago puede estar aún procesándose."
                    )

                # Si hay múltiples, usar el más reciente
                if len(succeeded_intents) > 1:
                    logger.warning(
                        f"[Nivel 3] ⚠️ Se encontraron {len(succeeded_intents)} Payment Intents exitosos. "
                        f"IDs: {[pi.id for pi in succeeded_intents]}. "
                        f"Usando el más reciente."
                    )
                    succeeded_intents.sort(key=lambda x: x.created, reverse=True)

                payment_intent = succeeded_intents[0]

                logger.info(
                    f"[Nivel 3] ✅ Payment Intent encontrado por metadata: {payment_intent.id} "
                    f"(creado: {datetime.fromtimestamp(payment_intent.created)}, "
                    f"monto: {payment_intent.amount} {payment_intent.currency})"
                )

                # CRÍTICO: Auto-reparación - Actualizar BD con el ID encontrado
                if not participation.stripe_payment_intent_id:
                    logger.info(
                        f"[Nivel 3] 🔧 Auto-reparación: Actualizando participation.stripe_payment_intent_id "
                        f"de NULL a {payment_intent.id}"
                    )
                    participation.stripe_payment_intent_id = payment_intent.id
                    db.commit()
                elif participation.stripe_payment_intent_id != payment_intent.id:
                    logger.warning(
                        f"[Nivel 3] ⚠️ Inconsistencia: BD tiene {participation.stripe_payment_intent_id} "
                        f"pero metadata encontró {payment_intent.id}. Actualizando a {payment_intent.id}"
                    )
                    participation.stripe_payment_intent_id = payment_intent.id
                    db.commit()

                return await self._process_successful_payment(
                    db, participation, event, payment_intent
                )

            except stripe.error.StripeError as e:
                logger.error(f"[Nivel 3] Error buscando Payment Intent por metadata: {e}")
                raise ValueError(
                    f"Error verificando pago con Stripe: {str(e)}. "
                    f"Por favor contacta a soporte con ID de participación: {participation.id}"
                )

        except ValueError:
            # Re-raise ValueError para que el endpoint lo maneje
            raise
        except Exception as e:
            logger.error(f"Error inesperado confirmando pago: {e}", exc_info=True)
            raise ValueError(f"Error inesperado procesando confirmación de pago: {str(e)}")

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

    async def _process_successful_payment(
        self,
        db: Session,
        participation: EventParticipation,
        event: Event,
        payment_intent: stripe.PaymentIntent
    ) -> EventParticipation:
        """
        Procesar pago exitoso y actualizar participación.

        Extraído como función helper para evitar duplicación de código
        entre los 3 niveles de fallback.

        Args:
            db: Sesión de base de datos
            participation: Participación a actualizar
            event: Evento asociado
            payment_intent: Payment Intent de Stripe con status='succeeded'

        Returns:
            Participación actualizada
        """
        logger.info(
            f"[Procesamiento] Confirmando pago para participación {participation.id} "
            f"con Payment Intent {payment_intent.id}"
        )

        # Actualizar estado de pago
        participation.payment_status = PaymentStatusType.PAID
        participation.stripe_payment_intent_id = payment_intent.id
        participation.amount_paid_cents = payment_intent.amount
        participation.payment_date = datetime.utcnow()

        # CRÍTICO: Promover de PENDING_PAYMENT a REGISTERED
        if participation.status == EventParticipationStatus.PENDING_PAYMENT:
            from sqlalchemy import func
            registered_count = db.query(func.count(EventParticipation.id)).filter(
                EventParticipation.event_id == event.id,
                EventParticipation.status == EventParticipationStatus.REGISTERED
            ).scalar()

            if event.max_participants > 0 and registered_count >= event.max_participants:
                # No hay capacidad, mover a lista de espera
                participation.status = EventParticipationStatus.WAITING_LIST
                logger.warning(
                    f"[Procesamiento] Participación {participation.id} movida a WAITING_LIST "
                    f"(capacidad llena: {registered_count}/{event.max_participants})"
                )
            else:
                # Hay capacidad, promover a REGISTERED
                participation.status = EventParticipationStatus.REGISTERED
                logger.info(
                    f"[Procesamiento] Participación {participation.id} promovida a REGISTERED "
                    f"(registrados: {registered_count + 1}/{event.max_participants or 'ilimitado'})"
                )

        db.commit()
        db.refresh(participation)

        logger.info(
            f"[Procesamiento] ✅ Pago confirmado exitosamente para participación {participation.id}"
        )

        return participation

    async def cancel_event_with_full_refunds(
        self,
        db: Session,
        event: Event,
        gym_id: int,
        cancelled_by_user_id: int,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cancelar un evento y procesar reembolsos automáticos del 100% para todos los participantes.

        Este método:
        - Reembolsa 100% a todos los participantes con payment_status=PAID (ignora políticas de reembolso)
        - Cancela Payment Intents pendientes (status=PENDING_PAYMENT)
        - Marca todas las participaciones como CANCELLED
        - Actualiza el evento con información de auditoría
        - Continúa procesando aunque algunos reembolsos fallen

        Args:
            db: Sesión de base de datos
            event: Evento a cancelar
            gym_id: ID del gimnasio
            cancelled_by_user_id: ID del usuario admin que cancela
            reason: Razón de la cancelación

        Returns:
            Diccionario con estadísticas de la cancelación:
            - participants_count: Total de participantes
            - refunds_processed: Reembolsos exitosos
            - refunds_failed: Reembolsos fallidos
            - payments_cancelled: Payment Intents cancelados
            - total_refunded_cents: Total reembolsado en centavos
            - failed_refunds: Lista de errores
        """
        try:
            logger.info(
                f"╔════════════════════════════════════════════════════════════════╗\n"
                f"║ INICIANDO CANCELACIÓN MASIVA DE EVENTO                        ║\n"
                f"╠════════════════════════════════════════════════════════════════╣\n"
                f"║ Evento ID: {event.id}\n"
                f"║ Título: {event.title}\n"
                f"║ Gym ID: {gym_id}\n"
                f"║ Es pago: {event.is_paid}\n"
                f"║ Precio: {event.price_cents/100 if event.price_cents else 0:.2f} {event.currency or 'EUR'}\n"
                f"║ Cancelado por User ID: {cancelled_by_user_id}\n"
                f"║ Razón: {reason or 'Sin razón especificada'}\n"
                f"╚════════════════════════════════════════════════════════════════╝"
            )

            # Obtener cuenta de Stripe del gimnasio
            stripe_account = db.query(GymStripeAccount).filter(
                GymStripeAccount.gym_id == gym_id
            ).first()

            if not stripe_account and event.is_paid:
                raise ValueError("No se encontró cuenta de Stripe para el gimnasio")

            # Obtener todas las participaciones activas del evento
            participations = db.query(EventParticipation).filter(
                and_(
                    EventParticipation.event_id == event.id,
                    EventParticipation.gym_id == gym_id,
                    EventParticipation.status.in_([
                        EventParticipationStatus.REGISTERED,
                        EventParticipationStatus.PENDING_PAYMENT,
                        EventParticipationStatus.WAITING_LIST
                    ])
                )
            ).all()

            # Estadísticas de procesamiento
            stats = {
                "participants_count": len(participations),
                "refunds_processed": 0,
                "refunds_failed": 0,
                "payments_cancelled": 0,
                "total_refunded_cents": 0,
                "failed_refunds": []
            }

            # Procesar cada participación
            for participation in participations:
                try:
                    # CASO 1: Participante ya pagó -> Reembolsar 100%
                    if participation.payment_status == PaymentStatusType.PAID:
                        if not participation.stripe_payment_intent_id:
                            logger.warning(
                                f"Participación {participation.id} marcada como PAID "
                                f"pero sin stripe_payment_intent_id"
                            )
                            stats["refunds_failed"] += 1
                            stats["failed_refunds"].append({
                                "participation_id": participation.id,
                                "member_id": participation.member_id,
                                "error": "Sin Payment Intent ID"
                            })
                            continue

                        # Reembolsar 100% del monto pagado
                        refund_amount = participation.amount_paid_cents or 0

                        if refund_amount > 0:
                            logger.info(
                                f"[Reembolso] Iniciando reembolso para participación {participation.id} - "
                                f"Member ID: {participation.member_id} - "
                                f"Payment Intent: {participation.stripe_payment_intent_id} - "
                                f"Monto: {refund_amount} centavos (€{refund_amount/100:.2f})"
                            )

                            try:
                                refund = stripe.Refund.create(
                                    payment_intent=participation.stripe_payment_intent_id,
                                    amount=refund_amount,  # 100% del monto
                                    reason="requested_by_customer",
                                    metadata={
                                        "event_id": str(event.id),
                                        "participation_id": str(participation.id),
                                        "refund_reason": reason or "Evento cancelado por administrador",
                                        "cancelled_by_user_id": str(cancelled_by_user_id)
                                    },
                                    stripe_account=stripe_account.stripe_account_id
                                )

                                # Actualizar participación
                                participation.payment_status = PaymentStatusType.REFUNDED
                                participation.refund_date = datetime.utcnow()
                                participation.refund_amount_cents = refund_amount
                                participation.status = EventParticipationStatus.CANCELLED

                                stats["refunds_processed"] += 1
                                stats["total_refunded_cents"] += refund_amount

                                logger.info(
                                    f"[Reembolso] ✅ EXITOSO - Refund ID: {refund.id} - "
                                    f"Participación: {participation.id} - "
                                    f"Member: {participation.member_id} - "
                                    f"Monto reembolsado: €{refund_amount/100:.2f} {event.currency or 'EUR'} - "
                                    f"Status: {refund.get('status', 'N/A')}"
                                )

                            except stripe.error.StripeError as e:
                                error_type = type(e).__name__
                                error_code = getattr(e, 'code', 'N/A')
                                error_message = str(e)

                                logger.error(
                                    f"[Reembolso] ❌ ERROR - Participación {participation.id} - "
                                    f"Member: {participation.member_id} - "
                                    f"Payment Intent: {participation.stripe_payment_intent_id} - "
                                    f"Error Type: {error_type} - "
                                    f"Error Code: {error_code} - "
                                    f"Message: {error_message}"
                                )

                                stats["refunds_failed"] += 1
                                stats["failed_refunds"].append({
                                    "participation_id": participation.id,
                                    "member_id": participation.member_id,
                                    "error": f"{error_type}: {error_message}",
                                    "error_code": error_code
                                })
                                # Continuar con otros reembolsos
                                continue
                        else:
                            logger.warning(
                                f"[Reembolso] ⚠️ Participación {participation.id} marcada como PAID "
                                f"pero con monto 0 o None - Saltando reembolso"
                            )

                    # CASO 2: Pago pendiente -> Cancelar Payment Intent
                    elif participation.status == EventParticipationStatus.PENDING_PAYMENT:
                        if participation.stripe_payment_intent_id:
                            logger.info(
                                f"[Cancelación PI] Cancelando Payment Intent pendiente - "
                                f"Participación: {participation.id} - "
                                f"Member: {participation.member_id} - "
                                f"Payment Intent: {participation.stripe_payment_intent_id}"
                            )

                            try:
                                # Cancelar Payment Intent en Stripe
                                cancelled_pi = stripe.PaymentIntent.cancel(
                                    participation.stripe_payment_intent_id,
                                    stripe_account=stripe_account.stripe_account_id
                                )

                                participation.payment_status = PaymentStatusType.EXPIRED
                                participation.status = EventParticipationStatus.CANCELLED

                                stats["payments_cancelled"] += 1

                                logger.info(
                                    f"[Cancelación PI] ✅ EXITOSO - Payment Intent cancelado - "
                                    f"PI ID: {participation.stripe_payment_intent_id} - "
                                    f"Participación: {participation.id} - "
                                    f"Member: {participation.member_id} - "
                                    f"Status: {cancelled_pi.get('status', 'N/A')}"
                                )

                            except stripe.error.StripeError as e:
                                error_type = type(e).__name__
                                error_code = getattr(e, 'code', 'N/A')

                                logger.warning(
                                    f"[Cancelación PI] ⚠️ ERROR (continuando) - "
                                    f"Participación {participation.id} - "
                                    f"Member: {participation.member_id} - "
                                    f"Payment Intent: {participation.stripe_payment_intent_id} - "
                                    f"Error Type: {error_type} - "
                                    f"Error Code: {error_code} - "
                                    f"Message: {str(e)}"
                                )
                                # Marcar como cancelado de todas formas
                                participation.status = EventParticipationStatus.CANCELLED
                                participation.payment_status = PaymentStatusType.EXPIRED

                                logger.info(
                                    f"[Cancelación PI] Participación {participation.id} marcada como "
                                    f"CANCELLED/EXPIRED a pesar del error"
                                )
                        else:
                            # Sin Payment Intent, solo marcar como cancelado
                            logger.info(
                                f"[Cancelación PI] Participación {participation.id} (Member: {participation.member_id}) "
                                f"sin Payment Intent - Marcando como CANCELLED/EXPIRED"
                            )
                            participation.status = EventParticipationStatus.CANCELLED
                            participation.payment_status = PaymentStatusType.EXPIRED

                    # CASO 3: Participante sin pago (evento gratuito o waiting list)
                    else:
                        logger.info(
                            f"[Cancelación] Participación {participation.id} (Member: {participation.member_id}) - "
                            f"Status: {participation.status.value} - Sin pago - Marcando como CANCELLED"
                        )
                        participation.status = EventParticipationStatus.CANCELLED

                except Exception as e:
                    logger.error(f"Error procesando participación {participation.id}: {e}")
                    stats["failed_refunds"].append({
                        "participation_id": participation.id,
                        "member_id": participation.member_id,
                        "error": str(e)
                    })
                    continue

            # Actualizar evento con información de auditoría
            from app.models.event import EventStatus
            event.status = EventStatus.CANCELLED
            event.cancellation_date = datetime.utcnow()
            event.cancelled_by_user_id = cancelled_by_user_id
            event.cancellation_reason = reason
            event.total_refunded_cents = stats["total_refunded_cents"]

            # Commit de todos los cambios
            db.commit()

            # Calcular totales para el resumen
            total_refunded_amount = stats["total_refunded_cents"] / 100
            success_rate = (
                (stats["refunds_processed"] / (stats["refunds_processed"] + stats["refunds_failed"]) * 100)
                if (stats["refunds_processed"] + stats["refunds_failed"]) > 0
                else 100
            )

            logger.info(
                f"\n╔════════════════════════════════════════════════════════════════╗\n"
                f"║ CANCELACIÓN DE EVENTO COMPLETADA                              ║\n"
                f"╠════════════════════════════════════════════════════════════════╣\n"
                f"║ Evento ID: {event.id} - {event.title}\n"
                f"║ \n"
                f"║ 📊 RESUMEN DE PARTICIPANTES:\n"
                f"║   • Total participantes procesados: {stats['participants_count']}\n"
                f"║ \n"
                f"║ 💰 REEMBOLSOS:\n"
                f"║   • ✅ Exitosos: {stats['refunds_processed']}\n"
                f"║   • ❌ Fallidos: {stats['refunds_failed']}\n"
                f"║   • Tasa de éxito: {success_rate:.1f}%\n"
                f"║   • Total reembolsado: €{total_refunded_amount:.2f} {event.currency or 'EUR'}\n"
                f"║ \n"
                f"║ 🚫 PAYMENT INTENTS CANCELADOS:\n"
                f"║   • Pagos pendientes cancelados: {stats['payments_cancelled']}\n"
                f"║ \n"
                f"║ 📝 AUDITORÍA:\n"
                f"║   • Cancelado por User ID: {cancelled_by_user_id}\n"
                f"║   • Fecha: {event.cancellation_date}\n"
                f"║   • Razón: {reason or 'Sin razón especificada'}\n"
                f"╚════════════════════════════════════════════════════════════════╝"
            )

            # Log de errores detallados si los hay
            if stats["refunds_failed"] > 0:
                logger.warning(
                    f"\n⚠️ ERRORES DE REEMBOLSO DETALLADOS ({stats['refunds_failed']} fallos):\n" +
                    "\n".join([
                        f"  • Participación {err['participation_id']} (Member {err['member_id']}): "
                        f"{err.get('error', 'Error desconocido')}"
                        for err in stats["failed_refunds"]
                    ])
                )

            return stats

        except Exception as e:
            logger.error(f"Error en cancelación masiva de evento {event.id}: {e}")
            db.rollback()
            raise


# Instancia global del servicio
event_payment_service = EventPaymentService()