#!/usr/bin/env python3
"""
Script para monitorear el estado del deploy en Render
"""
import requests
import time
import sys

BASE_URL = "https://gymapi-eh6m.onrender.com"
EXPECTED_COMMIT = "95236d4"  # Commit con todas las correcciones de await
CHECK_INTERVAL = 15  # segundos

def check_deploy():
    """Verifica si el deploy está completo"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            git_commit = data.get('git_commit', 'unknown')
            return git_commit
        return None
    except Exception as e:
        print(f"⚠️  Error al verificar: {str(e)}")
        return None

def main():
    print("🔍 Monitoreando deploy en Render...")
    print(f"   Esperando commit: {EXPECTED_COMMIT}")
    print(f"   Verificando cada {CHECK_INTERVAL} segundos")
    print("   Presiona Ctrl+C para cancelar\n")

    attempts = 0
    max_attempts = 40  # 10 minutos máximo

    while attempts < max_attempts:
        attempts += 1
        elapsed_time = attempts * CHECK_INTERVAL

        current_commit = check_deploy()

        if current_commit == EXPECTED_COMMIT:
            print(f"\n✅ ¡DEPLOY COMPLETADO! (después de {elapsed_time}s)")
            print(f"   Commit activo: {current_commit}")
            print("\n🎉 Ahora puedes probar el endpoint de stories:")
            print(f"   python test_stories_endpoint.py")
            print("\n   O desde tu app móvil - debería funcionar correctamente")
            return 0

        elif current_commit:
            print(f"[{elapsed_time:3d}s] Commit actual: {current_commit} - Esperando deploy...", end='\r')
        else:
            print(f"[{elapsed_time:3d}s] Servidor no responde - Esperando...", end='\r')

        time.sleep(CHECK_INTERVAL)

    print(f"\n⏰ Timeout después de {max_attempts * CHECK_INTERVAL} segundos")
    print("   El deploy puede tardar más de lo esperado")
    print("   Verifica manualmente en Render Dashboard")
    return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Monitoreo cancelado por el usuario")
        sys.exit(0)
