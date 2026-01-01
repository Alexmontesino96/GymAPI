#!/usr/bin/env python3
"""
Verificación rápida del fix de OpenAI
"""

import os
import sys

# Configurar entorno
os.environ['CHAT_GPT_MODEL'] = 'test-key'
os.environ['DATABASE_URL'] = 'postgresql://localhost/test'
os.environ['REDIS_URL'] = 'redis://localhost:6379/0'

def main():
    print("="*60)
    print("VERIFICACIÓN: Fix de OpenAI")
    print("="*60)

    try:
        # Test 1: Verificar versión
        import openai
        print(f"\n1. Versión de OpenAI: {openai.__version__}")
        if openai.__version__ >= "1.61.0":
            print("   ✅ Versión actualizada correctamente")
        else:
            print("   ⚠️ Versión antigua detectada")

        # Test 2: Crear cliente
        from openai import OpenAI
        print("\n2. Creando cliente OpenAI...")
        client = OpenAI(api_key="test-key")
        print("   ✅ Cliente creado sin error de 'proxies'")

        # Test 3: Crear servicio
        from app.services.nutrition_ai_service import NutritionAIService
        print("\n3. Creando NutritionAIService...")
        service = NutritionAIService()
        print("   ✅ Servicio creado exitosamente")
        print(f"   - API Key configurada: {bool(service.api_key)}")
        print(f"   - Cliente creado: {service.client is not None}")

        print("\n" + "="*60)
        print("✅ TODAS LAS VERIFICACIONES PASARON")
        print("="*60)
        return 0

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\n" + "="*60)
        print("❌ VERIFICACIÓN FALLIDA")
        print("="*60)
        return 1

if __name__ == "__main__":
    sys.exit(main())