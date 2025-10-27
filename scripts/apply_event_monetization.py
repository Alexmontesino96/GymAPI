#!/usr/bin/env python
"""
Script para aplicar cambios de monetización de eventos directamente en la BD.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def apply_monetization_changes():
    """Aplicar cambios de monetización a la BD."""
    db = SessionLocal()

    try:
        # Crear enums si no existen
        logger.info("Creando enums...")
        try:
            db.execute(text("""
                CREATE TYPE refundpolicytype AS ENUM (
                    'NO_REFUND', 'FULL_REFUND', 'PARTIAL_REFUND', 'CREDIT'
                )
            """))
            db.commit()
            logger.info("✓ Enum refundpolicytype creado")
        except Exception as e:
            db.rollback()
            logger.warning(f"Enum refundpolicytype ya existe o error: {e}")

        try:
            db.execute(text("""
                CREATE TYPE paymentstatustype AS ENUM (
                    'PENDING', 'PAID', 'REFUNDED', 'CREDITED', 'EXPIRED'
                )
            """))
            db.commit()
            logger.info("✓ Enum paymentstatustype creado")
        except Exception as e:
            db.rollback()
            logger.warning(f"Enum paymentstatustype ya existe o error: {e}")

        # Agregar columnas a events
        logger.info("\nAgregando columnas a tabla events...")
        columns_events = [
            ("is_paid", "BOOLEAN DEFAULT false NOT NULL"),
            ("price_cents", "INTEGER"),
            ("currency", "VARCHAR(3) DEFAULT 'EUR'"),
            ("refund_policy", "refundpolicytype"),
            ("refund_deadline_hours", "INTEGER DEFAULT 24"),
            ("partial_refund_percentage", "INTEGER DEFAULT 50"),
            ("stripe_product_id", "VARCHAR(255)"),
            ("stripe_price_id", "VARCHAR(255)")
        ]

        for col_name, col_type in columns_events:
            try:
                db.execute(text(f"ALTER TABLE events ADD COLUMN {col_name} {col_type}"))
                db.commit()
                logger.info(f"✓ Columna {col_name} agregada a events")
            except Exception as e:
                db.rollback()
                logger.warning(f"Columna {col_name} ya existe o error: {e}")

        # Agregar columnas a event_participations
        logger.info("\nAgregando columnas a tabla event_participations...")
        columns_participations = [
            ("payment_status", "paymentstatustype"),
            ("stripe_payment_intent_id", "VARCHAR(255)"),
            ("amount_paid_cents", "INTEGER"),
            ("payment_date", "TIMESTAMP WITH TIME ZONE"),
            ("refund_date", "TIMESTAMP WITH TIME ZONE"),
            ("refund_amount_cents", "INTEGER"),
            ("payment_expiry", "TIMESTAMP WITH TIME ZONE")
        ]

        for col_name, col_type in columns_participations:
            try:
                db.execute(text(f"ALTER TABLE event_participations ADD COLUMN {col_name} {col_type}"))
                db.commit()
                logger.info(f"✓ Columna {col_name} agregada a event_participations")
            except Exception as e:
                db.rollback()
                logger.warning(f"Columna {col_name} ya existe o error: {e}")

        # Crear índices
        logger.info("\nCreando índices...")
        indices = [
            ("ix_events_is_paid", "events", "is_paid"),
            ("ix_events_stripe_product_id", "events", "stripe_product_id"),
            ("ix_events_stripe_price_id", "events", "stripe_price_id"),
            ("ix_event_participations_payment_status", "event_participations", "payment_status"),
            ("ix_event_participations_stripe_payment_intent_id", "event_participations", "stripe_payment_intent_id")
        ]

        for idx_name, table_name, col_name in indices:
            try:
                db.execute(text(f"CREATE INDEX {idx_name} ON {table_name}({col_name})"))
                db.commit()
                logger.info(f"✓ Índice {idx_name} creado")
            except Exception as e:
                db.rollback()
                logger.warning(f"Índice {idx_name} ya existe o error: {e}")

        logger.info("\n✅ Cambios de monetización aplicados exitosamente")

    except Exception as e:
        logger.error(f"Error aplicando cambios: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    apply_monetization_changes()