"""
Script de prueba para verificar el flujo de cancelación con reembolsos.

Simula la cancelación del evento 652 que tiene:
- 1 participación PAGADA ($13 USD)
- 1 participación PENDIENTE

Esto probará:
1. Reembolso 100% automático
2. Cancelación de Payment Intent pendiente
3. Actualización de campos de auditoría
4. Logs detallados del proceso

Uso:
    python scripts/test_event_652_cancellation.py
"""

import os
import sys
import asyncio
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.event import Event
from app.services.event_payment_service import EventPaymentService
from app.db.session import SessionLocal

# Cargar variables de entorno
load_dotenv()


async def test_cancellation():
    """Probar cancelación del evento 652."""

    print("=" * 100)
    print("PRUEBA DE CANCELACIÓN DE EVENTO CON REEMBOLSOS AUTOMÁTICOS")
    print("=" * 100)
    print()

    db = SessionLocal()

    try:
        # Obtener evento 652
        event = db.query(Event).filter(Event.id == 652).first()

        if not event:
            print("❌ ERROR: Evento 652 no encontrado")
            return

        print(f"📋 EVENTO A CANCELAR:")
        print(f"   ID: {event.id}")
        print(f"   Título: {event.title}")
        print(f"   Precio: ${event.price_cents/100:.2f} {event.currency}")
        print(f"   Estado actual: {event.status}")
        print(f"   is_paid: {event.is_paid}")
        print()

        # Verificar participaciones
        from app.models.event import EventParticipation
        participations = db.query(EventParticipation).filter(
            EventParticipation.event_id == event.id
        ).all()

        print(f"📊 PARTICIPACIONES ({len(participations)} total):")
        for p in participations:
            amount = (p.amount_paid_cents or 0) / 100
            print(f"   • ID {p.id} - Member {p.member_id} - Status: {p.status} - Payment: {p.payment_status} - PI: {p.stripe_payment_intent_id or 'N/A'} - Pagado: ${amount:.2f}")
        print()

        # Confirmar antes de cancelar
        response = input("⚠️  ¿Proceder con la cancelación y reembolsos? (yes/no): ")

        if response.lower() not in ['yes', 'y', 'si', 's']:
            print("❌ Operación cancelada por el usuario")
            return

        print()
        print("🚀 Iniciando cancelación con reembolsos automáticos...")
        print()

        # Ejecutar cancelación
        payment_service = EventPaymentService()

        result = await payment_service.cancel_event_with_full_refunds(
            db=db,
            event=event,
            gym_id=event.gym_id,
            cancelled_by_user_id=1,  # User ID del admin
            reason="Prueba de sistema de reembolsos automáticos"
        )

        print()
        print("=" * 100)
        print("✅ RESULTADO DE LA CANCELACIÓN:")
        print("=" * 100)
        print(f"   Total participaciones: {result['total_participations']}")
        print(f"   Reembolsos procesados: {result['refunds_processed']}")
        print(f"   Reembolsos fallidos: {result['refunds_failed']}")
        print(f"   Pagos cancelados: {result['payments_cancelled']}")
        print(f"   Total reembolsado: ${result['total_refunded_cents']/100:.2f} {result['currency']}")
        print()

        if result['failed_refunds']:
            print("⚠️  REEMBOLSOS FALLIDOS:")
            for failed in result['failed_refunds']:
                print(f"   • Participación {failed['participation_id']}: {failed['error']}")
            print()

        # Verificar evento actualizado
        db.refresh(event)
        print("📝 AUDITORÍA DEL EVENTO:")
        print(f"   Estado: {event.status}")
        print(f"   Fecha cancelación: {event.cancellation_date}")
        print(f"   Cancelado por user_id: {event.cancelled_by_user_id}")
        print(f"   Razón: {event.cancellation_reason}")
        print(f"   Total reembolsado: ${(event.total_refunded_cents or 0)/100:.2f}")
        print()

        # Verificar participaciones actualizadas
        db.expire_all()
        participations = db.query(EventParticipation).filter(
            EventParticipation.event_id == event.id
        ).all()

        print("📊 PARTICIPACIONES ACTUALIZADAS:")
        for p in participations:
            refund = (p.refund_amount_cents or 0) / 100
            print(f"   • ID {p.id} - Status: {p.status} - Payment: {p.payment_status} - Reembolsado: ${refund:.2f}")

        print()
        print("=" * 100)
        print("🎉 PRUEBA COMPLETADA EXITOSAMENTE")
        print("=" * 100)

    except Exception as e:
        print(f"\n❌ ERROR durante la prueba: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_cancellation())
