#!/usr/bin/env python3
"""
Test de performance para identificar por qué OpenAI tarda tanto
"""

import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

api_key = os.getenv("CHAT_GPT_MODEL") or os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

print("🔍 ANÁLISIS DE PERFORMANCE DE OPENAI")
print("=" * 60)

def test_scenario(name, system_prompt, user_prompt, **kwargs):
    """Prueba un escenario específico y mide el tiempo"""
    print(f"\n📊 TEST: {name}")
    print(f"   System prompt length: {len(system_prompt)} chars")
    print(f"   Config: {kwargs}")

    start = time.time()
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            **kwargs
        )
        elapsed = time.time() - start

        content = response.choices[0].message.content
        tokens = response.usage.completion_tokens

        print(f"   ✅ Tiempo: {elapsed:.2f}s")
        print(f"   ✅ Tokens: {tokens}")
        print(f"   ✅ Chars: {len(content)}")
        print(f"   ✅ Tokens/segundo: {tokens/elapsed:.1f}")

        # Verificar si es JSON válido
        if "json" in name.lower():
            try:
                json.loads(content)
                print(f"   ✅ JSON válido")
            except:
                print(f"   ❌ JSON inválido")

        return elapsed, tokens

    except Exception as e:
        elapsed = time.time() - start
        print(f"   ❌ Error después de {elapsed:.2f}s: {e}")
        return elapsed, 0

# Prompt de usuario común para todos los tests
user_prompt = """Día 1 (Lunes)
2000cal
5 comidas
Meta: cut"""

print("\n🧪 ESCENARIO 1: Prompt actual problemático")
test_scenario(
    "Prompt actual con JSON format",
    """SOLO JSON. 5 comidas/día. Max 2 ingredientes.
{"days":[{"day_number":1,"day_name":"Día","meals":[{"name":"nombre","meal_type":"breakfast|snack|lunch|dinner","calories":400,"protein":30,"carbs":45,"fat":10,"ingredients":[{"name":"ing","quantity":100,"unit":"g"}],"instructions":"prep"}]}]}""",
    user_prompt,
    temperature=0.2,
    max_tokens=800,
    response_format={"type": "json_object"}
)

print("\n🧪 ESCENARIO 2: Sin response_format JSON")
test_scenario(
    "Sin JSON format enforcement",
    """SOLO JSON. 5 comidas/día. Max 2 ingredientes.
{"days":[{"day_number":1,"day_name":"Día","meals":[{"name":"nombre","meal_type":"breakfast|snack|lunch|dinner","calories":400,"protein":30,"carbs":45,"fat":10,"ingredients":[{"name":"ing","quantity":100,"unit":"g"}],"instructions":"prep"}]}]}""",
    user_prompt,
    temperature=0.2,
    max_tokens=800
    # Sin response_format
)

print("\n🧪 ESCENARIO 3: Prompt más claro y estructurado")
test_scenario(
    "Prompt mejorado con JSON format",
    """Genera un plan nutricional en formato JSON.

Estructura requerida:
- 1 día con 5 comidas
- Cada comida: nombre, tipo (breakfast/snack/lunch/dinner), calorías, proteína, carbohidratos, grasa
- Máximo 2 ingredientes por comida
- Instrucciones breves

Responde SOLO con JSON válido.""",
    user_prompt,
    temperature=0.2,
    max_tokens=800,
    response_format={"type": "json_object"}
)

print("\n🧪 ESCENARIO 4: Prompt simple sin ejemplo")
test_scenario(
    "Prompt minimalista",
    "Genera un plan nutricional de 1 día con 5 comidas en formato JSON. Solo JSON válido.",
    user_prompt,
    temperature=0.2,
    max_tokens=800,
    response_format={"type": "json_object"}
)

print("\n🧪 ESCENARIO 5: Sin ninguna restricción")
test_scenario(
    "Sin restricciones",
    "Eres un nutricionista. Genera un plan de alimentación.",
    user_prompt,
    temperature=0.2,
    max_tokens=800
)

print("\n🧪 ESCENARIO 6: Temperatura 0 (más determinístico)")
test_scenario(
    "Temperatura 0",
    """Genera un plan nutricional en formato JSON.
Solo JSON válido. 1 día, 5 comidas.""",
    user_prompt,
    temperature=0,
    max_tokens=800,
    response_format={"type": "json_object"}
)

print("\n" + "=" * 60)
print("📊 CONCLUSIONES:")
print("- response_format JSON puede agregar overhead")
print("- Prompts confusos o con ejemplos mal formateados causan demoras")
print("- El modelo puede estar 'pensando' más cuando el prompt es ambiguo")
print("=" * 60)