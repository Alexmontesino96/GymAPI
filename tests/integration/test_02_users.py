"""
Tests de Integración - Users Module (Prioridad 1)

Valida gestión de usuarios y perfiles.
"""
import pytest
import httpx
from .test_config import config


class TestUsersModule:
    """Tests para el módulo de usuarios"""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup para cada test"""
        self.base_url = f"{config.base_url}/api/v1"
        self.timeout = config.request_timeout

    async def make_request(
        self,
        method: str,
        endpoint: str,
        headers: dict = None,
        json: dict = None,
        expected_status: int = 200
    ) -> httpx.Response:
        """Helper para hacer requests"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            url = f"{self.base_url}{endpoint}"

            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=json)
            elif method == "PUT":
                response = await client.put(url, headers=headers, json=json)
            elif method == "DELETE":
                response = await client.delete(url, headers=headers)

            print(f"\n{'='*60}")
            print(f"Request: {method} {endpoint}")
            print(f"Status: {response.status_code}")
            print(f"Time: {response.elapsed.total_seconds():.3f}s")

            if response.status_code != expected_status:
                print(f"❌ Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"Response: {response.json()}")
                except:
                    print(f"Response: {response.text[:200]}")
            else:
                print(f"✅ Status correcto")

            return response

    @pytest.mark.asyncio
    async def test_get_my_profile(self):
        """Test: GET /api/v1/users/me - Obtener mi perfil"""
        headers = config.get_headers("admin")
        response = await self.make_request("GET", "/users/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "email" in data
        print(f"✅ Perfil obtenido: {data.get('email')}")

    @pytest.mark.asyncio
    async def test_update_my_profile(self):
        """Test: PUT /api/v1/users/me - Actualizar mi perfil"""
        headers = config.get_headers("admin")

        # Actualizar nombre
        update_data = {
            "name": "Test User Updated",
            "phone": "+1234567890"
        }

        response = await self.make_request(
            "PUT",
            "/users/me",
            headers=headers,
            json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        print(f"✅ Perfil actualizado")

    @pytest.mark.asyncio
    async def test_get_gym_users_list(self):
        """Test: GET /api/v1/users/ - Listar usuarios del gym"""
        headers = config.get_headers("admin")
        response = await self.make_request("GET", "/users/?limit=10", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Usuarios obtenidos: {len(data)}")

    @pytest.mark.asyncio
    async def test_get_specific_user(self):
        """Test: GET /api/v1/users/{user_id} - Ver usuario específico"""
        headers = config.get_headers("admin")
        response = await self.make_request(
            "GET",
            f"/users/{config.test_user_id}",
            headers=headers
        )

        # Puede ser 200 o 404 si el usuario no existe
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            print(f"✅ Usuario encontrado: {data.get('id')}")
        else:
            print(f"⚠️  Usuario {config.test_user_id} no encontrado (esperado en algunos casos)")

    @pytest.mark.asyncio
    async def test_users_response_time(self):
        """Test: Tiempos de respuesta de endpoints de usuarios"""
        headers = config.get_headers("admin")

        # Test GET /users/me
        times = []
        for _ in range(3):
            response = await self.make_request("GET", "/users/me", headers=headers)
            times.append(response.elapsed.total_seconds())

        avg_time = sum(times) / len(times)
        print(f"📊 Tiempo promedio /users/me: {avg_time*1000:.0f}ms")

        assert avg_time < 0.5, f"Tiempo {avg_time*1000:.0f}ms > 500ms target"
        print(f"✅ Tiempos dentro del target")
