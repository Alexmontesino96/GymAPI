#!/usr/bin/env python3
"""
Test del prompt optimizado final
"""

import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("CHAT_GPT_MODEL") or os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

print("🚀 TEST DE PROMPT OPTIMIZADO FINAL")
print("=" * 60)

# Configuración optimizada
system_prompt = """Genera un plan nutricional en formato JSON.
Incluye 1 día con 5 comidas (breakfast, snack, lunch, snack, dinner).
Cada comida debe tener: nombre, meal_type, calories, protein, carbs, fat, ingredients (máx 2), instructions.
Responde SOLO con JSON válido, sin texto adicional."""

print("\n📝 CONFIGURACIÓN OPTIMIZADA:")
print(f"• Prompt claro y estructurado")
print(f"• Sin response_format JSON (más rápido)")
print(f"• Temperatura 0.3 (balance velocidad/variedad)")
print(f"• Max tokens 600 (suficiente para 1 día)")
print(f"• Timeout 15 segundos")

print("\n🧪 Generando 5 días para medir consistencia...")

times = []
successes = 0

for day in range(1, 6):
    day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

    user_prompt = f"""Crea el plan para el día {day} ({day_names[day-1]}).
Objetivo: cut con 2000 calorías diarias.
Distribuir en 5 comidas: breakfast, snack, lunch, snack, dinner."""

    print(f"\n📅 Día {day} ({day_names[day-1]})...")

    start = time.time()
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=600,
            timeout=15.0
        )

        elapsed = time.time() - start
        times.append(elapsed)

        content = response.choices[0].message.content
        tokens = response.usage.completion_tokens

        # Verificar JSON
        try:
            data = json.loads(content)
            json_valid = True
            successes += 1
        except:
            json_valid = False

        print(f"   ✅ Tiempo: {elapsed:.2f}s")
        print(f"   ✅ Tokens: {tokens} ({tokens/elapsed:.1f} tokens/seg)")
        print(f"   ✅ JSON válido: {'Sí' if json_valid else 'No'}")

    except Exception as e:
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"   ❌ Error después de {elapsed:.2f}s: {str(e)[:50]}")

# Estadísticas finales
if times:
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)

    print("\n" + "=" * 60)
    print("📊 RESULTADOS FINALES:")
    print(f"• Días exitosos: {successes}/5")
    print(f"• Tiempo promedio: {avg_time:.2f} segundos")
    print(f"• Tiempo mínimo: {min_time:.2f} segundos")
    print(f"• Tiempo máximo: {max_time:.2f} segundos")

    if avg_time < 10:
        print("✅ EXCELENTE: Promedio bajo 10 segundos")
    elif avg_time < 15:
        print("✅ BUENO: Promedio bajo 15 segundos")
    else:
        print("⚠️ MEJORABLE: Promedio sobre 15 segundos")

print("\n" + "=" * 60)