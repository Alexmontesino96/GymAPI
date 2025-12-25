"""
Script para verificar la configuración del webhook de Stripe Connect.

El webhook es CRÍTICO para detectar cuando Standard Accounts se desconectan.

Uso:
    python scripts/verify_stripe_connect_webhook.py
"""
import os
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings

settings = get_settings()


def verify_webhook_config():
    """Verificar configuración de webhook de Stripe Connect."""

    print("\n" + "=" * 70)
    print("VERIFICACIÓN DE WEBHOOK DE STRIPE CONNECT")
    print("=" * 70 + "\n")

    all_ok = True

    # 1. Verificar variable de entorno
    print("📋 PASO 1: Verificando variable de entorno...")
    connect_secret = os.getenv("STRIPE_CONNECT_WEBHOOK_SECRET")

    if not connect_secret:
        print("❌ STRIPE_CONNECT_WEBHOOK_SECRET no configurado\n")
        all_ok = False

        print("=" * 70)
        print("📝 PASOS PARA CONFIGURAR EL WEBHOOK")
        print("=" * 70 + "\n")

        print("1️⃣  Ir a Stripe Dashboard > Developers > Webhooks")
        print("   URL: https://dashboard.stripe.com/webhooks\n")

        print("2️⃣  Click en 'Add endpoint'\n")

        # Determinar URL del endpoint
        base_url = getattr(settings, 'BASE_URL', None) or "https://api.tu-dominio.com"
        endpoint_url = f"{base_url}/api/v1/webhooks/stripe-connect/connect"

        print("3️⃣  Configurar endpoint:")
        print(f"   URL: {endpoint_url}")
        print("   Descripción: Webhook para desconexiones de Stripe Connect\n")

        print("4️⃣  Seleccionar eventos (IMPORTANTE):")
        print("   ✅ account.application.deauthorized (CRÍTICO para Standard accounts)")
        print("   ✅ account.updated (Recomendado)\n")

        print("5️⃣  Copiar 'Signing secret' (formato: whsec_...)\n")

        print("6️⃣  Agregar a archivo .env:")
        print("   STRIPE_CONNECT_WEBHOOK_SECRET=whsec_xxx\n")

        print("7️⃣  Reiniciar servidor para que tome la nueva variable\n")

        print("=" * 70)
        print("\n📖 Documentación completa: docs/STRIPE_CONNECT_WEBHOOK_SETUP.md\n")

    else:
        print(f"✅ STRIPE_CONNECT_WEBHOOK_SECRET configurado")
        print(f"   Valor: {connect_secret[:15]}...{connect_secret[-4:]}\n")

    # 2. Verificar endpoint de webhook existe
    print("📋 PASO 2: Verificando endpoint de webhook...")

    webhook_file = Path(__file__).parent.parent / "app" / "api" / "v1" / "endpoints" / "webhooks" / "stripe_connect_webhooks.py"

    if webhook_file.exists():
        print("✅ Archivo de webhook existe")
        print(f"   Ubicación: {webhook_file}\n")
    else:
        print(f"❌ Archivo de webhook NO encontrado: {webhook_file}\n")
        all_ok = False

    # 3. Información sobre testing
    if connect_secret:
        print("📋 PASO 3: Información sobre testing...")
        print("\n💡 Para probar el webhook localmente:\n")
        print("1️⃣  Instalar Stripe CLI:")
        print("   brew install stripe/stripe-cli/stripe  # macOS")
        print("   https://stripe.com/docs/stripe-cli  # Otras plataformas\n")

        print("2️⃣  Login con Stripe CLI:")
        print("   stripe login\n")

        print("3️⃣  Simular evento de desconexión:")
        print("   stripe trigger account.application.deauthorized\n")

        print("4️⃣  Escuchar webhooks en desarrollo:")
        base_url = settings.BASE_URL or "localhost:8000"
        endpoint_path = "/api/v1/webhooks/stripe-connect/connect"
        print(f"   stripe listen --forward-to {base_url}{endpoint_path}\n")

    # 4. Resumen
    print("=" * 70)
    print("RESUMEN")
    print("=" * 70 + "\n")

    if all_ok:
        print("✅ Configuración básica OK\n")
        print("⚠️  IMPORTANTE: Asegúrate de que el webhook esté configurado en Stripe Dashboard")
        print("   para que las desconexiones se detecten automáticamente.\n")
    else:
        print("❌ Se detectaron problemas de configuración\n")
        print("📝 Sigue los pasos indicados arriba para configurar el webhook.\n")
        print("⚠️  Sin webhook configurado:")
        print("   • Las cuentas desconectadas NO se marcarán como inactivas automáticamente")
        print("   • Los pagos pueden fallar con errores 403 'account_invalid'")
        print("   • Requiere verificación manual con el script de diagnóstico\n")

    print("=" * 70 + "\n")

    return all_ok


def main():
    result = verify_webhook_config()
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
