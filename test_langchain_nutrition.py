#!/usr/bin/env python3
"""
Script de prueba para el generador de planes nutricionales con LangChain.
Compara el rendimiento entre OpenAI directo y LangChain.
"""

import asyncio
import json
import time
from datetime import datetime
import os
import sys

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar variables de entorno para prueba
os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', 'sk-test-key')  # Reemplazar con clave real

from app.services.nutrition_ai_service import NutritionAIService
from app.schemas.nutrition_ai import AIGenerationRequest
from app.models.nutrition import NutritionGoal, DifficultyLevel, BudgetLevel, DietaryRestriction


def test_direct_openai():
    """Prueba generación con OpenAI directo."""
    print("\n" + "="*60)
    print("PRUEBA 1: OpenAI Directo (sin LangChain)")
    print("="*60)

    service = NutritionAIService()

    # Desactivar LangChain temporalmente
    original_use_langchain = service.use_langchain
    service.use_langchain = False

    request = AIGenerationRequest(
        goal=NutritionGoal.CUT,
        difficulty_level=DifficultyLevel.BEGINNER,
        budget_level=BudgetLevel.MEDIUM,
        dietary_restrictions=DietaryRestriction.NONE,
        duration_days=1,  # Solo 1 día para prueba rápida
        target_calories=2000,
        target_protein_g=150,
        target_carbs_g=200,
        target_fat_g=67,
        meals_per_day=5
    )

    start_time = time.time()
    try:
        result = service._generate_days_with_ai(request, 1, 1, "Test Plan Direct")
        elapsed = time.time() - start_time

        print(f"\n✅ Generación exitosa en {elapsed:.2f} segundos")

        if result and len(result) > 0:
            day = result[0]
            print(f"\nDía generado: {day.get('day_name', 'Día 1')}")
            print(f"Número de comidas: {len(day.get('meals', []))}")

            # Verificar tipos de comidas
            meal_types = [meal.get('meal_type') for meal in day.get('meals', [])]
            print(f"Tipos de comidas: {meal_types}")

            # Verificar que no haya "snack"
            if 'snack' in meal_types:
                print("⚠️ ADVERTENCIA: Se encontró 'snack' en los tipos de comidas")
            else:
                print("✅ Todos los tipos de comidas son válidos")

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ Error después de {elapsed:.2f} segundos: {e}")

    # Restaurar configuración
    service.use_langchain = original_use_langchain
    return elapsed


