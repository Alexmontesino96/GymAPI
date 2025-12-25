"""
Script de diagnóstico para cuentas de Stripe Connect de gimnasios.

Detecta y repara automáticamente cuentas desconectadas o inactivas.

Uso:
    python scripts/diagnose_gym_stripe_account.py --gym-id 4
    python scripts/diagnose_gym_stripe_account.py --gym-id 4 --auto-repair
"""
import os
import sys
import argparse
import json
from datetime import datetime
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

import stripe
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
stripe.api_key = settings.STRIPE_SECRET_KEY

# Crear engine y session directamente para evitar problemas de imports
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def diagnose_gym_stripe_account(gym_id: int, auto_repair: bool = False) -> dict:
    """
    Diagnosticar y opcionalmente reparar cuenta de Stripe de un gym.

    Args:
        gym_id: ID del gimnasio a diagnosticar
        auto_repair: Si es True, repara automáticamente problemas detectados

    Returns:
        Diccionario con reporte de diagnóstico
    """
    db = SessionLocal()

    try:
        print(f"\n{'='*70}")
        print(f"DIAGNÓSTICO DE CUENTA STRIPE - GYM ID: {gym_id}")
        print(f"{'='*70}\n")

        # 1. Consultar BD usando SQL directo
        print("📋 PASO 1: Consultando base de datos...")

        result = db.execute(
            text("""
                SELECT id, gym_id, stripe_account_id, account_type, is_active,
                       charges_enabled, payouts_enabled, onboarding_completed,
                       country, default_currency, created_at, updated_at
                FROM gym_stripe_accounts
                WHERE gym_id = :gym_id
                LIMIT 1
            """),
            {"gym_id": gym_id}
        ).fetchone()

        if not result:
            gym_account = None
        else:
            # Crear objeto simple con los datos
            class GymAccount:
                def __init__(self, row):
                    self.id = row[0]
                    self.gym_id = row[1]
                    self.stripe_account_id = row[2]
                    self.account_type = row[3]
                    self.is_active = row[4]
                    self.charges_enabled = row[5]
                    self.payouts_enabled = row[6]
                    self.onboarding_completed = row[7]
                    self.country = row[8]
                    self.default_currency = row[9]
                    self.created_at = row[10]
                    self.updated_at = row[11]

            gym_account = GymAccount(result)

        if not gym_account:
            report = {
                "gym_id": gym_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "ERROR",
                "message": "No se encontró cuenta de Stripe en BD",
                "action_required": [
                    "❌ El gimnasio no tiene cuenta de Stripe configurada",
                    "",
                    "📝 SOLUCIÓN:",
                    "1. Crear cuenta: POST /api/v1/stripe-connect/accounts",
                    "2. Completar onboarding: POST /api/v1/stripe-connect/accounts/onboarding-link"
                ]
            }
            print("❌ No se encontró cuenta de Stripe en la base de datos\n")
            return report

        print("✅ Cuenta encontrada en BD\n")

        # Datos de la BD
        status_bd = {
            "account_id": gym_account.stripe_account_id,
            "account_type": gym_account.account_type,
            "is_active": gym_account.is_active,
            "charges_enabled": gym_account.charges_enabled,
            "payouts_enabled": gym_account.payouts_enabled,
            "onboarding_completed": gym_account.onboarding_completed,
            "country": gym_account.country,
            "currency": gym_account.default_currency,
            "created_at": gym_account.created_at.isoformat(),
            "updated_at": gym_account.updated_at.isoformat()
        }

        print("📊 ESTADO EN BASE DE DATOS:")
        print(f"   Account ID: {status_bd['account_id']}")
        print(f"   Tipo: {status_bd['account_type']}")
        print(f"   Activa: {'✅ Sí' if status_bd['is_active'] else '❌ No'}")
        print(f"   Charges habilitados: {'✅ Sí' if status_bd['charges_enabled'] else '❌ No'}")
        print(f"   Payouts habilitados: {'✅ Sí' if status_bd['payouts_enabled'] else '❌ No'}")
        print(f"   Onboarding completado: {'✅ Sí' if status_bd['onboarding_completed'] else '❌ No'}")
        print()

        # 2. Verificar en Stripe
        print("🔍 PASO 2: Verificando en Stripe API...")

        report = {
            "gym_id": gym_id,
            "timestamp": datetime.utcnow().isoformat(),
            "status_bd": status_bd,
            "discrepancies": [],
            "auto_repaired": False,
            "repair_actions": []
        }

        # Detectar cuenta placeholder
        if gym_account.stripe_account_id.startswith("placeholder_"):
            print("⚠️  CUENTA PLACEHOLDER DETECTADA\n")
            report["status"] = "WARNING"
            report["status_stripe"] = {
                "exists": False,
                "error": "Cuenta placeholder - nunca se creó en Stripe"
            }
            report["discrepancies"].append("Cuenta placeholder que nunca se migró a Stripe real")
            report["action_required"] = [
                "⚠️  Cuenta placeholder detectada",
                "",
                "📝 SOLUCIÓN:",
                "1. Crear cuenta real: POST /api/v1/stripe-connect/accounts",
                "2. Completar onboarding: POST /api/v1/stripe-connect/accounts/onboarding-link"
            ]
            return report

        try:
            # Intentar recuperar cuenta de Stripe
            stripe_account = stripe.Account.retrieve(gym_account.stripe_account_id)

            print("✅ Cuenta existe en Stripe\n")

            status_stripe = {
                "exists": True,
                "charges_enabled": stripe_account.charges_enabled,
                "payouts_enabled": stripe_account.payouts_enabled,
                "details_submitted": stripe_account.details_submitted,
                "type": stripe_account.type
            }

            report["status_stripe"] = status_stripe

            print("📊 ESTADO EN STRIPE:")
            print(f"   Charges habilitados: {'✅ Sí' if status_stripe['charges_enabled'] else '❌ No'}")
            print(f"   Payouts habilitados: {'✅ Sí' if status_stripe['payouts_enabled'] else '❌ No'}")
            print(f"   Detalles enviados: {'✅ Sí' if status_stripe['details_submitted'] else '❌ No'}")
            print(f"   Tipo: {status_stripe['type']}")
            print()

            # 3. Detectar discrepancias
            print("🔎 PASO 3: Detectando discrepancias...")

            # Discrepancia 1: BD dice activa pero Stripe dice charges_enabled=False
            if gym_account.is_active and not stripe_account.charges_enabled:
                discrepancy = "BD marca is_active=True pero Stripe tiene charges_enabled=False"
                report["discrepancies"].append(discrepancy)
                print(f"⚠️  {discrepancy}")

                if auto_repair:
                    db.execute(
                        text("""
                            UPDATE gym_stripe_accounts
                            SET is_active = false, charges_enabled = false, updated_at = NOW()
                            WHERE gym_id = :gym_id
                        """),
                        {"gym_id": gym_id}
                    )
                    report["repair_actions"].append("Marcada is_active=False en BD")
                    print("   🔧 AUTO-REPARADO: Marcada como inactiva")

            # Discrepancia 2: BD dice charges_enabled pero Stripe dice False
            if gym_account.charges_enabled and not stripe_account.charges_enabled:
                discrepancy = "BD marca charges_enabled=True pero Stripe tiene charges_enabled=False"
                report["discrepancies"].append(discrepancy)
                print(f"⚠️  {discrepancy}")

                if auto_repair:
                    db.execute(
                        text("UPDATE gym_stripe_accounts SET charges_enabled = false, updated_at = NOW() WHERE gym_id = :gym_id"),
                        {"gym_id": gym_id}
                    )
                    report["repair_actions"].append("Marcada charges_enabled=False en BD")
                    print("   🔧 AUTO-REPARADO: charges_enabled actualizado")

            # Discrepancia 3: BD dice payouts_enabled pero Stripe dice False
            if gym_account.payouts_enabled and not stripe_account.payouts_enabled:
                discrepancy = "BD marca payouts_enabled=True pero Stripe tiene payouts_enabled=False"
                report["discrepancies"].append(discrepancy)
                print(f"⚠️  {discrepancy}")

                if auto_repair:
                    db.execute(
                        text("UPDATE gym_stripe_accounts SET payouts_enabled = false, updated_at = NOW() WHERE gym_id = :gym_id"),
                        {"gym_id": gym_id}
                    )
                    report["repair_actions"].append("Marcada payouts_enabled=False en BD")
                    print("   🔧 AUTO-REPARADO: payouts_enabled actualizado")

            # Commit cambios si auto-repair está activo
            if auto_repair and report["repair_actions"]:
                db.commit()
                report["auto_repaired"] = True
                print("\n✅ Cambios guardados en base de datos")

            if not report["discrepancies"]:
                print("✅ No se detectaron discrepancias\n")
            else:
                print()

            # 4. Generar recomendaciones
            if not gym_account.is_active or not stripe_account.charges_enabled:
                report["status"] = "WARNING"
                report["action_required"] = [
                    "⚠️  La cuenta está inactiva o no puede procesar pagos",
                    "",
                    "📝 OPCIONES:",
                    "1. Verificar estado completo: GET /api/v1/stripe-connect/accounts/connection-status",
                    "2. Si el gym necesita reconectar: POST /api/v1/stripe-connect/accounts/onboarding-link",
                    "3. Si quieren nueva cuenta: POST /api/v1/stripe-connect/accounts"
                ]
            elif not gym_account.onboarding_completed or not stripe_account.details_submitted:
                report["status"] = "WARNING"
                report["action_required"] = [
                    "⚠️  Onboarding incompleto",
                    "",
                    "📝 SOLUCIÓN:",
                    "1. Generar link de onboarding: POST /api/v1/stripe-connect/accounts/onboarding-link",
                    "2. El admin del gym debe completar el proceso en Stripe"
                ]
            else:
                report["status"] = "OK"
                report["message"] = "✅ Cuenta activa y funcionando correctamente"
                print("🎉 RESULTADO: Cuenta en perfecto estado\n")

        except stripe.error.PermissionError as e:
            print("❌ Cuenta desautorizada o sin acceso\n")

            report["status"] = "ERROR"
            report["status_stripe"] = {
                "exists": False,
                "error": "PermissionError - cuenta desautorizada o desconectada",
                "error_details": str(e)
            }
            report["discrepancies"].append("Cuenta desconectada de la plataforma (sin permisos de acceso)")

            if auto_repair:
                print("🔧 AUTO-REPARACIÓN ACTIVADA...")
                db.execute(
                    text("""
                        UPDATE gym_stripe_accounts
                        SET is_active = false,
                            charges_enabled = false,
                            payouts_enabled = false,
                            updated_at = NOW()
                        WHERE gym_id = :gym_id
                    """),
                    {"gym_id": gym_id}
                )
                db.commit()

                report["auto_repaired"] = True
                report["repair_actions"] = [
                    "Marcada is_active=False",
                    "Marcada charges_enabled=False",
                    "Marcada payouts_enabled=False"
                ]
                print("✅ Cuenta marcada como inactiva en BD\n")

            report["action_required"] = [
                "❌ Cuenta desconectada o sin permisos",
                "",
                "📝 SOLUCIÓN:",
                "1. Si es Standard Account: El gym puede haberla desconectado desde su Stripe Dashboard",
                "2. Crear nueva cuenta: POST /api/v1/stripe-connect/accounts",
                "3. Completar onboarding: POST /api/v1/stripe-connect/accounts/onboarding-link",
                "",
                "⚠️  IMPORTANTE: Configurar webhook de desconexiones",
                "   Ver: docs/STRIPE_CONNECT_WEBHOOK_SETUP.md"
            ]

        except stripe.error.InvalidRequestError as e:
            print(f"❌ Error de Stripe: {e}\n")

            report["status"] = "ERROR"
            report["status_stripe"] = {
                "exists": False,
                "error": "InvalidRequestError",
                "error_details": str(e)
            }
            report["action_required"] = [
                f"❌ Error de Stripe: {str(e)}",
                "",
                "📝 Contactar soporte técnico"
            ]

        except Exception as e:
            print(f"❌ Error inesperado: {e}\n")

            report["status"] = "ERROR"
            report["status_stripe"] = {
                "exists": "unknown",
                "error": str(type(e).__name__),
                "error_details": str(e)
            }

        return report

    finally:
        db.close()


