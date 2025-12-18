"""
Script para probar el flujo completo de Standard accounts con Stripe Connect.

Este script prueba:
1. Creación de cuenta Standard
2. Generación de link de onboarding
3. Verificación de estado después de onboarding
4. Verificación de conexión
5. Acceso al dashboard
6. Simulación de desconexión (manual)

Uso:
    python scripts/test_stripe_connect_standard.py
"""

import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.services.stripe_connect_service import stripe_connect_service
from app.core.config import get_settings
import stripe
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
stripe.api_key = settings.STRIPE_SECRET_KEY


async def test_standard_account_flow():
    """Probar flujo completo de Standard account"""

    print("=" * 70)
    print("TEST: FLUJO COMPLETO DE STRIPE CONNECT STANDARD ACCOUNT")
    print("=" * 70)
    print()

    db = SessionLocal()
    test_gym_id = 1  # Cambiar según tu setup

    try:
        # Verificar configuración
        print("📋 Verificando configuración...")
        if not settings.STRIPE_SECRET_KEY:
            print("❌ ERROR: STRIPE_SECRET_KEY no configurada")
            print("   Configura STRIPE_SECRET_KEY en .env")
            return

        if not settings.STRIPE_CONNECT_WEBHOOK_SECRET:
            print("⚠️  ADVERTENCIA: STRIPE_CONNECT_WEBHOOK_SECRET no configurada")
            print("   El webhook de desconexión NO funcionará")
            print("   Configura STRIPE_CONNECT_WEBHOOK_SECRET en .env")
            print()

        print("✅ Configuración básica OK")
        print(f"   Usando gym_id: {test_gym_id}")
        print()

        # 1. Crear cuenta Standard
        print("-" * 70)
        print("PASO 1: Creando cuenta Standard...")
        print("-" * 70)

        try:
            gym_account = await stripe_connect_service.create_gym_stripe_account(
                db, test_gym_id, country="US", account_type="standard"
            )
            print(f"✅ Cuenta creada exitosamente:")
            print(f"   Account ID: {gym_account.stripe_account_id}")
            print(f"   Tipo: {gym_account.account_type}")
            print(f"   País: {gym_account.country}")
            print(f"   Activa: {gym_account.is_active}")
            print()
        except Exception as e:
            # Puede fallar si ya existe
            gym_account = stripe_connect_service.get_gym_stripe_account(db, test_gym_id)
            if gym_account:
                print(f"ℹ️  Cuenta ya existe: {gym_account.stripe_account_id}")
                print(f"   Tipo: {gym_account.account_type}")
                if gym_account.account_type != "standard":
                    print(f"   ⚠️  ADVERTENCIA: Cuenta es tipo '{gym_account.account_type}', no 'standard'")
                print()
            else:
                print(f"❌ Error creando cuenta: {str(e)}")
                return

        # 2. Generar link de onboarding
        print("-" * 70)
        print("PASO 2: Generando link de onboarding...")
        print("-" * 70)

        try:
            onboarding_url = await stripe_connect_service.create_onboarding_link(
                db, test_gym_id,
                refresh_url="http://localhost:8000/admin/stripe/reauth",
                return_url="http://localhost:8000/admin/stripe/complete"
            )
            print(f"✅ Link de onboarding generado:")
            print(f"   URL: {onboarding_url}")
            print(f"   Validez: 1 hora")
            print()
            print("⏸️  ACCIÓN MANUAL REQUERIDA:")
            print("   1. Abre el link en un navegador")
            print("   2. Completa el proceso de onboarding en Stripe")
            print("   3. Presiona Enter aquí cuando hayas terminado")
            print()
            input("   Presiona Enter cuando hayas completado el onboarding...")
            print()
        except Exception as e:
            print(f"❌ Error generando onboarding link: {str(e)}")
            if "already completed" in str(e).lower():
                print("   ℹ️  El onboarding ya fue completado previamente")
                print()
            else:
                return

        # 3. Verificar estado
        print("-" * 70)
        print("PASO 3: Verificando estado de la cuenta...")
        print("-" * 70)

        try:
            updated_account = await stripe_connect_service.update_gym_account_status(
                db, test_gym_id
            )
            print(f"✅ Estado actualizado desde Stripe:")
            print(f"   Account ID: {updated_account.stripe_account_id}")
            print(f"   Tipo: {updated_account.account_type}")
            print(f"   Onboarding completado: {updated_account.onboarding_completed}")
            print(f"   Charges enabled: {updated_account.charges_enabled}")
            print(f"   Payouts enabled: {updated_account.payouts_enabled}")
            print(f"   Details submitted: {updated_account.details_submitted}")
            print()

            if not updated_account.onboarding_completed:
                print("⚠️  ADVERTENCIA: Onboarding no completado")
                print("   Verifica que completaste todos los pasos en Stripe")
                print("   Puede tomar algunos minutos en procesarse")
                return

            if not updated_account.charges_enabled:
                print("⚠️  ADVERTENCIA: Charges no habilitados")
                print("   La cuenta puede estar en revisión por Stripe")
                print("   Verifica en el dashboard de Stripe")
                print()

        except Exception as e:
            print(f"❌ Error verificando estado: {str(e)}")
            return

        # 4. Test de verificación de conexión
        print("-" * 70)
        print("PASO 4: Probando endpoint de verificación de conexión...")
        print("-" * 70)

        try:
            # Simular verificación de conexión
            from app.models.stripe_profile import GymStripeAccount

            gym_account = db.query(GymStripeAccount).filter(
                GymStripeAccount.gym_id == test_gym_id,
                GymStripeAccount.is_active == True
            ).first()

            if gym_account:
                # Verificar acceso a Stripe
                try:
                    account = stripe.Account.retrieve(gym_account.stripe_account_id)
                    print(f"✅ Verificación de conexión exitosa:")
                    print(f"   Conectado: Sí")
                    print(f"   Tipo de cuenta: {gym_account.account_type}")
                    print(f"   Puede desconectar: {'Sí' if gym_account.account_type == 'standard' else 'No'}")
                    print(f"   Acceso directo dashboard: {'Sí' if gym_account.account_type == 'standard' else 'No'}")
                    print()
                except stripe.error.PermissionError:
                    print(f"❌ Sin acceso a la cuenta")
                    print(f"   La cuenta fue desautorizada")
                    print()
            else:
                print("❌ No se encontró cuenta activa")
                print()

        except Exception as e:
            print(f"❌ Error en verificación: {str(e)}")
            print()

        # 5. Test de dashboard access
        print("-" * 70)
        print("PASO 5: Verificando acceso al dashboard...")
        print("-" * 70)

        if gym_account.account_type == "standard":
            print(f"✅ Standard Account detectada:")
            print(f"   Dashboard URL: https://dashboard.stripe.com")
            print(f"   Acceso: Directo (sin login links temporales)")
            print(f"   Instrucciones:")
            print(f"     1. Vaya a https://dashboard.stripe.com")
            print(f"     2. Inicie sesión con sus credenciales de Stripe")
            print(f"     3. Tendrá acceso completo a su cuenta")
            print()
        else:
            print(f"ℹ️  Cuenta tipo '{gym_account.account_type}':")
            print(f"   Requiere login link temporal")
            try:
                dashboard_url = await stripe_connect_service.create_dashboard_login_link(
                    db, test_gym_id
                )
                print(f"   Dashboard URL (60 min): {dashboard_url}")
                print()
            except Exception as e:
                print(f"   ❌ Error generando login link: {str(e)}")
                print()

        # 6. Simulación de desconexión
        print("-" * 70)
        print("PASO 6: Prueba de manejo de desconexión...")
        print("-" * 70)
        print()
        print("📖 INFO: Standard accounts pueden desconectarse desde Stripe")
        print()
        print("Para probar el manejo de desconexión:")
        print("1. Ve a: https://dashboard.stripe.com/settings/applications")
        print(f"2. Busca tu aplicación (Account ID: {gym_account.stripe_account_id})")
        print("3. Haz clic en 'Disconnect'")
        print("4. El webhook debería:")
        print("   - Recibir evento 'account.application.deauthorized'")
        print("   - Marcar cuenta como inactiva en BD")
        print("   - Deshabilitar charges_enabled")
        print(f"   - Verificar en logs: grep 'desautorizada' logs/app.log")
        print()
        print("⚠️  NOTA: Si desconectas, necesitarás crear una nueva cuenta")
        print("         para continuar usando Stripe en este gym")
        print()

        # Resumen final
        print("=" * 70)
        print("RESUMEN DEL TEST")
        print("=" * 70)
        print()
        print(f"✅ Cuenta Standard creada: {gym_account.stripe_account_id}")
        print(f"✅ Tipo de cuenta: {gym_account.account_type}")
        print(f"✅ Onboarding completado: {updated_account.onboarding_completed}")
        print(f"✅ Charges enabled: {updated_account.charges_enabled}")
        print(f"✅ Payouts enabled: {updated_account.payouts_enabled}")
        print()

        if gym_account.account_type == "standard":
            print("🎉 Características de Standard Account:")
            print("   ✅ Dashboard propio en https://dashboard.stripe.com")
            print("   ✅ Acceso directo sin login links temporales")
            print("   ✅ Puede desconectarse cuando quiera")
            print("   ✅ Control total de su cuenta")
        print()
        print("=" * 70)

    except Exception as e:
        logger.error(f"❌ Error en test: {str(e)}", exc_info=True)

    finally:
        db.close()


if __name__ == "__main__":
    print()
    print("🧪 Iniciando test de Stripe Connect Standard Account...")
    print()

    asyncio.run(test_standard_account_flow())

    print()
    print("✅ Test completado")
    print()
