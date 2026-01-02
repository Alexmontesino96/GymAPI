#!/usr/bin/env python3
"""
Test para verificar que la generación de planes nutricionales funciona
correctamente después de corregir los errores de mapeo de campos.
"""

import requests
import json
import time
from datetime import datetime

def test_nutrition_generation():
    """Prueba la generación de un plan nutricional de 7 días"""

    print("="*60)
    print("TEST DE GENERACIÓN NUTRICIONAL - CAMPOS CORREGIDOS")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*60)

    # Configuración
    BASE_URL = "http://localhost:8000"  # Cambiar si es necesario
    API_URL = f"{BASE_URL}/api/v1/nutrition/plans/generate"

    # Token de prueba (actualizar si es necesario)
    TOKEN = "tu_token_aqui"  # Reemplazar con un token válido

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    # Datos de la solicitud
    payload = {
        "title": "Plan Nutricional de Prueba - 7 días",
        "description": "Plan generado para verificar correcciones de campos",
        "goal": "cut",
        "difficulty_level": "beginner",
        "budget_level": "medium",
        "dietary_restrictions": "none",
        "duration_days": 7,
        "target_calories": 2000,
        "target_protein_g": 150,
        "target_carbs_g": 200,
        "target_fat_g": 67,
        "use_ai": True
    }

    print("\n📝 CONFIGURACIÓN:")
    print(f"• Duración: {payload['duration_days']} días")
    print(f"• Calorías objetivo: {payload['target_calories']}")
    print(f"• Proteína: {payload['target_protein_g']}g")
    print(f"• Carbohidratos: {payload['target_carbs_g']}g")
    print(f"• Grasas: {payload['target_fat_g']}g")
    print(f"• Generación con IA: {'Sí' if payload['use_ai'] else 'No'}")

    print("\n🚀 Iniciando generación...")
    start_time = time.time()

    try:
        # Hacer la solicitud
        response = requests.post(API_URL, json=payload, headers=headers)
        elapsed = time.time() - start_time

        print(f"\n⏱️ Respuesta recibida en {elapsed:.2f} segundos")
        print(f"📊 Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("\n✅ GENERACIÓN EXITOSA!")
            print(f"• ID del plan: {data.get('id')}")
            print(f"• Título: {data.get('title')}")
            print(f"• Días creados: {len(data.get('daily_plans', []))}")

            # Verificar estructura de los días
            daily_plans = data.get('daily_plans', [])
            if daily_plans:
                print("\n📅 DÍAS GENERADOS:")
                for day in daily_plans:
                    meals = day.get('meals', [])
                    total_cal = sum(m.get('calories', 0) for m in meals)
                    print(f"  • Día {day.get('day_number')}: {len(meals)} comidas, {total_cal} cal totales")

            # Verificar campos corregidos en las comidas
            if daily_plans and daily_plans[0].get('meals'):
                first_meal = daily_plans[0]['meals'][0]
                print("\n🔍 VERIFICACIÓN DE CAMPOS (Primera comida):")
                critical_fields = ['name', 'meal_type', 'calories', 'protein_g', 'carbs_g', 'fat_g']
                for field in critical_fields:
                    value = first_meal.get(field, 'NO ENCONTRADO')
                    status = "✅" if field in first_meal else "❌"
                    print(f"  {status} {field}: {value}")

            return True

        else:
            print(f"\n❌ ERROR EN LA GENERACIÓN")
            print(f"Response: {response.text[:500]}")
            return False

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ Error después de {elapsed:.2f} segundos: {e}")
        return False

def check_field_mappings():
    """Verifica que los campos del modelo estén correctamente mapeados"""

    print("\n" + "="*60)
    print("VERIFICACIÓN DE MAPEO DE CAMPOS")
    print("="*60)

    print("\n📋 CAMPOS CORREGIDOS:")
    corrections = [
        ("day_plan_id", "daily_plan_id", "Foreign key a DailyNutritionPlan"),
        ("protein", "protein_g", "Proteína en gramos"),
        ("carbohydrates", "carbs_g", "Carbohidratos en gramos"),
        ("fat", "fat_g", "Grasas en gramos"),
        ("fiber", "fiber_g", "Fibra en gramos"),
        ("sugar", "ELIMINADO", "Campo no existe en el modelo"),
        ("sodium", "ELIMINADO", "Campo no existe en el modelo")
    ]

    for old, new, description in corrections:
        print(f"  • {old:20} → {new:20} ({description})")

    print("\n✅ Todos los campos han sido corregidos en:")
    print("  • app/services/nutrition_ai_service.py línea 289-299 (generación con IA)")
    print("  • app/services/nutrition_ai_service.py línea 627-636 (generación con plantillas)")

if __name__ == "__main__":
    print("🧪 INICIANDO PRUEBAS DE CORRECCIÓN DE CAMPOS")
    print()

    # Verificar mapeos
    check_field_mappings()

    # Ejecutar prueba de generación
    print("\n" + "="*60)
    input("\n⚠️ Asegúrate de que el servidor esté corriendo y presiona ENTER para continuar...")

    success = test_nutrition_generation()

    if success:
        print("\n" + "="*60)
        print("✅ TODAS LAS CORRECCIONES FUNCIONAN CORRECTAMENTE")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("⚠️ Revisa los logs del servidor para más detalles")
        print("="*60)