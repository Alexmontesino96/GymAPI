#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings

def main():
    print("🔍 VERIFICANDO CONFIGURACIÓN DE STRIPE")
    print("=" * 50)
    
    settings = get_settings()
    
    # Verificar claves (SIN exponer partes sensibles)
    publishable_key = settings.STRIPE_PUBLISHABLE_KEY or ""
    secret_key = settings.STRIPE_SECRET_KEY or ""
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET or ""
    
    # Verificar configuración sin exponer claves
    print(f"📋 STRIPE_PUBLISHABLE_KEY: {'✅ Configurada' if publishable_key else '❌ No configurada'}")
    print(f"📋 STRIPE_SECRET_KEY: {'✅ Configurada' if secret_key else '❌ No configurada'}")
    print(f"📋 STRIPE_WEBHOOK_SECRET: {'✅ Configurada' if webhook_secret else '❌ No configurada'}")
    
    errors = []
    
    # Verificar que no sean placeholders
    if not secret_key:
        errors.append("STRIPE_SECRET_KEY no está configurada")
    elif "your_sec" in secret_key.lower() or "placeholder" in secret_key.lower():
        errors.append("STRIPE_SECRET_KEY parece ser un placeholder")
    
    if not publishable_key:
        errors.append("STRIPE_PUBLISHABLE_KEY no está configurada")
    elif "your_pub" in publishable_key.lower() or "placeholder" in publishable_key.lower():
        errors.append("STRIPE_PUBLISHABLE_KEY parece ser un placeholder")
    
    if not webhook_secret:
        errors.append("STRIPE_WEBHOOK_SECRET no está configurada - CRÍTICO para seguridad")
    elif "your_webhook" in webhook_secret.lower() or "placeholder" in webhook_secret.lower():
        errors.append("STRIPE_WEBHOOK_SECRET parece ser un placeholder")
    elif not webhook_secret.startswith("whsec_"):
        errors.append("STRIPE_WEBHOOK_SECRET no tiene el formato esperado (debe empezar con 'whsec_')")
    
    # Verificar formato de claves
    if publishable_key and not publishable_key.startswith(("pk_test_", "pk_live_")):
        errors.append("STRIPE_PUBLISHABLE_KEY no tiene el formato esperado")
    
    if secret_key and not secret_key.startswith(("sk_test_", "sk_live_")):
        errors.append("STRIPE_SECRET_KEY no tiene el formato esperado")
    
    # Mostrar errores
    if errors:
        print("\n❌ ERRORES ENCONTRADOS:")
        for error in errors:
            print(f"   • {error}")
        print("\n📖 Consulta docs/environment_variables.md para más información")
        return False
    
    print("\n🎉 CONFIGURACIÓN DE STRIPE CORRECTA")
    print("🔒 Todas las claves están configuradas y tienen el formato correcto")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 