#!/usr/bin/env python
"""
Script para probar los webhooks de monetización de eventos.

Este script simula eventos de webhook de Stripe para verificar que los handlers
de eventos de pago funcionen correctamente.
"""

import os
import sys
import json
import hmac
import hashlib
import time
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.services.stripe_service import stripe_service
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_stripe_signature(payload: str, secret: str) -> str:
    """
    Generar una firma de Stripe válida para testing.

    Args:
        payload: El payload JSON como string
        secret: El webhook secret de Stripe

    Returns:
        str: Firma formateada como Stripe la enviaría
    """
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload}"

    # Generar signature usando HMAC-SHA256
    signature = hmac.new(
        secret.encode('utf-8'),
        signed_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return f"t={timestamp},v1={signature}"


async def test_payment_intent_succeeded():
    """Probar webhook de pago exitoso de evento."""
    logger.info("=== Probando payment_intent.succeeded ===")

    # Simular payload de Stripe
    event = {
        "id": "evt_test_123",
        "type": "payment_intent.succeeded",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": "pi_test_event_123",
                "amount": 4999,  # €49.99
                "currency": "eur",
                "status": "succeeded",
                "metadata": {
                    "event_id": "1",
                    "user_id": "1",
                    "gym_id": "1",
                    "event_title": "Workshop de Nutrición"
                },
                "created": int(time.time()),
                "customer": "cus_test_123"
            }
        }
    }

    payload = json.dumps(event)
    settings = get_settings()

    # Solo procesar si hay webhook secret configurado
    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET no configurado - saltando prueba de firma")
        # Procesar sin verificación de firma (solo para testing)
        result = await stripe_service._handle_event_payment_succeeded(event["data"]["object"])
        logger.info(f"Resultado (sin verificación): {result}")
    else:
        signature = generate_stripe_signature(payload, settings.STRIPE_WEBHOOK_SECRET)
        result = await stripe_service.handle_webhook(payload.encode(), signature)
        logger.info(f"Resultado: {result}")

    logger.info("✅ Test payment_intent.succeeded completado\n")


async def test_payment_intent_canceled():
    """Probar webhook de pago cancelado/expirado."""
    logger.info("=== Probando payment_intent.canceled ===")

    event = {
        "id": "evt_test_456",
        "type": "payment_intent.canceled",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": "pi_test_event_456",
                "amount": 4999,
                "currency": "eur",
                "status": "canceled",
                "metadata": {
                    "event_id": "2",
                    "user_id": "2",
                    "gym_id": "1"
                },
                "cancellation_reason": "abandoned"
            }
        }
    }

    payload = json.dumps(event)
    settings = get_settings()

    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET no configurado - procesando directamente")
        result = await stripe_service._handle_event_payment_canceled(event["data"]["object"])
    else:
        signature = generate_stripe_signature(payload, settings.STRIPE_WEBHOOK_SECRET)
        result = await stripe_service.handle_webhook(payload.encode(), signature)

    logger.info(f"Resultado: {result}")
    logger.info("✅ Test payment_intent.canceled completado\n")


async def test_charge_refunded():
    """Probar webhook de reembolso procesado."""
    logger.info("=== Probando charge.refunded ===")

    event = {
        "id": "evt_test_789",
        "type": "charge.refunded",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": "ch_test_123",
                "amount": 4999,
                "amount_refunded": 4999,  # Reembolso completo
                "currency": "eur",
                "refunded": True,
                "payment_intent": "pi_test_event_789",
                "metadata": {
                    "event_id": "3",
                    "user_id": "3",
                    "gym_id": "1"
                },
                "refunds": {
                    "data": [{
                        "id": "re_test_123",
                        "amount": 4999,
                        "reason": "requested_by_customer",
                        "created": int(time.time())
                    }]
                }
            }
        }
    }

    payload = json.dumps(event)
    settings = get_settings()

    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET no configurado - procesando directamente")
        result = await stripe_service._handle_event_refund_processed(event["data"]["object"])
    else:
        signature = generate_stripe_signature(payload, settings.STRIPE_WEBHOOK_SECRET)
        result = await stripe_service.handle_webhook(payload.encode(), signature)

    logger.info(f"Resultado: {result}")
    logger.info("✅ Test charge.refunded completado\n")


async def test_payment_requires_method():
    """Probar webhook cuando se requiere nuevo método de pago."""
    logger.info("=== Probando payment_intent.requires_payment_method ===")

    event = {
        "id": "evt_test_999",
        "type": "payment_intent.requires_payment_method",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": "pi_test_event_999",
                "amount": 4999,
                "currency": "eur",
                "status": "requires_payment_method",
                "metadata": {
                    "event_id": "4",
                    "user_id": "4",
                    "gym_id": "1"
                },
                "last_payment_error": {
                    "code": "card_declined",
                    "decline_code": "insufficient_funds",
                    "message": "Your card has insufficient funds."
                }
            }
        }
    }

    payload = json.dumps(event)
    settings = get_settings()

    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET no configurado - procesando directamente")
        result = await stripe_service._handle_event_payment_requires_method(event["data"]["object"])
    else:
        signature = generate_stripe_signature(payload, settings.STRIPE_WEBHOOK_SECRET)
        result = await stripe_service.handle_webhook(payload.encode(), signature)

    logger.info(f"Resultado: {result}")
    logger.info("✅ Test payment_intent.requires_payment_method completado\n")


async def main():
    """Ejecutar todas las pruebas de webhooks."""
    logger.info("🚀 Iniciando pruebas de webhooks de monetización de eventos\n")

    try:
        # Probar cada tipo de evento
        await test_payment_intent_succeeded()
        await test_payment_intent_canceled()
        await test_charge_refunded()
        await test_payment_requires_method()

        logger.info("✅ Todas las pruebas completadas exitosamente")

    except Exception as e:
        logger.error(f"❌ Error durante las pruebas: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())