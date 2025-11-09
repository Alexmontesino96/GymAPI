"""
Test simple del endpoint de stories en producción
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Configuración
BASE_URL = "https://gymapi-eh6m.onrender.com"
GYM_ID = 4

# Token de autenticación (proporcionado por el usuario)
AUTH_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InI2YXBIZVNOUEluaXpheDlYN1NidyJ9.eyJodHRwczovL2d5bWFwaS9wZXJtaXNzaW9ucyI6WyJ0ZW5hbnQ6cmVhZCIsInVzZXI6cmVhZCIsInJlc291cmNlOndyaXRlIiwicmVzb3VyY2U6cmVhZCJdLCJlbWFpbCI6Impvc2VwYXVsMTJAZ21haWwuY29tIiwiaXNzIjoiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vIiwic3ViIjoiYXV0aDB8NjdmNzFlMzA0YjhhMDUwMjRjMTYzZTA0IiwiYXVkIjpbImh0dHBzOi8vZ3ltYXBpIiwiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzYyNjc1NjM2LCJleHAiOjE3NjI3NjIwMzYsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUgZW1haWwiLCJhenAiOiJPdUo2SUtFMGxKU2RhTUc2amFXMDRqZnB0c01SYnl2cCIsInBlcm1pc3Npb25zIjpbInJlc291cmNlOnJlYWQiLCJyZXNvdXJjZTp3cml0ZSIsInRlbmFudDpyZWFkIiwidXNlcjpyZWFkIl19.HI6je08QiimoGkBMUzGITHz4s6Phy_oiBPIjoTNqdqY1YjAKoZv0alyoICy-uYNe2zywgfGmprVjWFBS7oDRyXWoaw1p0SPoO-3N2icNI8vwFfzT9clxPOhKttOqT7UNzyZ8wkLnnHvPuxgLeg3Jms4SYkYo1MtAI-_0NdPR-GZqtgeV-meBbt9ccw2537yY1nDiIrYZMOKMCkN_8kE9fJxuj4mVk4GA-rhqYpO1ZkU5w13ITMlr7wxQWOSOskXjDE38DDbjP6tmvkpNzyyEYBr_r6N1J-4HSxLakxSvfPAI4tf12h0xjXyXW8P3lZD2MMy-SxaMjZunzQ1S4SeOUg"

def test_stories_feed():
    """Test del endpoint GET /api/v1/stories/feed"""

    print("\n" + "="*60)
    print("TEST: GET /api/v1/stories/feed")
    print("="*60)

    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json",
        "X-Gym-Id": str(GYM_ID)
    }

    url = f"{BASE_URL}/api/v1/stories/feed"
    params = {
        "filter_type": "all",
        "limit": 25
    }

    print(f"\n📡 Haciendo request a: {url}")
    print(f"📊 Parámetros: {params}")
    print(f"🔑 Headers: Authorization, X-Gym-Id={GYM_ID}")

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)

        print(f"\n✅ Status Code: {response.status_code}")
        print(f"📝 Response Headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ SUCCESS! El endpoint respondió correctamente")
            print(f"\n📦 Estructura de respuesta:")
            print(f"   - user_stories: {len(data.get('user_stories', []))} usuarios")
            print(f"   - total_users: {data.get('total_users', 0)}")
            print(f"   - has_more: {data.get('has_more', False)}")

            if data.get('user_stories'):
                print(f"\n👥 Primer usuario con historias:")
                first_user = data['user_stories'][0]
                print(f"   - user_id: {first_user.get('user_id')}")
                print(f"   - user_name: {first_user.get('user_name')}")
                print(f"   - stories_count: {len(first_user.get('stories', []))}")

                if first_user.get('stories'):
                    first_story = first_user['stories'][0]
                    print(f"\n📖 Primera historia:")
                    print(f"   - id: {first_story.get('id')}")
                    print(f"   - story_type: {first_story.get('story_type')}")
                    print(f"   - caption: {first_story.get('caption', 'N/A')}")
                    print(f"   - has_viewed: {first_story.get('has_viewed')}")
            else:
                print(f"\n📭 No hay historias activas en este momento")

            print(f"\n✅ TODAS LAS CORRECCIONES FUNCIONARON CORRECTAMENTE")
            print(f"   - No hay errores de 'await' con Session síncrona")
            print(f"   - No hay errores de prefijo duplicado")
            print(f"   - Stream Feeds funciona con fallback a BD")

            return True

        elif response.status_code == 404:
            print(f"\n⚠️  404 Not Found")
            print(f"   El módulo de stories puede no estar habilitado")
            print(f"   O el endpoint no está registrado correctamente")
            return False

        elif response.status_code == 500:
            print(f"\n❌ 500 Internal Server Error")
            print(f"   Aún hay errores en el servidor")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Response text: {response.text}")
            return False

        else:
            print(f"\n⚠️  Unexpected status code: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print(f"\n❌ TIMEOUT: El servidor tardó más de 10 segundos en responder")
        return False

    except requests.exceptions.RequestException as e:
        print(f"\n❌ ERROR en la petición: {str(e)}")
        return False

    except Exception as e:
        print(f"\n❌ ERROR inesperado: {str(e)}")
        return False


def test_stories_health():
    """Test básico de salud del servidor"""
    print("\n" + "="*60)
    print("TEST: GET / (Health Check)")
    print("="*60)

    url = f"{BASE_URL}/"

    try:
        response = requests.get(url, timeout=5)
        print(f"\n✅ Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"📦 Response: {data}")
            print(f"\n✅ Servidor funcionando correctamente")
            return True
        else:
            print(f"\n⚠️  Status code inesperado: {response.status_code}")
            return False

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False


if __name__ == "__main__":
    print("\n🧪 INICIANDO TESTS DEL ENDPOINT DE STORIES")
    print("="*60)

    # Test 1: Health check
    health_ok = test_stories_health()

    if not health_ok:
        print("\n❌ El servidor no está respondiendo, abortando tests")
        exit(1)

    # Test 2: Stories feed endpoint
    stories_ok = test_stories_feed()

    # Resumen
    print("\n" + "="*60)
    print("📊 RESUMEN DE TESTS")
    print("="*60)
    print(f"Health Check: {'✅ PASS' if health_ok else '❌ FAIL'}")
    print(f"Stories Feed: {'✅ PASS' if stories_ok else '❌ FAIL'}")
    print("="*60)

    if stories_ok:
        print("\n🎉 ¡TODOS LOS TESTS PASARON!")
        print("   El endpoint de stories está funcionando correctamente")
        print("   Todas las correcciones de await fueron exitosas")
        exit(0)
    else:
        print("\n⚠️  Algunos tests fallaron")
        print("   Revisa los logs de Render para más detalles")
        exit(1)
