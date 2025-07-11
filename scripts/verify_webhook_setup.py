#!/usr/bin/env python3
"""
Script para verificar la configuración de webhooks de Stripe
"""
import os
import sys
import requests
import stripe
from datetime import datetime

# Agregar el directorio padre al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings

def main():
    print("🔍 Verificando configuración de webhooks de Stripe...")
    print("=" * 60)
    
    settings = get_settings()
    
    # 1. Verificar claves de API
    print("\n1️⃣ Verificando claves de API:")
    print(f"   STRIPE_PUBLISHABLE_KEY: {'✅ Configurada' if settings.STRIPE_PUBLISHABLE_KEY else '❌ No configurada'}")
    print(f"   STRIPE_SECRET_KEY: {'✅ Configurada' if settings.STRIPE_SECRET_KEY else '❌ No configurada'}")
    print(f"   STRIPE_WEBHOOK_SECRET: {'✅ Configurada' if settings.STRIPE_WEBHOOK_SECRET else '❌ No configurada'}")
    
    if not settings.STRIPE_SECRET_KEY:
        print("❌ No se puede continuar sin STRIPE_SECRET_KEY")
        return
    
    # 2. Configurar Stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    # 3. Verificar conexión con Stripe
    print("\n2️⃣ Verificando conexión con Stripe:")
    try:
        account = stripe.Account.retrieve()
        print(f"   ✅ Conectado a cuenta: {account.display_name or account.id}")
        print(f"   📧 Email: {account.email}")
        print(f"   🌍 País: {account.country}")
        print(f"   💰 Moneda: {account.default_currency}")
    except Exception as e:
        print(f"   ❌ Error conectando con Stripe: {e}")
        return
    
    # 4. Listar webhooks configurados
    print("\n3️⃣ Webhooks configurados en Stripe:")
    try:
        webhooks = stripe.WebhookEndpoint.list()
        
        if not webhooks.data:
            print("   ⚠️  No hay webhooks configurados")
        else:
            for webhook in webhooks.data:
                print(f"   📡 URL: {webhook.url}")
                print(f"      Status: {'✅ Activo' if webhook.status == 'enabled' else '❌ Inactivo'}")
                print(f"      Eventos: {', '.join(webhook.enabled_events)}")
                print(f"      Creado: {datetime.fromtimestamp(webhook.created)}")
                print()
    except Exception as e:
        print(f"   ❌ Error obteniendo webhooks: {e}")
    
    # 5. Verificar eventos críticos
    print("\n4️⃣ Eventos críticos para el sistema:")
    
    # Eventos críticos (OBLIGATORIOS)
    critical_events = [
        'checkout.session.completed',
        'invoice.payment_succeeded', 
        'invoice.payment_failed',
        'customer.subscription.deleted',
        'customer.subscription.updated'
    ]
    
    # Eventos recomendados
    recommended_events = [
        'customer.subscription.trial_will_end',
        'invoice.payment_action_required',
        'invoice.upcoming',
        'charge.dispute.created',
        'payment_intent.payment_failed'
    ]
    
    webhook_events = []
    for webhook in webhooks.data:
        webhook_events.extend(webhook.enabled_events)
    
    print("\n   🔴 EVENTOS CRÍTICOS (OBLIGATORIOS):")
    critical_missing = 0
    for event in critical_events:
        if event in webhook_events:
            print(f"   ✅ {event}")
        else:
            print(f"   ❌ {event} - NO CONFIGURADO")
            critical_missing += 1
    
    print("\n   🟡 EVENTOS RECOMENDADOS:")
    recommended_missing = 0
    for event in recommended_events:
        if event in webhook_events:
            print(f"   ✅ {event}")
        else:
            print(f"   ⚠️  {event} - NO CONFIGURADO")
            recommended_missing += 1
    
    # Resumen de configuración
    print(f"\n   📊 RESUMEN:")
    print(f"   • Eventos críticos configurados: {len(critical_events) - critical_missing}/{len(critical_events)}")
    print(f"   • Eventos recomendados configurados: {len(recommended_events) - recommended_missing}/{len(recommended_events)}")
    
    if critical_missing == 0:
        print("   ✅ Todos los eventos críticos están configurados")
    else:
        print(f"   ❌ Faltan {critical_missing} eventos críticos - SISTEMA NO FUNCIONARÁ CORRECTAMENTE")
    
    # 6. Verificar endpoint del webhook
    print("\n5️⃣ Verificando endpoint del webhook:")
    webhook_url = f"{settings.BASE_URL}/api/v1/memberships/webhooks/stripe"
    print(f"   URL esperada: {webhook_url}")
    
    try:
        # Hacer una petición GET para verificar que el endpoint existe
        response = requests.get(webhook_url.replace('/webhooks/stripe', '/plans'))
        if response.status_code in [200, 401, 403]:
            print("   ✅ Endpoint del backend accesible")
        else:
            print(f"   ⚠️  Endpoint responde con status {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error accediendo al endpoint: {e}")
    
    # 7. Verificar configuración del webhook secret
    print("\n6️⃣ Verificando webhook secret:")
    if settings.STRIPE_WEBHOOK_SECRET:
        if settings.STRIPE_WEBHOOK_SECRET.startswith('whsec_'):
            print("   ✅ Formato correcto del webhook secret")
        else:
            print("   ⚠️  El webhook secret no tiene el formato esperado")
            
        if 'your_webhook' in settings.STRIPE_WEBHOOK_SECRET.lower():
            print("   ❌ El webhook secret parece ser un placeholder")
    else:
        print("   ❌ Webhook secret no configurado")
    
    # 8. Resumen y recomendaciones
    print("\n7️⃣ Resumen y recomendaciones:")
    print("=" * 40)
    
    if not webhooks.data:
        print("🔧 ACCIÓN REQUERIDA: Configurar webhook en Stripe")
        print("   1. Ve a https://dashboard.stripe.com/webhooks")
        print("   2. Crea un nuevo webhook endpoint")
        print(f"   3. URL: {webhook_url}")
        print("   4. Selecciona estos eventos CRÍTICOS:")
        for event in critical_events:
            print(f"      - {event}")
        print("   5. Eventos RECOMENDADOS (opcionales):")
        for event in recommended_events:
            print(f"      - {event}")
        print("   6. Copia el webhook secret a tu archivo .env")
        print()
    elif critical_missing > 0:
        print("🚨 CONFIGURACIÓN INCOMPLETA:")
        print(f"   Faltan {critical_missing} eventos críticos")
        print("   Tu sistema NO funcionará correctamente sin estos eventos")
        print()
        print("   Eventos faltantes críticos:")
        for event in critical_events:
            if event not in webhook_events:
                print(f"      ❌ {event}")
        print()
        print("   📝 ACCIÓN REQUERIDA:")
        print("   1. Ve a tu webhook en https://dashboard.stripe.com/webhooks")
        print("   2. Edita el webhook")
        print("   3. Agrega los eventos faltantes")
        print("   4. Guarda los cambios")
    else:
        print("✅ CONFIGURACIÓN CORRECTA:")
        print("   Todos los eventos críticos están configurados")
        if recommended_missing > 0:
            print(f"   Opcional: Puedes agregar {recommended_missing} eventos recomendados")
        else:
            print("   ¡Configuración completa con todos los eventos!")
        print()
    
    # 9. Verificar pagos recientes
    print("\n8️⃣ Verificando pagos recientes:")
    try:
        charges = stripe.Charge.list(limit=5)
        if charges.data:
            print(f"   📊 Últimos {len(charges.data)} pagos:")
            for charge in charges.data:
                status = "✅ Exitoso" if charge.paid else "❌ Fallido"
                amount = charge.amount / 100
                currency = charge.currency.upper()
                created = datetime.fromtimestamp(charge.created)
                print(f"      {status} - {amount} {currency} - {created}")
        else:
            print("   ℹ️  No hay pagos recientes")
    except Exception as e:
        print(f"   ❌ Error obteniendo pagos: {e}")
    
    print("\n✅ Verificación completada!")

if __name__ == "__main__":
    main() 