#!/usr/bin/env python3
"""
Script de ejemplo para probar el sistema de planes nutricionales.
"""

import requests
import json
from datetime import datetime, timedelta

# Configuración del API
BASE_URL = "https://gymapi-eh6m.onrender.com/api/v1"
HEADERS = {
    "Content-Type": "application/json",
    "X-Gym-ID": "1"  # Cambiar por el ID de tu gimnasio
}

def test_nutrition_system():
    """Función principal para probar el sistema de nutrición."""
    
    print("🍎 Probando Sistema de Planes Nutricionales")
    print("=" * 50)
    
    # 1. Obtener enums disponibles
    print("\n1. 📋 Obteniendo enums disponibles...")
    
    endpoints = [
        "/nutrition/enums/goals",
        "/nutrition/enums/difficulty-levels", 
        "/nutrition/enums/budget-levels",
        "/nutrition/enums/dietary-restrictions",
        "/nutrition/enums/meal-types"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS)
            if response.status_code == 200:
                print(f"✅ {endpoint}: {len(response.json())} opciones")
            else:
                print(f"❌ {endpoint}: Error {response.status_code}")
        except Exception as e:
            print(f"❌ {endpoint}: {str(e)}")
    
    # 2. Crear un plan nutricional de ejemplo
    print("\n2. 🍽️ Creando plan nutricional de ejemplo...")
    
    plan_data = {
        "title": "Plan de Volumen - Ejemplo",
        "description": "Plan nutricional para ganancia de masa muscular con comidas balanceadas",
        "goal": "bulk",
        "difficulty_level": "beginner",
        "budget_level": "medium",
        "dietary_restrictions": "none",
        "duration_days": 7,
        "is_recurring": True,
        "target_calories": 3000,
        "target_protein_g": 150.0,
        "target_carbs_g": 375.0,
        "target_fat_g": 100.0,
        "is_public": True,
        "tags": ["volumen", "principiante", "masa muscular"]
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/nutrition/plans",
            headers=HEADERS,
            json=plan_data
        )
        
        if response.status_code == 201:
            plan = response.json()
            plan_id = plan["id"]
            print(f"✅ Plan creado: ID {plan_id} - {plan['title']}")
            
            # 3. Crear plan diario
            print("\n3. 📅 Creando plan diario...")
            
            daily_plan_data = {
                "nutrition_plan_id": plan_id,
                "day_number": 1,
                "total_calories": 3000,
                "total_protein_g": 150.0,
                "total_carbs_g": 375.0,
                "total_fat_g": 100.0,
                "notes": "Día 1 del plan de volumen"
            }
            
            response = requests.post(
                f"{BASE_URL}/nutrition/plans/{plan_id}/days",
                headers=HEADERS,
                json=daily_plan_data
            )
            
            if response.status_code == 201:
                daily_plan = response.json()
                daily_plan_id = daily_plan["id"]
                print(f"✅ Plan diario creado: ID {daily_plan_id}")
                
                # 4. Crear comidas
                print("\n4. 🥗 Creando comidas del día...")
                
                meals = [
                    {
                        "daily_plan_id": daily_plan_id,
                        "meal_type": "breakfast",
                        "name": "Desayuno Energético",
                        "description": "Avena con frutas y proteína",
                        "preparation_time_minutes": 15,
                        "cooking_instructions": "1. Cocinar avena\n2. Añadir frutas\n3. Mezclar proteína",
                        "calories": 600,
                        "protein_g": 30.0,
                        "carbs_g": 75.0,
                        "fat_g": 15.0,
                        "order_in_day": 1
                    },
                    {
                        "daily_plan_id": daily_plan_id,
                        "meal_type": "lunch",
                        "name": "Almuerzo Completo",
                        "description": "Pollo con arroz y verduras",
                        "preparation_time_minutes": 30,
                        "cooking_instructions": "1. Cocinar pollo a la plancha\n2. Preparar arroz\n3. Saltear verduras",
                        "calories": 800,
                        "protein_g": 50.0,
                        "carbs_g": 80.0,
                        "fat_g": 20.0,
                        "order_in_day": 2
                    },
                    {
                        "daily_plan_id": daily_plan_id,
                        "meal_type": "dinner",
                        "name": "Cena Ligera",
                        "description": "Salmón con quinoa y ensalada",
                        "preparation_time_minutes": 25,
                        "cooking_instructions": "1. Cocinar salmón al horno\n2. Preparar quinoa\n3. Hacer ensalada",
                        "calories": 700,
                        "protein_g": 40.0,
                        "carbs_g": 60.0,
                        "fat_g": 25.0,
                        "order_in_day": 3
                    }
                ]
                
                meal_ids = []
                for meal_data in meals:
                    response = requests.post(
                        f"{BASE_URL}/nutrition/days/{daily_plan_id}/meals",
                        headers=HEADERS,
                        json=meal_data
                    )
                    
                    if response.status_code == 201:
                        meal = response.json()
                        meal_ids.append(meal["id"])
                        print(f"✅ Comida creada: {meal['name']} (ID: {meal['id']})")
                    else:
                        print(f"❌ Error creando comida: {response.status_code}")
                
                # 5. Añadir ingredientes a la primera comida
                if meal_ids:
                    print("\n5. 🥄 Añadiendo ingredientes al desayuno...")
                    
                    ingredients = [
                        {
                            "meal_id": meal_ids[0],
                            "name": "Avena en hojuelas",
                            "quantity": 80.0,
                            "unit": "gramos",
                            "alternatives": ["Avena instantánea", "Quinoa"],
                            "calories_per_serving": 300,
                            "protein_per_serving": 10.0,
                            "carbs_per_serving": 55.0,
                            "fat_per_serving": 6.0
                        },
                        {
                            "meal_id": meal_ids[0],
                            "name": "Plátano",
                            "quantity": 1.0,
                            "unit": "unidad",
                            "alternatives": ["Manzana", "Pera"],
                            "calories_per_serving": 100,
                            "protein_per_serving": 1.0,
                            "carbs_per_serving": 25.0,
                            "fat_per_serving": 0.5
                        },
                        {
                            "meal_id": meal_ids[0],
                            "name": "Proteína en polvo",
                            "quantity": 30.0,
                            "unit": "gramos",
                            "calories_per_serving": 120,
                            "protein_per_serving": 25.0,
                            "carbs_per_serving": 2.0,
                            "fat_per_serving": 1.0
                        }
                    ]
                    
                    for ingredient_data in ingredients:
                        response = requests.post(
                            f"{BASE_URL}/nutrition/meals/{meal_ids[0]}/ingredients",
                            headers=HEADERS,
                            json=ingredient_data
                        )
                        
                        if response.status_code == 201:
                            ingredient = response.json()
                            print(f"✅ Ingrediente añadido: {ingredient['name']}")
                        else:
                            print(f"❌ Error añadiendo ingrediente: {response.status_code}")
                
                # 6. Listar planes disponibles
                print("\n6. 📋 Listando planes disponibles...")
                
                response = requests.get(
                    f"{BASE_URL}/nutrition/plans?page=1&per_page=10",
                    headers=HEADERS
                )
                
                if response.status_code == 200:
                    plans_list = response.json()
                    print(f"✅ Encontrados {plans_list['total']} planes:")
                    for plan in plans_list['plans']:
                        print(f"   - {plan['title']} (Objetivo: {plan['goal']})")
                else:
                    print(f"❌ Error listando planes: {response.status_code}")
                
                # 7. Obtener plan con detalles
                print(f"\n7. 🔍 Obteniendo detalles del plan {plan_id}...")
                
                response = requests.get(
                    f"{BASE_URL}/nutrition/plans/{plan_id}",
                    headers=HEADERS
                )
                
                if response.status_code == 200:
                    plan_details = response.json()
                    print(f"✅ Plan: {plan_details['title']}")
                    print(f"   Objetivo: {plan_details['goal']}")
                    print(f"   Duración: {plan_details['duration_days']} días")
                    print(f"   Calorías objetivo: {plan_details['target_calories']}")
                else:
                    print(f"❌ Error obteniendo detalles: {response.status_code}")
                
                print(f"\n🎉 ¡Sistema de nutrición probado exitosamente!")
                print(f"📝 Plan creado con ID: {plan_id}")
                print(f"📅 Plan diario creado con ID: {daily_plan_id}")
                print(f"🍽️ {len(meal_ids)} comidas creadas")
                
            else:
                print(f"❌ Error creando plan diario: {response.status_code}")
                
        else:
            print(f"❌ Error creando plan: {response.status_code}")
            print(f"Respuesta: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def test_user_flow():
    """Probar el flujo de usuario (seguir plan y completar comidas)."""
    
    print("\n" + "=" * 50)
    print("👤 Probando flujo de usuario")
    print("=" * 50)
    
    # Nota: Este flujo requiere autenticación real
    print("⚠️  Para probar el flujo de usuario necesitas:")
    print("   1. Estar autenticado con un token válido")
    print("   2. Añadir el token a los headers")
    print("   3. Seguir un plan: POST /nutrition/plans/{id}/follow")
    print("   4. Ver plan de hoy: GET /nutrition/today")
    print("   5. Completar comida: POST /nutrition/meals/{id}/complete")

if __name__ == "__main__":
    print("🚀 Iniciando pruebas del sistema de nutrición...")
    
    try:
        test_nutrition_system()
        test_user_flow()
        
        print("\n✅ Todas las pruebas completadas!")
        print("\n📚 Próximos pasos:")
        print("   1. Implementar autenticación en el frontend")
        print("   2. Crear interfaz para entrenadores")
        print("   3. Desarrollar app móvil para usuarios")
        print("   4. Añadir notificaciones push")
        print("   5. Implementar analytics avanzados")
        
    except KeyboardInterrupt:
        print("\n⏹️  Pruebas interrumpidas por el usuario")
    except Exception as e:
        print(f"\n❌ Error general: {str(e)}") 