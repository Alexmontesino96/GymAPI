#!/usr/bin/env python3
"""
Script para probar pagos de Stripe con tarjetas de prueba.
Permite simular diferentes escenarios de pago sin dinero real.
"""

import requests
import json
import os
from typing import Dict, Any

# Configuración
API_BASE_URL = "http://localhost:8000/api/v1"
TEST_CARDS = {
    "visa_success": "4242424242424242",
    "visa_decline": "4000000000000002",
    "insufficient_funds": "4000000000000995",
    "expired_card": "4000000000000069",
    "incorrect_cvc": "4000000000000127",
    "lost_card": "4000000000000987",
    "stolen_card": "4000000000000979",
    "fraud_high_risk": "4000000000004954",
    "fraud_always_blocked": "4100000000000019",
    "fraud_elevated": "4000000000009235"
}

def get_auth_token():
    """Obtener token de autenticación (simulado)"""
    # En un caso real, aquí harías login con Auth0
    return "Bearer your-test-token-here"

def create_test_plan(gym_id: int) -> Dict[str, Any]:
    """Crear un plan de prueba"""
    headers = {
        "Authorization": get_auth_token(),
        "X-Gym-ID": str(gym_id),
        "Content-Type": "application/json"
    }
    
    plan_data = {
        "name": "Plan de Prueba",
        "description": "Plan para testing de pagos",
        "price_cents": 2999,  # €29.99
        "currency": "EUR",
        "duration_days": 30,
        "billing_interval": "one_time",
        "is_active": True
    }
    
    response = requests.post(
        f"{API_BASE_URL}/memberships/plans",
        headers=headers,
        json=plan_data
    )
    
    if response.status_code == 201:
        return response.json()
    else:
        print(f"Error creando plan: {response.status_code} - {response.text}")
        return None

def test_payment_scenario(scenario_name: str, card_number: str, plan_id: int, gym_id: int):
    """Probar un escenario de pago específico"""
    print(f"\n🧪 Probando: {scenario_name}")
    print(f"💳 Tarjeta: {card_number}")
    print("-" * 50)
    
    # 1. Crear sesión de checkout
    headers = {
        "Authorization": get_auth_token(),
        "X-Gym-ID": str(gym_id),
        "Content-Type": "application/json"
    }
    
    purchase_data = {
        "plan_id": plan_id,
        "success_url": "http://localhost:3000/success",
        "cancel_url": "http://localhost:3000/cancel"
    }
    
    response = requests.post(
        f"{API_BASE_URL}/memberships/purchase",
        headers=headers,
        json=purchase_data
    )
    
    if response.status_code == 200:
        checkout_data = response.json()
        print(f"✅ Sesión de checkout creada: {checkout_data['session_id']}")
        print(f"🔗 URL de pago: {checkout_data['checkout_url']}")
        
        # Simular que el usuario completa el pago
        print(f"💡 Ahora usa la tarjeta {card_number} en: {checkout_data['checkout_url']}")
        
        # En un test real, aquí simularías el webhook de Stripe
        return checkout_data
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")
        return None

