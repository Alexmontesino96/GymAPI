"""
Tests de Integración - Gyms Module (Prioridad 1)

Valida gestión de gimnasios y membresías.
"""
import pytest
import httpx
from .test_config import config


class TestGymsModule:
    """Tests para el módulo de gimnasios"""

    @pytest.fixture(autouse=True)
    async def setup(self):
        self.base_url = f"{config.base_url}/api/v1"
        self.timeout = config.request_timeout

    async def make_request(self, method: str, endpoint: str, headers: dict = None,
                          json: dict = None, expected_status: int = 200) -> httpx.Response:
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
    async def test_get_my_gyms(self):
        """Test: GET /api/v1/gyms/me - Obtener mis gimnasios"""
        headers = config.get_headers("admin")
        response = await self.make_request("GET", "/gyms/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Gimnasios obtenidos: {len(data)}")

    @pytest.mark.asyncio
    async def test_get_gym_details(self):
        """Test: GET /api/v1/gyms/{gym_id} - Detalles del gimnasio"""
        headers = config.get_headers("admin")
        response = await self.make_request(
            "GET",
            f"/gyms/{config.test_gym_id}",
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
        print(f"✅ Gimnasio obtenido: {data.get('name')}")

    @pytest.mark.asyncio
    async def test_get_gym_members(self):
        """Test: GET /api/v1/gyms/{gym_id}/members - Miembros del gym"""
        headers = config.get_headers("admin")
        response = await self.make_request(
            "GET",
            f"/gyms/{config.test_gym_id}/members?limit=10",
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Miembros obtenidos: {len(data)}")

    @pytest.mark.asyncio
    async def test_gym_check_user_in_gym_async_fix(self):
        """Test: Verificar que check_user_in_gym async funciona correctamente"""
        headers = config.get_headers("admin")

        # Este endpoint internamente llama a async_gym_service.check_user_in_gym()
        # que fue uno de los métodos corregidos
        response = await self.make_request(
            "GET",
            f"/gyms/{config.test_gym_id}",
            headers=headers
        )

        assert response.status_code == 200
        print(f"✅ check_user_in_gym funcionando correctamente (async)")
