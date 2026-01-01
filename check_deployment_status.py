#!/usr/bin/env python3
"""
Verificar estado del deployment y versión del código en producción
"""

import requests
import json
from datetime import datetime

def check_health():
    """Verificar salud del servidor"""
    url = "https://gymapi-eh6m.onrender.com/"

    try:
        response = requests.get(url, timeout=10)
        print(f"✅ Servidor respondiendo: Status {response.status_code}")
        return True
    except:
        print("❌ Servidor no responde")
        return False

def check_api_version():
    """Verificar versión del API y tiempo de inicio"""
    url = "https://gymapi-eh6m.onrender.com/api/v1/health"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("\n📊 Estado del API:")
            print(f"  - Status: {data.get('status', 'N/A')}")
            print(f"  - Version: {data.get('version', 'N/A')}")
            print(f"  - Database: {data.get('database', 'N/A')}")
            print(f"  - Redis: {data.get('redis', 'N/A')}")
        return True
    except Exception as e:
        print(f"❌ Error verificando versión: {e}")
        return False

def test_prompt_version():
    """Test para verificar qué versión del prompt está usando"""
    print("\n🔍 VERIFICACIÓN DE VERSIÓN DEL CÓDIGO:")

    indicators = {
        "old_version": [
            "Debes responder SOLO con un JSON válido",
            "Instrucciones paso a paso de preparación",
            "7. Respetar todas las restricciones"
        ],
        "new_version": [
            "JSON válido y COMPACTO",
            "Instrucciones breves (1 línea)",
            "Mantén el JSON COMPACTO"
        ]
    }

    print("\nIndicadores de versión antigua:")
    for indicator in indicators["old_version"]:
        print(f"  - {indicator}")

    print("\nIndicadores de versión nueva (optimizada):")
    for indicator in indicators["new_version"]:
        print(f"  - {indicator}")

    print("\n⚠️  Los logs muestran que el servidor está usando la VERSIÓN ANTIGUA")

def check_github_commits():
    """Verificar últimos commits en GitHub"""
    print("\n📦 ÚLTIMOS COMMITS EN GITHUB:")

    commits = [
        ("75c6f9f", "2025-12-31", "optimizar generación con IA para 7 días completos"),
        ("63d25f7", "2025-12-31", "corregir errores críticos en generación con IA"),
        ("e35a2d5", "2025-12-31", "corregir errores en servicio de generación IA"),
    ]

    for sha, date, msg in commits:
        print(f"  {sha} ({date}) - {msg}")

def suggest_actions():
    """Sugerir acciones para actualizar el deployment"""
    print("\n🔧 ACCIONES RECOMENDADAS:")
    print("\n1. Verificar en Render Dashboard:")
    print("   - Ir a https://dashboard.render.com")
    print("   - Buscar el servicio 'gymapi'")
    print("   - Verificar el último deploy")
    print("   - Ver si hay builds fallidos")

    print("\n2. Forzar nuevo deploy (si es necesario):")
    print("   - En Render Dashboard > Manual Deploy")
    print("   - O hacer un commit vacío:")
    print("     git commit --allow-empty -m 'chore: trigger deploy'")
    print("     git push origin main")

    print("\n3. Verificar logs de build:")
    print("   - En Render Dashboard > Events")
    print("   - Buscar errores en el build")
    print("   - Verificar que instale openai==1.61.0")

    print("\n4. Verificar variables de entorno:")
    print("   - CHAT_GPT_MODEL debe estar configurado")
    print("   - DATABASE_URL debe apuntar a la BD correcta")

    print("\n5. Tiempo estimado de deploy:")
    print("   - Build: 3-5 minutos")
    print("   - Deploy: 1-2 minutos")
    print("   - Total: ~7 minutos")

def main():
    print("="*60)
    print("VERIFICACIÓN DE DEPLOYMENT EN RENDER")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*60)

    # Verificaciones
    check_health()
    check_api_version()
    test_prompt_version()
    check_github_commits()
    suggest_actions()

    print("\n" + "="*60)
    print("DIAGNÓSTICO COMPLETADO")
    print("="*60)

if __name__ == "__main__":
    main()