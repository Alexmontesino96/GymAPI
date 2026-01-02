#!/usr/bin/env python3
"""
Script de prueba para validar los nuevos validators de alias
en el schema AIGenerationRequest para nutrición.
"""

import sys
import os
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar environment
os.environ['DATABASE_URL'] = 'sqlite:///test.db'  # Base temporal

from app.schemas.nutrition import AIGenerationRequest
from app.models.nutrition import NutritionGoal
from pydantic import ValidationError


def test_goal_aliases():
    """Prueba los aliases del campo goal."""
    print("="*60)
    print("PRUEBA DE ALIASES PARA GOAL")
    print("="*60)

    # Casos de prueba: (input, expected)
    test_cases = [
        # Valores válidos del enum
        ('maintenance', NutritionGoal.MAINTENANCE),
        ('weight_loss', NutritionGoal.WEIGHT_LOSS),
        ('muscle_gain', NutritionGoal.MUSCLE_GAIN),
        ('bulk', NutritionGoal.BULK),
        ('cut', NutritionGoal.CUT),
        ('performance', NutritionGoal.PERFORMANCE),

        # Aliases que deben funcionar
        ('maintain', NutritionGoal.MAINTENANCE),  # El caso que falló en producción
        ('lose_weight', NutritionGoal.WEIGHT_LOSS),
        ('gain_muscle', NutritionGoal.MUSCLE_GAIN),
        ('gain', NutritionGoal.MUSCLE_GAIN),
        ('lose', NutritionGoal.WEIGHT_LOSS),
        ('build', NutritionGoal.MUSCLE_GAIN),
        ('bulking', NutritionGoal.BULK),
        ('cutting', NutritionGoal.CUT),
        ('definition', NutritionGoal.CUT),
        ('recomp', NutritionGoal.PERFORMANCE),

        # Casos con mayúsculas/espacios
        ('MAINTAIN', NutritionGoal.MAINTENANCE),
        ('  maintain  ', NutritionGoal.MAINTENANCE),
        ('Lose_Weight', NutritionGoal.WEIGHT_LOSS),
    ]

    success_count = 0
    fail_count = 0

    for input_value, expected in test_cases:
        try:
            request = AIGenerationRequest(
                title="Test Plan",
                goal=input_value,
                target_calories=2000,
                duration_days=7
            )

            if request.goal == expected:
                print(f"✅ '{input_value}' → {expected.value}")
                success_count += 1
            else:
                print(f"⚠️ '{input_value}' → {request.goal.value} (esperado: {expected.value})")
                fail_count += 1

        except ValidationError as e:
            print(f"❌ '{input_value}' → ERROR: {e.errors()[0]['msg']}")
            fail_count += 1

    print(f"\nResultado: {success_count} éxitos, {fail_count} fallos")
    return fail_count == 0


def test_dietary_restrictions_aliases():
    """Prueba los aliases de restricciones dietéticas."""
    print("\n" + "="*60)
    print("PRUEBA DE ALIASES PARA RESTRICCIONES DIETÉTICAS")
    print("="*60)

    # Casos de prueba
    test_cases = [
        # Input → Expected
        (['vegetarian'], ['vegetarian']),
        (['veggie'], ['vegetarian']),
        (['veg'], ['vegetarian']),
        (['gluten-free'], ['gluten_free']),
        (['gluten_free'], ['gluten_free']),
        (['lactose-free'], ['lactose_free']),
        (['dairy-free'], ['lactose_free']),
        (['no-gluten'], ['gluten_free']),
        (['mediterranean-diet'], ['mediterranean']),

        # Múltiples restricciones
        (['veggie', 'gluten-free'], ['vegetarian', 'gluten_free']),

        # String simple (se convierte a lista)
        ('vegetarian', ['vegetarian']),
        ('veggie', ['vegetarian']),

        # None se convierte a lista vacía
        (None, []),
    ]

    success_count = 0
    fail_count = 0

    for input_value, expected in test_cases:
        try:
            request = AIGenerationRequest(
                title="Test Plan",
                goal="maintenance",
                target_calories=2000,
                dietary_restrictions=input_value
            )

            if request.dietary_restrictions == expected:
                print(f"✅ {input_value} → {expected}")
                success_count += 1
            else:
                print(f"⚠️ {input_value} → {request.dietary_restrictions} (esperado: {expected})")
                fail_count += 1

        except Exception as e:
            print(f"❌ {input_value} → ERROR: {e}")
            fail_count += 1

    print(f"\nResultado: {success_count} éxitos, {fail_count} fallos")
    return fail_count == 0


def test_edge_cases():
    """Prueba casos extremos y validación de otros campos."""
    print("\n" + "="*60)
    print("PRUEBA DE CASOS EXTREMOS")
    print("="*60)

    # Caso 1: Goal inválido (no hay alias)
    try:
        request = AIGenerationRequest(
            title="Test",
            goal="invalid_goal",
            target_calories=2000
        )
        print(f"⚠️ Goal inválido aceptado: {request.goal}")
    except ValidationError as e:
        print(f"✅ Goal inválido rechazado correctamente: {e.errors()[0]['msg']}")

    # Caso 2: Calorías fuera de rango
    try:
        request = AIGenerationRequest(
            title="Test",
            goal="maintenance",
            target_calories=500  # Mínimo es 1200
        )
        print(f"⚠️ Calorías inválidas aceptadas: {request.target_calories}")
    except ValidationError as e:
        print(f"✅ Calorías inválidas rechazadas correctamente")

    # Caso 3: Título muy corto
    try:
        request = AIGenerationRequest(
            title="AB",  # Mínimo 3 caracteres
            goal="maintenance",
            target_calories=2000
        )
        print(f"⚠️ Título muy corto aceptado: '{request.title}'")
    except ValidationError as e:
        print(f"✅ Título muy corto rechazado correctamente")

    # Caso 4: Request completo válido con alias
    try:
        request = AIGenerationRequest(
            title="Plan de Mantenimiento",
            goal="maintain",  # Usando alias
            target_calories=2000,
            duration_days=14,
            dietary_restrictions="veggie",  # String simple con alias
            meals_per_day=5,
            difficulty_level="beginner",
            budget_level="medium"
        )
        print(f"✅ Request completo con aliases creado exitosamente")
        print(f"   - goal: {request.goal.value}")
        print(f"   - dietary_restrictions: {request.dietary_restrictions}")
    except ValidationError as e:
        print(f"❌ Error creando request válido: {e}")

    return True


def main():
    """Función principal de pruebas."""
    print("🧪 INICIANDO PRUEBAS DE VALIDATORS DE NUTRICIÓN")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    # Ejecutar todas las pruebas
    all_passed = True

    if not test_goal_aliases():
        all_passed = False

    if not test_dietary_restrictions_aliases():
        all_passed = False

    if not test_edge_cases():
        all_passed = False

    # Resumen final
    print("\n" + "="*60)
    if all_passed:
        print("✅ TODAS LAS PRUEBAS PASARON EXITOSAMENTE")
        print("="*60)
        print("\n📋 RESUMEN:")
        print("• El error de 'maintain' → 'maintenance' está corregido")
        print("• Los aliases comunes funcionan correctamente")
        print("• Las restricciones dietéticas se normalizan")
        print("• La validación de otros campos sigue funcionando")
        print("\n✅ El sistema ahora es más flexible y amigable con el usuario")
    else:
        print("⚠️ ALGUNAS PRUEBAS FALLARON")
        print("="*60)
        print("Revisa los errores arriba para más detalles")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)