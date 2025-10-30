#!/usr/bin/env python
"""
Script para verificar y sincronizar pagos pendientes de eventos.

Este script revisa todos los pagos en estado PENDING y verifica su estado real
en Stripe, actualizando la base de datos si es necesario.
"""

import os
import sys
import logging
from datetime import datetime, timedelta

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.event import EventParticipation, Event, PaymentStatusType
from app.core.config import get_settings
import stripe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurar Stripe
settings = get_settings()
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY
else:
    logger.error("STRIPE_SECRET_KEY no configurada")
    sys.exit(1)


def check_single_participation(participation_id: int, fix: bool = False):
    """
    Verificar una participación específica.

    Args:
        participation_id: ID de la participación
        fix: Si True, actualiza el estado si hay inconsistencia
    """
    db = SessionLocal()
    try:
        # Obtener participación y evento
        participation = db.query(EventParticipation).filter(
            EventParticipation.id == participation_id
        ).first()

        if not participation:
            logger.error(f"Participación {participation_id} no encontrada")
            return

        event = db.query(Event).filter(Event.id == participation.event_id).first()

        logger.info("=" * 60)
        logger.info(f"Participación ID: {participation.id}")
        logger.info(f"Evento: {event.title if event else 'No encontrado'}")
        logger.info(f"Usuario ID: {participation.member_id}")
        logger.info(f"Estado en BD: {participation.payment_status}")
        logger.info(f"Payment Intent ID: {participation.stripe_payment_intent_id}")
        logger.info(f"Fecha registro: {participation.registered_at}")

        if not participation.stripe_payment_intent_id:
            logger.warning("No hay Payment Intent asociado")
            return

        # Verificar en Stripe
        try:
            # Intentar obtener el Payment Intent
            payment_intent = stripe.PaymentIntent.retrieve(
                participation.stripe_payment_intent_id
            )

            logger.info(f"\n📊 Estado en Stripe:")
            logger.info(f"  - Status: {payment_intent.status}")
            logger.info(f"  - Monto: {payment_intent.amount / 100:.2f} {payment_intent.currency.upper()}")
            logger.info(f"  - Creado: {datetime.fromtimestamp(payment_intent.created)}")

            # Analizar el estado
            if payment_intent.status == "succeeded":
                if participation.payment_status != PaymentStatusType.PAID:
                    logger.warning("⚠️ INCONSISTENCIA: Pagado en Stripe pero no en BD")

                    if fix:
                        logger.info("🔧 Actualizando BD...")
                        participation.payment_status = PaymentStatusType.PAID
                        participation.amount_paid_cents = payment_intent.amount
                        participation.payment_date = datetime.utcnow()
                        db.commit()
                        logger.info("✅ Actualizado a PAID")
                    else:
                        logger.info("ℹ️ Usa --fix para actualizar")
                else:
                    logger.info("✅ Estado consistente: PAID en ambos sistemas")

            elif payment_intent.status == "canceled":
                if participation.payment_status not in [PaymentStatusType.EXPIRED, PaymentStatusType.REFUNDED]:
                    logger.warning("⚠️ Payment Intent cancelado pero BD muestra PENDING")

                    if fix:
                        logger.info("🔧 Actualizando BD a EXPIRED...")
                        participation.payment_status = PaymentStatusType.EXPIRED
                        db.commit()
                        logger.info("✅ Actualizado a EXPIRED")

            elif payment_intent.status == "requires_payment_method":
                logger.info("⏳ Esperando método de pago del usuario")

                # Verificar si ha expirado (más de 24 horas)
                created_time = datetime.fromtimestamp(payment_intent.created)
                if datetime.utcnow() - created_time > timedelta(hours=24):
                    logger.warning("⚠️ Payment Intent tiene más de 24 horas")

                    if fix:
                        logger.info("🔧 Marcando como EXPIRED...")
                        participation.payment_status = PaymentStatusType.EXPIRED
                        db.commit()
                        # Cancelar en Stripe también
                        stripe.PaymentIntent.cancel(participation.stripe_payment_intent_id)
                        logger.info("✅ Marcado como EXPIRED y cancelado en Stripe")

            elif payment_intent.status == "requires_confirmation":
                logger.warning("⚠️ Payment Intent requiere confirmación")

            elif payment_intent.status == "processing":
                logger.info("🔄 Pago en procesamiento")

            else:
                logger.warning(f"❓ Estado desconocido: {payment_intent.status}")

            # Mostrar última actividad
            if payment_intent.charges and payment_intent.charges.data:
                last_charge = payment_intent.charges.data[0]
                logger.info(f"\n💳 Último intento de cargo:")
                logger.info(f"  - Estado: {last_charge.status}")
                logger.info(f"  - Fecha: {datetime.fromtimestamp(last_charge.created)}")
                if last_charge.failure_message:
                    logger.info(f"  - Error: {last_charge.failure_message}")

        except stripe.error.InvalidRequestError as e:
            logger.error(f"❌ Payment Intent no encontrado en Stripe: {e}")
            if fix:
                logger.info("🔧 Marcando como EXPIRED en BD...")
                participation.payment_status = PaymentStatusType.EXPIRED
                db.commit()

        except stripe.error.StripeError as e:
            logger.error(f"❌ Error de Stripe: {e}")

    except Exception as e:
        logger.error(f"Error procesando participación: {e}")
    finally:
        db.close()


