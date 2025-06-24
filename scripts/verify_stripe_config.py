#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings

def main():
    print("🔍 VERIFICANDO CONFIGURACIÓN DE STRIPE")
    print("=" * 50)
    
    settings = get_settings()
    
    # Verificar claves (ocultar parte sensible)
    publishable_key = settings.STRIPE_PUBLISHABLE_KEY
    secret_key = settings.STRIPE_SECRET_KEY
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET
    
    print(f"✅ STRIPE_PUBLISHABLE_KEY: {publishable_key[:20]}...{publishable_key[-10:] if len(publishable_key) > 30 else publishable_key}")
    print(f"✅ STRIPE_SECRET_KEY: {secret_key[:20]}...{secret_key[-10:] if len(secret_key) > 30 else secret_key}")
    print(f"✅ STRIPE_WEBHOOK_SECRET: {webhook_secret[:20]}...{webhook_secret[-10:] if len(webhook_secret) > 30 else webhook_secret}")
    
    # Verificar que no sean placeholders
    if "your_sec" in secret_key.lower() or "placeholder" in secret_key.lower():
        print("❌ ERROR: STRIPE_SECRET_KEY parece ser un placeholder")
        return False
    
    if "your_pub" in publishable_key.lower() or "placeholder" in publishable_key.lower():
        print("❌ ERROR: STRIPE_PUBLISHABLE_KEY parece ser un placeholder")
        return False
    
    print("\n🎉 CONFIGURACIÓN DE STRIPE CORRECTA")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 