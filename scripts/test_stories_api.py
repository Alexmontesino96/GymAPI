#!/usr/bin/env python
"""
Script para probar el API de historias.
"""

import requests
import json
import os
import sys
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuración
BASE_URL = "http://localhost:8000/api/v1"
AUTH_TOKEN = os.getenv("TEST_AUTH_TOKEN", "")  # Token de Auth0 para pruebas

# Headers con autenticación
headers = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json"
}


def test_stories_module_enabled():
    """
    Verifica que el módulo de historias esté habilitado.
    """
    print("\n📋 Verificando módulo de historias...")

    response = requests.get(
        f"{BASE_URL}/modules",
        headers=headers
    )

    if response.status_code == 200:
        modules = response.json()
        stories_module = next((m for m in modules if m.get("code") == "stories"), None)

        if stories_module and stories_module.get("active"):
            print("✅ Módulo de historias está activo")
            return True
        else:
            print("❌ Módulo de historias no está activo")
            return False
    else:
        print(f"❌ Error al verificar módulos: {response.status_code}")
        print(f"   Respuesta: {response.text}")
        return False


def test_create_story():
    """
    Prueba crear una historia de texto.
    """
    print("\n📝 Creando historia de texto...")

    data = {
        "caption": "Esta es mi primera historia desde el API! 💪",
        "story_type": "text",
        "privacy": "public",
        "duration_hours": 24
    }

    response = requests.post(
        f"{BASE_URL}/stories/",
        data=data,
        headers={
            "Authorization": f"Bearer {AUTH_TOKEN}"
        }
    )

    if response.status_code == 201:
        story = response.json()
        print(f"✅ Historia creada exitosamente")
        print(f"   ID: {story.get('id')}")
        print(f"   Tipo: {story.get('story_type')}")
        print(f"   Caption: {story.get('caption')}")
        return story.get("id")
    else:
        print(f"❌ Error al crear historia: {response.status_code}")
        print(f"   Respuesta: {response.text}")
        return None


def test_get_stories_feed():
    """
    Prueba obtener el feed de historias.
    """
    print("\n📱 Obteniendo feed de historias...")

    response = requests.get(
        f"{BASE_URL}/stories/feed",
        headers=headers
    )

    if response.status_code == 200:
        feed = response.json()
        print(f"✅ Feed obtenido exitosamente")
        print(f"   Usuarios con historias: {feed.get('total_users', 0)}")

        # Mostrar resumen de historias por usuario
        for user_story in feed.get("user_stories", []):
            user_name = user_story.get("user_name", "Usuario")
            story_count = len(user_story.get("stories", []))
            has_unseen = user_story.get("has_unseen", False)

            status = "🔵" if has_unseen else "⚪"
            print(f"   {status} {user_name}: {story_count} historia(s)")

        return True
    else:
        print(f"❌ Error al obtener feed: {response.status_code}")
        print(f"   Respuesta: {response.text}")
        return False


def test_view_story(story_id):
    """
    Prueba marcar una historia como vista.
    """
    if not story_id:
        print("\n⏭️  Saltando prueba de vista (no hay historia)")
        return False

    print(f"\n👁️  Marcando historia {story_id} como vista...")

    response = requests.post(
        f"{BASE_URL}/stories/{story_id}/view",
        headers=headers,
        json={"view_duration_seconds": 3}
    )

    if response.status_code == 200:
        print("✅ Historia marcada como vista")
        return True
    else:
        print(f"❌ Error al marcar vista: {response.status_code}")
        print(f"   Respuesta: {response.text}")
        return False


def test_add_reaction(story_id):
    """
    Prueba agregar una reacción a una historia.
    """
    if not story_id:
        print("\n⏭️  Saltando prueba de reacción (no hay historia)")
        return False

    print(f"\n💪 Agregando reacción a historia {story_id}...")

    data = {
        "emoji": "🔥",
        "message": "Increíble progreso!"
    }

    response = requests.post(
        f"{BASE_URL}/stories/{story_id}/reaction",
        headers=headers,
        json=data
    )

    if response.status_code == 200:
        print("✅ Reacción agregada exitosamente")
        return True
    else:
        print(f"❌ Error al agregar reacción: {response.status_code}")
        print(f"   Respuesta: {response.text}")
        return False


def main():
    """
    Ejecuta todas las pruebas.
    """
    print("=" * 50)
    print("PRUEBAS DEL SISTEMA DE HISTORIAS")
    print("=" * 50)

    if not AUTH_TOKEN:
        print("\n⚠️  ADVERTENCIA: No se encontró TEST_AUTH_TOKEN en las variables de entorno")
        print("   Las pruebas pueden fallar sin autenticación")

    # Verificar que el servidor esté corriendo
    try:
        response = requests.get(f"{BASE_URL.replace('/api/v1', '')}/")
        if response.status_code != 200:
            print("\n❌ El servidor no responde en http://localhost:8000")
            print("   Asegúrate de ejecutar: python app_wrapper.py")
            return
    except requests.exceptions.ConnectionError:
        print("\n❌ No se puede conectar al servidor en http://localhost:8000")
        print("   Asegúrate de ejecutar: python app_wrapper.py")
        return

    print("\n✅ Servidor en línea")

    # Ejecutar pruebas
    results = []

    # 1. Verificar módulo habilitado
    results.append(("Módulo habilitado", test_stories_module_enabled()))

    # 2. Crear historia
    story_id = test_create_story()
    results.append(("Crear historia", story_id is not None))

    # 3. Obtener feed
    results.append(("Obtener feed", test_get_stories_feed()))

    # 4. Marcar como vista
    results.append(("Marcar vista", test_view_story(story_id)))

    # 5. Agregar reacción
    results.append(("Agregar reacción", test_add_reaction(story_id)))

    # Resumen
    print("\n" + "=" * 50)
    print("RESUMEN DE PRUEBAS")
    print("=" * 50)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")

    print(f"\nResultado: {passed}/{total} pruebas pasaron")

    if passed == total:
        print("\n🎉 ¡Todas las pruebas pasaron exitosamente!")
    else:
        print(f"\n⚠️  {total - passed} prueba(s) fallaron")


if __name__ == "__main__":
    main()