def simulate_webhook_payment(session_id: str, success: bool = True):
    """Simular webhook de pago completado"""
    print(f"\n🔔 Simulando webhook para sesión: {session_id}")
    
    # Simular confirmación de pago exitoso
    response = requests.post(
        f"{API_BASE_URL}/memberships/purchase/success",
        params={"session_id": session_id}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Pago procesado exitosamente")
        print(f"📅 Membresía expira: {result.get('membership_expires_at')}")
        return result
    else:
        print(f"❌ Error procesando pago: {response.status_code} - {response.text}")
        return None

def test_all_scenarios():
    """Probar todos los escenarios de pago"""
    print("🚀 Iniciando pruebas de pagos con Stripe")
    print("=" * 60)
    
    # Configuración de prueba
    gym_id = 1  # ID del gimnasio de prueba
    
    # Crear plan de prueba
    print("📋 Creando plan de prueba...")
    plan = create_test_plan(gym_id)
    if not plan:
        print("❌ No se pudo crear el plan de prueba")
        return
    
    plan_id = plan['id']
    print(f"✅ Plan creado: {plan['name']} (ID: {plan_id})")
    
    # Probar diferentes escenarios
    scenarios = [
        ("Pago Exitoso (Visa)", TEST_CARDS["visa_success"]),
        ("Pago Rechazado (Genérico)", TEST_CARDS["visa_decline"]),
        ("Fondos Insuficientes", TEST_CARDS["insufficient_funds"]),
        ("Tarjeta Expirada", TEST_CARDS["expired_card"]),
        ("CVC Incorrecto", TEST_CARDS["incorrect_cvc"]),
        ("Tarjeta Perdida", TEST_CARDS["lost_card"]),
        ("Tarjeta Robada", TEST_CARDS["stolen_card"]),
        ("Fraude - Riesgo Alto", TEST_CARDS["fraud_high_risk"]),
        ("Fraude - Siempre Bloqueado", TEST_CARDS["fraud_always_blocked"]),
        ("Fraude - Riesgo Elevado", TEST_CARDS["fraud_elevated"])
    ]
    
    results = []
    for scenario_name, card_number in scenarios:
        checkout_data = test_payment_scenario(scenario_name, card_number, plan_id, gym_id)
        if checkout_data:
            results.append({
                "scenario": scenario_name,
                "card": card_number,
                "session_id": checkout_data["session_id"],
                "checkout_url": checkout_data["checkout_url"]
            })
    
    # Mostrar resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE PRUEBAS")
    print("=" * 60)
    
    for result in results:
        print(f"🧪 {result['scenario']}")
        print(f"   💳 Tarjeta: {result['card']}")
        print(f"   🔗 URL: {result['checkout_url']}")
        print()
    
    print("💡 INSTRUCCIONES:")
    print("1. Visita cada URL de checkout")
    print("2. Usa la tarjeta correspondiente")
    print("3. Observa el comportamiento esperado")
    print("4. Verifica los logs en tu aplicación")
    print()
    print("📚 Documentación: https://stripe.com/docs/testing")

def test_specific_card():
    """Probar una tarjeta específica interactivamente"""
    print("\n🎯 Prueba de Tarjeta Específica")
    print("=" * 40)
    
    # Mostrar tarjetas disponibles
    print("Tarjetas disponibles:")
    for i, (name, card) in enumerate(TEST_CARDS.items(), 1):
        print(f"{i}. {name}: {card}")
    
    try:
        choice = int(input("\nSelecciona una tarjeta (número): ")) - 1
        card_names = list(TEST_CARDS.keys())
        
        if 0 <= choice < len(card_names):
            card_name = card_names[choice]
            card_number = TEST_CARDS[card_name]
            
            gym_id = int(input("ID del gimnasio: "))
            plan_id = int(input("ID del plan: "))
            
            checkout_data = test_payment_scenario(card_name, card_number, plan_id, gym_id)
            
            if checkout_data:
                print(f"\n✅ Prueba configurada exitosamente")
                print(f"🔗 Visita: {checkout_data['checkout_url']}")
                print(f"💳 Usa la tarjeta: {card_number}")
        else:
            print("❌ Selección inválida")
            
    except ValueError:
        print("❌ Entrada inválida")

def main():
    """Función principal"""
    print("🏋️ Stripe Payment Testing Tool")
    print("=" * 40)
    print("1. Probar todos los escenarios")
    print("2. Probar tarjeta específica")
    print("3. Mostrar tarjetas de prueba")
    print("4. Salir")
    
    while True:
        try:
            choice = input("\nSelecciona una opción: ").strip()
            
            if choice == "1":
                test_all_scenarios()
            elif choice == "2":
                test_specific_card()
            elif choice == "3":
                print("\n💳 TARJETAS DE PRUEBA DE STRIPE")
                print("=" * 40)
                for name, card in TEST_CARDS.items():
                    print(f"{name}: {card}")
            elif choice == "4":
                print("👋 ¡Hasta luego!")
                break
            else:
                print("❌ Opción inválida")
                
        except KeyboardInterrupt:
            print("\n👋 ¡Hasta luego!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main() 