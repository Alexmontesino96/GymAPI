#!/usr/bin/env python3
"""
Test del endpoint de nutrición con IA en producción
"""

import requests
import json
import time
from datetime import datetime

# Configuración
API_URL = "https://gymapi-eh6m.onrender.com/api/v1/nutrition/plans/generate"
TOKEN = "Bearer YOUR_TOKEN_HERE"  # Reemplazar con token real
GYM_ID = 4

def test_generate_plan():
    """Test de generación de plan con IA"""
    print("\n" + "="*60)
    print("TEST ENDPOINT: Generación de Plan Nutricional con IA")
    print("="*60)

    # Datos de prueba
    payload = {
        "title": "Plan de Definición TEST",
        "goal": "cut",  # cut, bulk, maintenance, etc.
        "target_calories": 2000,
        "duration_days": 7,
        "difficulty_level": "intermediate",
        "budget_level": "medium",
        "meals_per_day": 5,
        "dietary_restrictions": [],
        "exclude_ingredients": ["maní"],
        "allergies": [],
        "user_context": {
            "weight": 70,
            "height": 175,
            "age": 30,
            "activity_level": "moderate"
        },
        "prompt": "Plan enfocado en definición muscular con comidas fáciles de preparar",
        "temperature": 0.7,
        "max_tokens": 3500
    }

    headers = {
        "Authorization": TOKEN,
        "Content-Type": "application/json",
        "X-Gym-Id": str(GYM_ID)
    }

    print(f"\n📍 URL: {API_URL}")
    print(f"📊 Payload: {json.dumps(payload, indent=2)}")

    try:
        print(f"\n⏱️  Enviando petición... {datetime.now().strftime('%H:%M:%S')}")
        start_time = time.time()

        response = requests.post(API_URL, json=payload, headers=headers, timeout=60)

        elapsed_time = time.time() - start_time
        print(f"⏱️  Respuesta recibida en {elapsed_time:.2f} segundos")

        print(f"\n📡 Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("\n✅ PLAN GENERADO EXITOSAMENTE!")

            print(f"\n📋 Resumen del Plan:")
            print(f"  - ID: {data.get('plan_id', 'N/A')}")
            print(f"  - Nombre: {data.get('name', 'N/A')}")
            print(f"  - Días: {data.get('total_days', 0)}")
            print(f"  - Comidas totales: {data.get('total_meals', 0)}")
            print(f"  - Calorías objetivo: {data.get('target_calories', 0)}")

            if 'ai_metadata' in data:
                print(f"\n🤖 Metadata IA:")
                print(f"  - Modelo: {data['ai_metadata'].get('model', 'N/A')}")
                print(f"  - Tokens usados: {data['ai_metadata'].get('total_tokens', 'N/A')}")
                print(f"  - Tiempo de generación: {data.get('generation_time_ms', 0)}ms")
                print(f"  - Costo estimado: ${data.get('cost_estimate_usd', 0):.4f} USD")

            return True

        else:
            print(f"\n❌ ERROR: {response.status_code}")

            try:
                error_data = response.json()
                print(f"Mensaje: {error_data.get('detail', 'Sin mensaje de error')}")
            except:
                print(f"Respuesta: {response.text[:500]}")

            return False

    except requests.exceptions.Timeout:
        print("\n❌ ERROR: Timeout - La petición tardó más de 60 segundos")
        return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

def main():
    """Ejecutar test"""
    print("\n" + "="*60)
    print("INICIANDO TEST DE ENDPOINT EN PRODUCCIÓN")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*60)

    print("\n⚠️  NOTA: Asegúrate de configurar el TOKEN en el script")
    print("⚠️  El endpoint puede tardar 10-30 segundos en responder")

    # Ejecutar test
    success = test_generate_plan()

    print("\n" + "="*60)
    if success:
        print("✅ TEST COMPLETADO EXITOSAMENTE")
    else:
        print("❌ TEST FALLÓ")
    print("="*60)

    return 0 if success else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())