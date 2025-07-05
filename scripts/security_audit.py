#!/usr/bin/env python3
"""
Script de Auditoría de Seguridad para GymAPI

Verifica que todas las configuraciones críticas de seguridad estén correctamente configuradas
sin exponer información sensible en logs.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
import logging

# Configurar logging para no mostrar información sensible
logging.basicConfig(level=logging.WARNING)

def check_stripe_config(settings) -> tuple[bool, list]:
    """Verificar configuración de Stripe"""
    errors = []
    
    # Verificar STRIPE_SECRET_KEY
    if not settings.STRIPE_SECRET_KEY:
        errors.append("🔴 CRÍTICO: STRIPE_SECRET_KEY no configurada")
    elif "your_sec" in str(settings.STRIPE_SECRET_KEY).lower() or "placeholder" in str(settings.STRIPE_SECRET_KEY).lower():
        errors.append("🔴 CRÍTICO: STRIPE_SECRET_KEY parece ser un placeholder")
    elif not str(settings.STRIPE_SECRET_KEY).startswith(("sk_test_", "sk_live_")):
        errors.append("🟡 ADVERTENCIA: STRIPE_SECRET_KEY no tiene el formato esperado")
    
    # Verificar STRIPE_PUBLISHABLE_KEY
    if not settings.STRIPE_PUBLISHABLE_KEY:
        errors.append("🔴 CRÍTICO: STRIPE_PUBLISHABLE_KEY no configurada")
    elif not str(settings.STRIPE_PUBLISHABLE_KEY).startswith(("pk_test_", "pk_live_")):
        errors.append("🟡 ADVERTENCIA: STRIPE_PUBLISHABLE_KEY no tiene el formato esperado")
    
    # Verificar STRIPE_WEBHOOK_SECRET
    if not settings.STRIPE_WEBHOOK_SECRET:
        errors.append("🔴 CRÍTICO: STRIPE_WEBHOOK_SECRET no configurada - webhooks inseguros")
    elif "your_webhook" in str(settings.STRIPE_WEBHOOK_SECRET).lower():
        errors.append("🔴 CRÍTICO: STRIPE_WEBHOOK_SECRET parece ser un placeholder")
    elif not str(settings.STRIPE_WEBHOOK_SECRET).startswith("whsec_"):
        errors.append("🟡 ADVERTENCIA: STRIPE_WEBHOOK_SECRET no tiene el formato esperado")
    
    return len(errors) == 0, errors

def check_auth0_config(settings) -> tuple[bool, list]:
    """Verificar configuración de Auth0"""
    errors = []
    
    if not settings.AUTH0_DOMAIN:
        errors.append("🔴 CRÍTICO: AUTH0_DOMAIN no configurado")
    
    if not settings.AUTH0_CLIENT_SECRET:
        errors.append("🔴 CRÍTICO: AUTH0_CLIENT_SECRET no configurado")
    elif "your_client_secret" in str(settings.AUTH0_CLIENT_SECRET).lower():
        errors.append("🔴 CRÍTICO: AUTH0_CLIENT_SECRET parece ser un placeholder")
    
    if not settings.AUTH0_WEBHOOK_SECRET:
        errors.append("🟡 ADVERTENCIA: AUTH0_WEBHOOK_SECRET no configurado")
    
    return len(errors) == 0, errors

def check_database_config(settings) -> tuple[bool, list]:
    """Verificar configuración de base de datos"""
    errors = []
    
    if not settings.DATABASE_URL and not settings.SQLALCHEMY_DATABASE_URI:
        errors.append("🔴 CRÍTICO: DATABASE_URL no configurada")
    
    if not settings.SECRET_KEY:
        errors.append("🔴 CRÍTICO: SECRET_KEY no configurada")
    elif len(str(settings.SECRET_KEY)) < 32:
        errors.append("🟡 ADVERTENCIA: SECRET_KEY muy corta (recomendado: 32+ caracteres)")
    
    return len(errors) == 0, errors

def check_redis_config(settings) -> tuple[bool, list]:
    """Verificar configuración de Redis"""
    errors = []
    
    if not settings.REDIS_URL:
        errors.append("🟡 ADVERTENCIA: REDIS_URL no configurada")
    
    return len(errors) == 0, errors

def check_external_services(settings) -> tuple[bool, list]:
    """Verificar configuración de servicios externos"""
    errors = []
    
    # Stream.io (Chat)
    if not settings.STREAM_API_SECRET:
        errors.append("🟡 ADVERTENCIA: STREAM_API_SECRET no configurado (chat deshabilitado)")
    
    # OneSignal (Notificaciones)
    if not settings.ONESIGNAL_REST_API_KEY:
        errors.append("🟡 ADVERTENCIA: ONESIGNAL_REST_API_KEY no configurado (notificaciones deshabilitadas)")
    
    return len(errors) == 0, errors

def main():
    print("🔒 AUDITORÍA DE SEGURIDAD - GYMAPI")
    print("=" * 60)
    
    try:
        settings = get_settings()
    except Exception as e:
        print(f"🔴 ERROR CRÍTICO: No se pudo cargar la configuración: {e}")
        return False
    
    all_passed = True
    total_errors = []
    
    # Verificar Stripe
    print("\n📊 Verificando configuración de Stripe...")
    stripe_ok, stripe_errors = check_stripe_config(settings)
    if stripe_ok:
        print("   ✅ Configuración de Stripe correcta")
    else:
        all_passed = False
        total_errors.extend(stripe_errors)
    
    # Verificar Auth0
    print("\n🔐 Verificando configuración de Auth0...")
    auth0_ok, auth0_errors = check_auth0_config(settings)
    if auth0_ok:
        print("   ✅ Configuración de Auth0 correcta")
    else:
        all_passed = False
        total_errors.extend(auth0_errors)
    
    # Verificar Base de Datos
    print("\n🗄️ Verificando configuración de base de datos...")
    db_ok, db_errors = check_database_config(settings)
    if db_ok:
        print("   ✅ Configuración de base de datos correcta")
    else:
        all_passed = False
        total_errors.extend(db_errors)
    
    # Verificar Redis
    print("\n📦 Verificando configuración de Redis...")
    redis_ok, redis_errors = check_redis_config(settings)
    if redis_ok:
        print("   ✅ Configuración de Redis correcta")
    else:
        total_errors.extend(redis_errors)
    
    # Verificar servicios externos
    print("\n🌐 Verificando servicios externos...")
    ext_ok, ext_errors = check_external_services(settings)
    if ext_ok:
        print("   ✅ Configuración de servicios externos correcta")
    else:
        total_errors.extend(ext_errors)
    
    # Resumen
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 AUDITORÍA COMPLETADA: Todas las configuraciones críticas están correctas")
        print("🔒 El sistema está configurado de forma segura")
        return True
    else:
        print("⚠️ AUDITORÍA COMPLETADA: Se encontraron problemas de configuración")
        print("\n🔍 PROBLEMAS ENCONTRADOS:")
        for error in total_errors:
            print(f"   {error}")
        
        critical_errors = [e for e in total_errors if "🔴 CRÍTICO" in e]
        if critical_errors:
            print(f"\n🚨 ERRORES CRÍTICOS: {len(critical_errors)}")
            print("   Estos problemas deben resolverse antes de usar el sistema en producción")
        
        print("\n📖 Consulta docs/environment_variables.md para configurar las variables faltantes")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 