def check_all_pending_payments(gym_id: int = None, fix: bool = False):
    """
    Verificar todos los pagos pendientes.

    Args:
        gym_id: Filtrar por gimnasio (opcional)
        fix: Si True, actualiza estados inconsistentes
    """
    db = SessionLocal()
    try:
        query = db.query(EventParticipation).filter(
            EventParticipation.payment_status == PaymentStatusType.PENDING
        )

        if gym_id:
            query = query.filter(EventParticipation.gym_id == gym_id)

        pending_participations = query.all()

        logger.info(f"\n🔍 Encontradas {len(pending_participations)} participaciones pendientes")

        for participation in pending_participations:
            check_single_participation(participation.id, fix=fix)
            logger.info("-" * 60)

        logger.info(f"\n✅ Verificación completada")

    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        db.close()


def check_duplicate_payment_intents(gym_id: int = None):
    """
    Detectar Payment Intents duplicados para el mismo evento.

    Args:
        gym_id: Filtrar por gimnasio (opcional)
    """
    db = SessionLocal()
    try:
        # Buscar todas las participaciones de eventos con Payment Intents
        query = db.query(EventParticipation).filter(
            EventParticipation.stripe_payment_intent_id.isnot(None)
        )

        if gym_id:
            query = query.filter(EventParticipation.gym_id == gym_id)

        participations = query.all()

        logger.info(f"\n🔍 Verificando duplicados en {len(participations)} participaciones con Payment Intents")

        # Agrupar por evento
        events_dict = {}
        for participation in participations:
            if participation.event_id not in events_dict:
                events_dict[participation.event_id] = []
            events_dict[participation.event_id].append(participation)

        # Buscar duplicados
        duplicates_found = False
        for event_id, parts in events_dict.items():
            # Agrupar por usuario
            user_parts = {}
            for part in parts:
                if part.member_id not in user_parts:
                    user_parts[part.member_id] = []
                user_parts[part.member_id].append(part)

            # Verificar si algún usuario tiene múltiples participaciones
            for user_id, user_participations in user_parts.items():
                if len(user_participations) > 1:
                    duplicates_found = True
                    logger.warning(f"\n⚠️  DUPLICADO DETECTADO:")
                    logger.warning(f"   Evento ID: {event_id}, Usuario ID: {user_id}")
                    logger.warning(f"   Participaciones: {len(user_participations)}")

                    for part in user_participations:
                        logger.warning(
                            f"     - Part ID: {part.id}, "
                            f"Estado: {part.status}, "
                            f"Pago: {part.payment_status}, "
                            f"PI: {part.stripe_payment_intent_id}"
                        )

        if not duplicates_found:
            logger.info("✅ No se encontraron duplicados")

        # Buscar Payment Intents múltiples en Stripe para eventos
        logger.info("\n🔍 Buscando Payment Intents en Stripe para eventos...")

        # Obtener todos los Payment Intents únicos
        all_payment_intents = set()
        event_metadata = {}

        for participation in participations:
            if participation.stripe_payment_intent_id:
                all_payment_intents.add(participation.stripe_payment_intent_id)

                if participation.event_id not in event_metadata:
                    event = db.query(Event).filter(Event.id == participation.event_id).first()
                    event_metadata[participation.event_id] = {
                        'title': event.title if event else 'Unknown',
                        'gym_id': participation.gym_id,
                        'payment_intents': []
                    }

                event_metadata[participation.event_id]['payment_intents'].append({
                    'pi_id': participation.stripe_payment_intent_id,
                    'participation_id': participation.id,
                    'member_id': participation.member_id
                })

        logger.info(f"📊 Resumen por evento:")
        for event_id, metadata in event_metadata.items():
            pi_count = len(metadata['payment_intents'])
            logger.info(f"\nEvento ID {event_id}: {metadata['title']}")
            logger.info(f"  Total Payment Intents: {pi_count}")

            if pi_count > 5:  # Umbral arbitrario para detectar posible problema
                logger.warning(f"  ⚠️ Muchos Payment Intents para este evento")

            # Mostrar detalles de cada Payment Intent
            for pi_data in metadata['payment_intents']:
                logger.info(
                    f"    - PI: {pi_data['pi_id']}, "
                    f"Part: {pi_data['participation_id']}, "
                    f"User: {pi_data['member_id']}"
                )

        logger.info(f"\n✅ Verificación de duplicados completada")

    except Exception as e:
        logger.error(f"Error verificando duplicados: {e}")
    finally:
        db.close()


def main():
    """Función principal del script."""
    import argparse

    parser = argparse.ArgumentParser(description='Verificar pagos pendientes de eventos')
    parser.add_argument(
        '--participation-id',
        type=int,
        help='ID de participación específica a verificar'
    )
    parser.add_argument(
        '--gym-id',
        type=int,
        help='Filtrar por ID de gimnasio'
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Actualizar estados inconsistentes automáticamente'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Verificar todos los pagos pendientes'
    )
    parser.add_argument(
        '--check-duplicates',
        action='store_true',
        help='Verificar Payment Intents duplicados'
    )

    args = parser.parse_args()

    logger.info("🚀 Iniciando verificación de pagos pendientes de eventos\n")

    if args.participation_id:
        check_single_participation(args.participation_id, fix=args.fix)
    elif args.all:
        check_all_pending_payments(gym_id=args.gym_id, fix=args.fix)
    elif args.check_duplicates:
        check_duplicate_payment_intents(gym_id=args.gym_id)
    else:
        logger.error("Debe especificar --participation-id, --all o --check-duplicates")
        parser.print_help()


if __name__ == "__main__":
    main()