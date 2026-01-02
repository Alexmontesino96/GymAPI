#!/usr/bin/env python3
"""
Monitorea el deployment de las optimizaciones ultra-rápidas
"""

import time
import requests
from datetime import datetime

def monitor_deployment():
    print("=" * 60)
    print("🔍 MONITOREANDO DEPLOYMENT DE OPTIMIZACIONES")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    print("\n📋 CAMBIOS PENDIENTES DE DEPLOY:")
    print("• Generación día por día (1 día/chunk)")
    print("• Timeouts: 5s estructura, 10s por día")
    print("• Prompts 80% más cortos")
    print("• Temperatura 0.1-0.2")

    print("\n⏱️ PROCESO DE DEPLOY EN RENDER:")
    print("1. Detectar cambios en GitHub (~1 min)")
    print("2. Build del contenedor (~3-4 min)")
    print("3. Health checks (~1 min)")
    print("4. Swap de versiones (~1 min)")
    print("Total: ~7 minutos desde el push")

    # Calcular tiempo desde el push
    push_time = datetime(2026, 1, 1, 14, 27, 30)  # Aproximado
    current = datetime.now()
    elapsed = (current - push_time).total_seconds()

    print(f"\n⌚ Tiempo desde el push: {int(elapsed/60)} minutos")

    if elapsed < 420:  # 7 minutos
        remaining = 420 - elapsed
        print(f"⏳ Deploy en progreso... (~{int(remaining/60)} minutos restantes)")
    else:
        print("✅ Deploy debería estar completo")

    print("\n🧪 PARA VERIFICAR:")
    print("1. Hacer una prueba de generación de 7 días")
    print("2. Verificar en logs que usa:")
    print("   - 'JSON puro, sin texto' (nuevo prompt)")
    print("   - timeout=10.0 (no 15.0)")
    print("   - max_tokens=400 (no 1200)")
    print("3. NO debe haber timeouts si funciona correctamente")

    print("\n📊 RESULTADOS ESPERADOS:")
    print("✅ Estructura base: 2-3 segundos")
    print("✅ Cada día: 4-5 segundos")
    print("✅ Total 7 días: ~33 segundos")
    print("✅ Sin timeouts")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    monitor_deployment()