def print_report_summary(report: dict):
    """Imprimir resumen del reporte."""
    print(f"\n{'='*70}")
    print("RESUMEN DEL DIAGNÓSTICO")
    print(f"{'='*70}\n")

    status_emoji = {
        "OK": "✅",
        "WARNING": "⚠️",
        "ERROR": "❌"
    }

    status = report.get("status", "UNKNOWN")
    print(f"Estado: {status_emoji.get(status, '❓')} {status}")

    if report.get("message"):
        print(f"\n{report['message']}")

    if report.get("discrepancies"):
        print(f"\n📋 Discrepancias detectadas: {len(report['discrepancies'])}")
        for disc in report["discrepancies"]:
            print(f"   • {disc}")

    if report.get("auto_repaired"):
        print(f"\n🔧 Auto-reparación ejecutada:")
        for action in report.get("repair_actions", []):
            print(f"   ✓ {action}")

    if report.get("action_required"):
        print(f"\n📝 ACCIONES REQUERIDAS:")
        for action in report["action_required"]:
            print(f"   {action}")

    print(f"\n{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Diagnosticar cuenta de Stripe Connect de un gimnasio"
    )
    parser.add_argument(
        "--gym-id",
        type=int,
        required=True,
        help="ID del gimnasio a diagnosticar"
    )
    parser.add_argument(
        "--auto-repair",
        action="store_true",
        help="Auto-reparar problemas detectados (marca cuentas desconectadas como inactivas)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Salida en formato JSON"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Guardar reporte en archivo JSON"
    )

    args = parser.parse_args()

    # Ejecutar diagnóstico
    report = diagnose_gym_stripe_account(args.gym_id, args.auto_repair)

    # Salida JSON
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report_summary(report)

    # Guardar en archivo si se especificó
    if args.output:
        with open(args.output, 'w') as f:
            json.dumps(report, f, indent=2)
        print(f"✅ Reporte guardado en: {args.output}\n")


if __name__ == "__main__":
    main()
