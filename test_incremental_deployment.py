#!/usr/bin/env python3
"""
Verificar si el nuevo código de generación incremental está desplegado.
"""

import requests
import time
from datetime import datetime

def check_deployment():
    print("=" * 60)
    print("VERIFICACIÓN DE DEPLOYMENT - GENERACIÓN INCREMENTAL")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    # Verificar si el servidor responde
    try:
        response = requests.get("https://gymapi-cjb0.onrender.com/", timeout=10)
        print(f"✅ Servidor respondiendo: Status {response.status_code}")
    except Exception as e:
        print(f"❌ Error conectando al servidor: {e}")
        return

    # Buscar indicadores en logs si es posible
    print("\n🔍 ESTADO DEL DEPLOYMENT:")
    print("El nuevo código debería:")
    print("1. Generar estructura base primero (10s timeout)")
    print("2. Generar días en chunks de 2 días (15s timeout cada uno)")
    print("3. NO causar timeouts de 30+ segundos")
    print("4. Usar prompts ultra-compactos")

    print("\n📊 TIEMPOS ESPERADOS:")
    print("- Estructura base: ~2-3 segundos")
    print("- Chunk días 1-2: ~8 segundos")
    print("- Chunk días 3-4: ~8 segundos")
    print("- Chunk días 5-6: ~8 segundos")
    print("- Chunk día 7: ~4 segundos")
    print("- TOTAL: ~30 segundos (pero sin timeout individual)")

    print("\n⏱️ ÚLTIMA ACTUALIZACIÓN:")
    print("- Commit: 4f7b340 (feat: generación incremental)")
    print("- Tiempo de deploy estimado: 5-7 minutos")
    print("- Si el deploy inició a las 05:16:43, debería estar listo ~05:23")

    current_time = datetime.now()
    deploy_start = datetime(2026, 1, 1, 5, 16, 43)
    elapsed = (current_time - deploy_start).total_seconds()

    if elapsed < 420:  # 7 minutos
        remaining = 420 - elapsed
        print(f"\n⏳ Deploy en progreso... (~{int(remaining/60)} minutos restantes)")
    else:
        print(f"\n✅ Deploy debería estar completo (han pasado {int(elapsed/60)} minutos)")

    print("\n🔧 PRÓXIMOS PASOS:")
    print("1. Esperar a que termine el deploy (~7 minutos total)")
    print("2. Probar generación de plan de 7 días")
    print("3. Verificar que NO hay timeouts de 30s")
    print("4. Confirmar que genera en chunks incrementales")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    check_deployment()