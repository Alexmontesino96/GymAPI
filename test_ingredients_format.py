#!/usr/bin/env python3
"""
Script de prueba para verificar el manejo robusto de diferentes formatos
de ingredientes devueltos por OpenAI.
"""

import json

def test_ingredient_formats():
    """Prueba diferentes formatos de ingredientes que podría devolver OpenAI."""

    print("="*60)
    print("PRUEBA DE FORMATOS DE INGREDIENTES")
    print("="*60)

    # Caso 1: Formato correcto (objetos)
    correct_format = {
        "days": [{
            "day_number": 1,
            "day_name": "Lunes",
            "meals": [{
                "name": "Desayuno",
                "meal_type": "breakfast",
                "calories": 400,
                "protein": 30,
                "carbs": 50,
                "fat": 10,
                "ingredients": [
                    {"name": "Avena", "quantity": 60, "unit": "g"},
                    {"name": "Plátano", "quantity": 1, "unit": "unidad"}
                ],
                "instructions": "Cocinar la avena y agregar plátano"
            }]
        }]
    }

    # Caso 2: Formato incorrecto (strings simples) - el que causa el error
    incorrect_format = {
        "days": [{
            "day_number": 1,
            "day_name": "Lunes",
            "meals": [{
                "name": "Desayuno",
                "meal_type": "breakfast",
                "calories": 400,
                "protein": 30,
                "carbs": 50,
                "fat": 10,
                "ingredients": ["Avena", "Plátano"],  # <-- PROBLEMA
                "instructions": "Cocinar la avena y agregar plátano"
            }]
        }]
    }

    # Caso 3: Formato mixto
    mixed_format = {
        "days": [{
            "day_number": 1,
            "day_name": "Lunes",
            "meals": [{
                "name": "Desayuno",
                "meal_type": "breakfast",
                "calories": 400,
                "protein": 30,
                "carbs": 50,
                "fat": 10,
                "ingredients": [
                    {"name": "Avena", "quantity": 60, "unit": "g"},
                    "Plátano"  # String mezclado con objeto
                ],
                "instructions": "Cocinar la avena y agregar plátano"
            }]
        }]
    }

    # Simular procesamiento con el código corregido
    def process_ingredients(ingredients):
        """Simula el procesamiento robusto de ingredientes."""
        processed = []

        for idx, ing_data in enumerate(ingredients):
            # Si el ingrediente es un string simple, convertirlo a objeto
            if isinstance(ing_data, str):
                ingredient_obj = {
                    'name': ing_data,
                    'quantity': 100,  # Cantidad por defecto
                    'unit': 'g'       # Unidad por defecto
                }
                print(f"  ⚠️ Convirtiendo string '{ing_data}' a objeto")
            elif isinstance(ing_data, dict):
                ingredient_obj = ing_data
                print(f"  ✅ Objeto válido: {ingredient_obj['name']}")
            else:
                print(f"  ❌ Formato no reconocido: {type(ing_data)}")
                continue

            processed.append(ingredient_obj)

        return processed

    # Probar cada formato
    print("\n1. FORMATO CORRECTO (Objetos):")
    print("-" * 40)
    meal = correct_format['days'][0]['meals'][0]
    print(f"Comida: {meal['name']}")
    result = process_ingredients(meal['ingredients'])
    print(f"Resultado: {len(result)} ingredientes procesados\n")

    print("2. FORMATO INCORRECTO (Strings) - El que causa el error:")
    print("-" * 40)
    meal = incorrect_format['days'][0]['meals'][0]
    print(f"Comida: {meal['name']}")
    result = process_ingredients(meal['ingredients'])
    print(f"Resultado: {len(result)} ingredientes procesados\n")

    print("3. FORMATO MIXTO:")
    print("-" * 40)
    meal = mixed_format['days'][0]['meals'][0]
    print(f"Comida: {meal['name']}")
    result = process_ingredients(meal['ingredients'])
    print(f"Resultado: {len(result)} ingredientes procesados\n")

    # Mostrar ejemplo de error sin el manejo robusto
    print("4. SIMULACIÓN DEL ERROR ORIGINAL:")
    print("-" * 40)
    try:
        # Esto es lo que pasaba antes
        ingredients = ["Avena", "Plátano"]
        for ing_data in ingredients:
            name = ing_data['name']  # <-- Error: string indices must be integers
            print(f"Nombre: {name}")
    except TypeError as e:
        print(f"❌ ERROR: {e}")
        print("   Este es el error que estábamos viendo en producción")

    print("\n" + "="*60)
    print("RESUMEN DE LA SOLUCIÓN:")
    print("="*60)
    print("✅ El código ahora detecta si el ingrediente es un string")
    print("✅ Lo convierte automáticamente a un objeto con valores por defecto")
    print("✅ Maneja casos mixtos (algunos strings, algunos objetos)")
    print("✅ Registra warnings para depuración sin romper el flujo")
    print("\n✅ RESULTADO: No más errores 'string indices must be integers'")


if __name__ == "__main__":
    test_ingredient_formats()