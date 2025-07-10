#!/usr/bin/env python3
"""
Script para probar el endpoint administrativo de creación de links de pago.
Permite a los administradores crear links personalizados para usuarios específicos.
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any

# Configuración
API_BASE_URL = "http://localhost:8000/api/v1"

def get_admin_token():
    """Obtener token de administrador (simulado)"""
    # En un caso real, aquí harías login con Auth0 como administrador
    return "Bearer your-admin-token-here"

def create_admin_payment_link(
    user_id: int,
    plan_id: int,
    gym_id: int,
    notes: str = None,
    expires_in_hours: int = 24,
    success_url: str = None,
    cancel_url: str = None
) -> Dict[str, Any]:
    """Crear un link de pago administrativo"""
    
    headers = {
        "Authorization": get_admin_token(),
        "X-Gym-ID": str(gym_id),
        "Content-Type": "application/json"
    }
    
    payment_data = {
        "user_id": user_id,
        "plan_id": plan_id,
        "notes": notes,
        "expires_in_hours": expires_in_hours,
        "success_url": success_url,
        "cancel_url": cancel_url
    }
    
    # Remover campos None
    payment_data = {k: v for k, v in payment_data.items() if v is not None}
    
    print(f"🔗 Creando link de pago administrativo...")
    print(f"👤 Usuario ID: {user_id}")
    print(f"📋 Plan ID: {plan_id}")
    print(f"🏋️ Gym ID: {gym_id}")
    print(f"📝 Notas: {notes or 'Sin notas'}")
    print(f"⏰ Expira en: {expires_in_hours} horas")
    print("-" * 50)
    
    response = requests.post(
        f"{API_BASE_URL}/memberships/admin/create-payment-link",
        headers=headers,
        json=payment_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Link creado exitosamente!")
        print(f"🔗 URL de pago: {result['checkout_url']}")
        print(f"📧 Usuario: {result['user_email']}")
        print(f"👤 Nombre: {result['user_name']}")
        print(f"💰 Plan: {result['plan_name']} - €{result['price_amount']}")
        print(f"⏰ Expira: {result['expires_at']}")
        print(f"👨‍💼 Creado por: {result['created_by_admin']}")
        if result.get('notes'):
            print(f"📝 Notas: {result['notes']}")
        return result
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"📄 Respuesta: {response.text}")
        return None

def list_users(gym_id: int) -> Dict[str, Any]:
    """Listar usuarios del gimnasio para seleccionar"""
    headers = {
        "Authorization": get_admin_token(),
        "X-Gym-ID": str(gym_id),
        "Content-Type": "application/json"
    }
    
    # Este endpoint debería existir en tu API
    response = requests.get(
        f"{API_BASE_URL}/users/gym-participants",
        headers=headers,
        params={"limit": 10}
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Error obteniendo usuarios: {response.status_code}")
        return {"users": []}

def list_plans(gym_id: int) -> Dict[str, Any]:
    """Listar planes de membresía disponibles"""
    headers = {
        "Authorization": get_admin_token(),
        "X-Gym-ID": str(gym_id),
        "Content-Type": "application/json"
    }
    
    response = requests.get(
        f"{API_BASE_URL}/memberships/plans",
        headers=headers,
        params={"active_only": True}
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Error obteniendo planes: {response.status_code}")
        return {"plans": []}

def test_scenarios():
    """Probar diferentes escenarios de uso"""
    print("🧪 Probando escenarios de links administrativos")
    print("=" * 60)
    
    gym_id = 1  # ID del gimnasio de prueba
    
    # Escenario 1: Link estándar con expiración de 24 horas
    print("\n📋 Escenario 1: Link estándar")
    result1 = create_admin_payment_link(
        user_id=123,
        plan_id=456,
        gym_id=gym_id,
        notes="Pago de membresía mensual - contacto telefónico",
        expires_in_hours=24
    )
    
    # Escenario 2: Link urgente con expiración corta
    print("\n📋 Escenario 2: Link urgente (2 horas)")
    result2 = create_admin_payment_link(
        user_id=124,
        plan_id=457,
        gym_id=gym_id,
        notes="Pago urgente - oferta especial válida hoy",
        expires_in_hours=2,
        success_url="https://mi-gym.com/success-urgente",
        cancel_url="https://mi-gym.com/cancel-urgente"
    )
    
    # Escenario 3: Link para nuevo usuario (sin notas)
    print("\n📋 Escenario 3: Nuevo usuario")
    result3 = create_admin_payment_link(
        user_id=125,
        plan_id=458,
        gym_id=gym_id,
        expires_in_hours=72  # 3 días para decidir
    )
    
    # Escenario 4: Link con URLs personalizadas
    print("\n📋 Escenario 4: URLs personalizadas")
    result4 = create_admin_payment_link(
        user_id=126,
        plan_id=459,
        gym_id=gym_id,
        notes="Cliente VIP - atención personalizada",
        expires_in_hours=48,
        success_url="https://mi-gym.com/vip/success",
        cancel_url="https://mi-gym.com/vip/cancel"
    )
    
    # Mostrar resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE LINKS CREADOS")
    print("=" * 60)
    
    results = [result1, result2, result3, result4]
    for i, result in enumerate(results, 1):
        if result:
            expires_at = datetime.fromisoformat(result['expires_at'].replace('Z', '+00:00'))
            time_left = expires_at - datetime.now().replace(tzinfo=expires_at.tzinfo)
            
            print(f"\n🔗 Link {i}:")
            print(f"   👤 Usuario: {result['user_email']}")
            print(f"   💰 Plan: {result['plan_name']}")
            print(f"   ⏰ Expira en: {time_left}")
            print(f"   🔗 URL: {result['checkout_url']}")

def interactive_link_creation():
    """Crear link de forma interactiva"""
    print("\n🎯 Creación Interactiva de Link de Pago")
    print("=" * 50)
    
    try:
        # Solicitar datos básicos
        gym_id = int(input("ID del gimnasio: "))
        
        # Listar usuarios disponibles
        print("\n👥 Obteniendo usuarios del gimnasio...")
        users_data = list_users(gym_id)
        users = users_data.get('users', [])
        
        if users:
            print("\nUsuarios disponibles:")
            for i, user in enumerate(users[:10], 1):
                print(f"{i}. {user.get('email', 'Sin email')} - {user.get('first_name', '')} {user.get('last_name', '')}")
            
            user_choice = int(input("\nSelecciona un usuario (número): ")) - 1
            if 0 <= user_choice < len(users):
                user_id = users[user_choice]['id']
                print(f"✅ Usuario seleccionado: {users[user_choice].get('email')}")
            else:
                user_id = int(input("ID del usuario: "))
        else:
            user_id = int(input("ID del usuario: "))
        
        # Listar planes disponibles
        print("\n📋 Obteniendo planes de membresía...")
        plans_data = list_plans(gym_id)
        plans = plans_data.get('plans', [])
        
        if plans:
            print("\nPlanes disponibles:")
            for i, plan in enumerate(plans, 1):
                price = plan['price_cents'] / 100
                print(f"{i}. {plan['name']} - €{price:.2f} ({plan['billing_interval']})")
            
            plan_choice = int(input("\nSelecciona un plan (número): ")) - 1
            if 0 <= plan_choice < len(plans):
                plan_id = plans[plan_choice]['id']
                print(f"✅ Plan seleccionado: {plans[plan_choice]['name']}")
            else:
                plan_id = int(input("ID del plan: "))
        else:
            plan_id = int(input("ID del plan: "))
        
        # Datos opcionales
        notes = input("Notas (opcional): ").strip() or None
        expires_in_hours = int(input("Expira en horas (default 24): ") or "24")
        success_url = input("URL de éxito (opcional): ").strip() or None
        cancel_url = input("URL de cancelación (opcional): ").strip() or None
        
        # Crear el link
        result = create_admin_payment_link(
            user_id=user_id,
            plan_id=plan_id,
            gym_id=gym_id,
            notes=notes,
            expires_in_hours=expires_in_hours,
            success_url=success_url,
            cancel_url=cancel_url
        )
        
        if result:
            print(f"\n✅ ¡Link creado exitosamente!")
            print(f"📋 Copia este link y envíalo al usuario:")
            print(f"🔗 {result['checkout_url']}")
            
    except ValueError as e:
        print(f"❌ Entrada inválida: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Función principal"""
    print("🏋️ Herramienta de Links de Pago Administrativos")
    print("=" * 50)
    print("1. Probar escenarios predefinidos")
    print("2. Crear link interactivamente")
    print("3. Listar usuarios de un gimnasio")
    print("4. Listar planes de un gimnasio")
    print("5. Salir")
    
    while True:
        try:
            choice = input("\nSelecciona una opción: ").strip()
            
            if choice == "1":
                test_scenarios()
            elif choice == "2":
                interactive_link_creation()
            elif choice == "3":
                gym_id = int(input("ID del gimnasio: "))
                users_data = list_users(gym_id)
                users = users_data.get('users', [])
                print(f"\n👥 Usuarios en gimnasio {gym_id}:")
                for user in users:
                    print(f"- ID: {user['id']}, Email: {user.get('email', 'Sin email')}, Nombre: {user.get('first_name', '')} {user.get('last_name', '')}")
            elif choice == "4":
                gym_id = int(input("ID del gimnasio: "))
                plans_data = list_plans(gym_id)
                plans = plans_data.get('plans', [])
                print(f"\n📋 Planes en gimnasio {gym_id}:")
                for plan in plans:
                    price = plan['price_cents'] / 100
                    print(f"- ID: {plan['id']}, Nombre: {plan['name']}, Precio: €{price:.2f}, Tipo: {plan['billing_interval']}")
            elif choice == "5":
                print("👋 ¡Hasta luego!")
                break
            else:
                print("❌ Opción inválida")
                
        except KeyboardInterrupt:
            print("\n👋 ¡Hasta luego!")
            break
        except ValueError as e:
            print(f"❌ Entrada inválida: {e}")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main() 