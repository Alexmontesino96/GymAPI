#!/usr/bin/env python3
"""
Test del endpoint de generación de planes con IA
"""

import os
import sys
import json
import traceback
from datetime import datetime

# Agregar el path del proyecto
sys.path.insert(0, '/Users/alexmontesino/GymApi')

# Configurar variables de entorno antes de importar
os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', 'postgresql://localhost/test')
os.environ['REDIS_URL'] = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
os.environ['AUTH0_DOMAIN'] = os.getenv('AUTH0_DOMAIN', 'test.auth0.com')
os.environ['AUTH0_API_AUDIENCE'] = os.getenv('AUTH0_API_AUDIENCE', 'test')
os.environ['CHAT_GPT_MODEL'] = os.getenv('CHAT_GPT_MODEL', 'test-key')

def test_nutrition_ai_service():
    """Test directo del servicio de IA"""
    print("\n" + "="*60)
    print("TEST: NutritionAIService")
    print("="*60)

    try:
        from app.services.nutrition_ai_service import NutritionAIService

        print("\n1. Intentando crear servicio...")
        service = NutritionAIService()
        print("   ✅ Servicio creado exitosamente")

        print(f"\n2. Verificando configuración:")
        print(f"   - API Key configurada: {bool(service.api_key)}")
        print(f"   - Cliente OpenAI: {service.client is not None}")
        print(f"   - Modelo: {service.model}")

        return True

    except Exception as e:
        print(f"\n   ❌ ERROR: {e}")
        print(f"\n   Tipo de error: {type(e).__name__}")
        print("\n   Stack trace:")
        traceback.print_exc()
        return False

def test_openai_client_direct():
    """Test directo del cliente OpenAI"""
    print("\n" + "="*60)
    print("TEST: OpenAI Client Directo")
    print("="*60)

    try:
        from openai import OpenAI

        print("\n1. Verificando parámetros del cliente OpenAI...")
        import inspect
        sig = inspect.signature(OpenAI.__init__)
        params = list(sig.parameters.keys())
        print(f"   Parámetros aceptados: {params}")

        if 'proxies' in params:
            print("   ⚠️ ALERTA: 'proxies' está en los parámetros!")
        else:
            print("   ✅ 'proxies' NO está en los parámetros")

        print("\n2. Creando cliente con api_key básico...")
        client = OpenAI(api_key="test-key")
        print("   ✅ Cliente creado exitosamente")

        return True

    except Exception as e:
        print(f"\n   ❌ ERROR: {e}")
        print(f"\n   Tipo de error: {type(e).__name__}")
        traceback.print_exc()
        return False

def test_endpoint_logic():
    """Test de la lógica del endpoint"""
    print("\n" + "="*60)
    print("TEST: Lógica del Endpoint")
    print("="*60)

    try:
        # Simular el contexto del endpoint
        from sqlalchemy.orm import Session
        from app.db.session import SessionLocal
        from app.schemas.nutrition import AIGenerationRequest, NutritionGoal

        print("\n1. Creando request de prueba...")
        request = AIGenerationRequest(
            title="Plan Test",
            goal=NutritionGoal.DEFINITION,
            target_calories=2000,
            duration_days=7,
            meals_per_day=5
        )
        print("   ✅ Request creado")

        print("\n2. Simulando creación del servicio en endpoint...")
        try:
            from app.services.nutrition_ai_service import NutritionAIService
            ai_service = NutritionAIService()
            print("   ✅ Servicio creado en contexto de endpoint")
        except Exception as e:
            print(f"   ❌ Error creando servicio: {e}")
            raise

        return True

    except Exception as e:
        print(f"\n   ❌ ERROR: {e}")
        print(f"\n   Tipo de error: {type(e).__name__}")
        traceback.print_exc()
        return False

def check_openai_version():
    """Verificar versión de OpenAI instalada"""
    print("\n" + "="*60)
    print("VERIFICACIÓN: Versión de OpenAI")
    print("="*60)

    try:
        import openai
        print(f"\n   Versión instalada: {openai.__version__}")

        # Verificar si es la versión esperada
        expected = "1.12.0"
        if openai.__version__ == expected:
            print(f"   ✅ Versión correcta ({expected})")
        else:
            print(f"   ⚠️ ALERTA: Se esperaba {expected}")

    except ImportError:
        print("   ❌ OpenAI no está instalado")

def main():
    """Ejecutar todos los tests"""
    print("\n" + "="*60)
    print("INICIANDO TESTS DE NUTRICIÓN IA")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*60)

    # Verificar versión
    check_openai_version()

    # Tests
    results = []
    results.append(("OpenAI Client Directo", test_openai_client_direct()))
    results.append(("NutritionAIService", test_nutrition_ai_service()))
    results.append(("Lógica del Endpoint", test_endpoint_logic()))

    # Resumen
    print("\n" + "="*60)
    print("RESUMEN DE TESTS")
    print("="*60)

    for name, passed in results:
        status = "✅ PASÓ" if passed else "❌ FALLÓ"
        print(f"  {name}: {status}")

    all_passed = all(r[1] for r in results)

    print("\n" + "="*60)
    if all_passed:
        print("✅ TODOS LOS TESTS PASARON")
    else:
        print("❌ ALGUNOS TESTS FALLARON")
    print("="*60)

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())