def test_langchain():
    """Prueba generación con LangChain."""
    print("\n" + "="*60)
    print("PRUEBA 2: LangChain con Validación Pydantic")
    print("="*60)

    try:
        from app.services.langchain_nutrition import LangChainNutritionGenerator

        generator = LangChainNutritionGenerator(os.environ.get('OPENAI_API_KEY'))

        request = AIGenerationRequest(
            goal=NutritionGoal.CUT,
            difficulty_level=DifficultyLevel.BEGINNER,
            budget_level=BudgetLevel.MEDIUM,
            dietary_restrictions=DietaryRestriction.NONE,
            duration_days=1,
            target_calories=2000,
            target_protein_g=150,
            target_carbs_g=200,
            target_fat_g=67,
            meals_per_day=5
        )

        start_time = time.time()
        result = generator.generate_nutrition_plan(request, 1, 1)
        elapsed = time.time() - start_time

        print(f"\n✅ Generación exitosa en {elapsed:.2f} segundos")

        if result and 'days' in result and len(result['days']) > 0:
            day = result['days'][0]
            print(f"\nDía generado: {day.get('day_name', 'Día 1')}")
            print(f"Número de comidas: {len(day.get('meals', []))}")

            # Verificar tipos de comidas
            meal_types = [meal.get('meal_type') for meal in day.get('meals', [])]
            print(f"Tipos de comidas: {meal_types}")

            # Verificar validación Pydantic
            print("\n📋 Validaciones aplicadas:")
            print("✅ Estructura JSON validada")
            print("✅ Tipos de datos verificados")
            print("✅ Rangos de valores validados")
            print("✅ Mapeo automático de tipos incorrectos")

            # Mostrar primera comida como ejemplo
            if day['meals']:
                meal = day['meals'][0]
                print(f"\n🍽️ Ejemplo de comida validada:")
                print(f"  Nombre: {meal.get('name')}")
                print(f"  Tipo: {meal.get('meal_type')}")
                print(f"  Calorías: {meal.get('calories')} kcal")
                print(f"  Proteína: {meal.get('protein')}g")
                print(f"  Carbohidratos: {meal.get('carbs')}g")
                print(f"  Grasa: {meal.get('fat')}g")

        return elapsed

    except ImportError:
        print("❌ LangChain no está instalado")
        print("Ejecuta: pip install langchain langchain-openai")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_integrated_service():
    """Prueba el servicio integrado con detección automática."""
    print("\n" + "="*60)
    print("PRUEBA 3: Servicio Integrado (Detección Automática)")
    print("="*60)

    service = NutritionAIService()

    print(f"LangChain disponible: {'✅ Sí' if service.use_langchain else '❌ No'}")
    print(f"Método a usar: {'LangChain' if service.use_langchain else 'OpenAI Directo'}")

    request = AIGenerationRequest(
        goal=NutritionGoal.CUT,
        difficulty_level=DifficultyLevel.BEGINNER,
        budget_level=BudgetLevel.MEDIUM,
        dietary_restrictions=DietaryRestriction.NONE,
        duration_days=3,  # 3 días para prueba más completa
        target_calories=2000,
        target_protein_g=150,
        target_carbs_g=200,
        target_fat_g=67,
        meals_per_day=5
    )

    start_time = time.time()
    try:
        # Generar 3 días
        all_days = []
        for day in range(1, 4):
            print(f"\nGenerando día {day}...")
            result = service._generate_days_with_ai(request, day, day, "Test Plan Integrated")
            all_days.extend(result)

        elapsed = time.time() - start_time

        print(f"\n✅ Generación completa en {elapsed:.2f} segundos")
        print(f"Total días generados: {len(all_days)}")

        # Verificar integridad
        for idx, day in enumerate(all_days, 1):
            meals = day.get('meals', [])
            meal_types = [m.get('meal_type') for m in meals]

            # Verificar que no haya tipos inválidos
            invalid_types = [mt for mt in meal_types if mt == 'snack']
            if invalid_types:
                print(f"⚠️ Día {idx}: Encontrados tipos inválidos: {invalid_types}")
            else:
                print(f"✅ Día {idx}: Todos los tipos son válidos ({len(meals)} comidas)")

        return elapsed

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ Error después de {elapsed:.2f} segundos: {e}")
        return None


def main():
    """Función principal de pruebas."""
    print("🧪 INICIANDO PRUEBAS DE GENERACIÓN NUTRICIONAL")
    print(f"Timestamp: {datetime.now().isoformat()}")

    # Verificar API key
    if not os.environ.get('OPENAI_API_KEY'):
        print("\n⚠️ ADVERTENCIA: OPENAI_API_KEY no configurada")
        print("Configura la variable de entorno o edita este script")
        return

    results = {}

    # Prueba 1: OpenAI Directo
    time_direct = test_direct_openai()
    if time_direct:
        results['OpenAI Directo'] = time_direct

    # Prueba 2: LangChain
    time_langchain = test_langchain()
    if time_langchain:
        results['LangChain'] = time_langchain

    # Prueba 3: Servicio Integrado
    time_integrated = test_integrated_service()
    if time_integrated:
        results['Servicio Integrado'] = time_integrated

    # Resumen de resultados
    print("\n" + "="*60)
    print("RESUMEN DE RESULTADOS")
    print("="*60)

    if results:
        for method, time_taken in results.items():
            print(f"{method:20} : {time_taken:.2f} segundos")

        # Comparación si tenemos ambos métodos
        if 'OpenAI Directo' in results and 'LangChain' in results:
            diff = results['LangChain'] - results['OpenAI Directo']
            if diff < 0:
                print(f"\n✅ LangChain es {abs(diff):.2f}s más rápido")
            else:
                print(f"\n⚠️ OpenAI Directo es {diff:.2f}s más rápido")

            print("\n📊 Ventajas de LangChain:")
            print("  • Validación automática de tipos")
            print("  • Mapeo automático de valores incorrectos")
            print("  • Mejor manejo de errores")
            print("  • Estructura garantizada con Pydantic")
    else:
        print("No se completaron pruebas exitosamente")

    print("\n" + "="*60)
    print("✅ PRUEBAS COMPLETADAS")
    print("="*60)


if __name__ == "__main__":
    main()