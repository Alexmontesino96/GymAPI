#!/usr/bin/env python3
"""
Test directo del endpoint de OpenAI con los parámetros exactos que usamos
"""

import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar cliente OpenAI
api_key = os.getenv("CHAT_GPT_MODEL") or os.getenv("OPENAI_API_KEY")
if not api_key:
    print("❌ No se encontró API key de OpenAI")
    exit(1)

client = OpenAI(api_key=api_key)
print(f"✅ Cliente OpenAI configurado")

def test_day_generation():
    """Prueba la generación de 1 día tal como lo hacemos en producción"""

    print("\n" + "="*60)
    print("TEST: Generación de 1 día con OpenAI")
    print("="*60)

    # Prompt exacto que usamos
    system_prompt = """SOLO JSON. 5 comidas/día. Max 2 ingredientes.
{"days":[{"day_number":1,"day_name":"Día","meals":[{"name":"nombre","meal_type":"breakfast|snack|lunch|dinner","calories":400,"protein":30,"carbs":45,"fat":10,"ingredients":[{"name":"ing","quantity":100,"unit":"g"}],"instructions":"prep"}]}]}"""

    user_prompt = """Día 1 (Lunes)
2000cal
5 comidas
Meta: cut"""

    print("\n📝 SISTEMA PROMPT (longitud:", len(system_prompt), "chars):")
    print(system_prompt[:200] + "..." if len(system_prompt) > 200 else system_prompt)

    print("\n📝 USER PROMPT:")
    print(user_prompt)

    print("\n🔧 CONFIGURACIÓN:")
    print(f"  • Modelo: gpt-4o-mini")
    print(f"  • Max tokens: 800")
    print(f"  • Temperatura: 0.2")
    print(f"  • Response format: json_object")

    # Llamada a OpenAI
    print("\n⏱️ Llamando a OpenAI...")
    start_time = time.time()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=800,
            response_format={"type": "json_object"}
        )

        elapsed = time.time() - start_time
        print(f"✅ Respuesta recibida en {elapsed:.2f} segundos")

        # Analizar respuesta
        content = response.choices[0].message.content
        print(f"\n📊 ESTADÍSTICAS DE RESPUESTA:")
        print(f"  • Longitud: {len(content)} caracteres")
        print(f"  • Tokens usados: {response.usage.completion_tokens}")
        print(f"  • Tokens totales: {response.usage.total_tokens}")

        # Verificar JSON válido
        print("\n🔍 VERIFICANDO JSON...")
        try:
            data = json.loads(content)
            print("✅ JSON válido")

            # Analizar estructura
            if "days" in data:
                days = data["days"]
                print(f"  • Días encontrados: {len(days)}")
                if days:
                    day = days[0]
                    meals = day.get("meals", [])
                    print(f"  • Comidas en día 1: {len(meals)}")

                    # Mostrar resumen de comidas
                    print("\n📋 COMIDAS GENERADAS:")
                    total_cal = 0
                    for i, meal in enumerate(meals, 1):
                        cal = meal.get("calories", 0)
                        total_cal += cal
                        print(f"    {i}. {meal.get('name', 'Sin nombre')} ({meal.get('meal_type', '?')}) - {cal} cal")
                    print(f"  • Total calorías: {total_cal}")

            # Guardar respuesta completa
            with open("openai_response.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print("\n💾 Respuesta guardada en openai_response.json")

        except json.JSONDecodeError as e:
            print(f"❌ JSON inválido: {e}")
            print("\n🔧 Intentando reparar JSON...")

            # Intentar reparar
            if content.count('{') > content.count('}'):
                content += '}' * (content.count('{') - content.count('}'))
            if content.count('[') > content.count(']'):
                content += ']' * (content.count('[') - content.count(']'))

            try:
                data = json.loads(content)
                print("✅ JSON reparado exitosamente")
            except:
                print("❌ No se pudo reparar el JSON")
                print("\nPrimeros 500 caracteres:")
                print(content[:500])
                print("\nÚltimos 500 caracteres:")
                print(content[-500:])

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ Error después de {elapsed:.2f} segundos: {e}")

    print("\n" + "="*60)

def test_multiple_days():
    """Prueba generar múltiples días secuencialmente"""

    print("\n" + "="*60)
    print("TEST: Generación de 3 días secuenciales")
    print("="*60)

    total_time = 0
    successful_days = 0

    for day in range(1, 4):
        day_names = ["Lunes", "Martes", "Miércoles"]

        print(f"\n📅 Generando día {day} ({day_names[day-1]})...")
        start_time = time.time()

        user_prompt = f"""Día {day} ({day_names[day-1]})
2000cal
5 comidas
Meta: cut"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """SOLO JSON. 5 comidas/día. Max 2 ingredientes.
{"days":[{"day_number":1,"day_name":"Día","meals":[{"name":"nombre","meal_type":"breakfast|snack|lunch|dinner","calories":400,"protein":30,"carbs":45,"fat":10,"ingredients":[{"name":"ing","quantity":100,"unit":"g"}],"instructions":"prep"}]}]}"""},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=800,
                response_format={"type": "json_object"},
                timeout=12.0
            )

            elapsed = time.time() - start_time
            total_time += elapsed

            # Verificar JSON
            content = response.choices[0].message.content
            data = json.loads(content)

            print(f"  ✅ Día {day} generado en {elapsed:.2f}s - {len(content)} chars")
            successful_days += 1

        except Exception as e:
            elapsed = time.time() - start_time
            total_time += elapsed
            print(f"  ❌ Error en día {day} después de {elapsed:.2f}s: {str(e)[:50]}")

    print(f"\n📊 RESUMEN:")
    print(f"  • Días exitosos: {successful_days}/3")
    print(f"  • Tiempo total: {total_time:.2f} segundos")
    print(f"  • Tiempo promedio: {total_time/3:.2f} segundos/día")

    print("\n" + "="*60)

if __name__ == "__main__":
    print("🚀 Iniciando pruebas directas con OpenAI...")

    # Test 1: Generar 1 día
    test_day_generation()

    # Test 2: Generar múltiples días
    test_multiple_days()

    print("\n✅ Pruebas completadas")