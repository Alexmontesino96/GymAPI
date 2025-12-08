"""
Tests de Integración - Auth Module (Prioridad 1)

Valida que todos los endpoints de autenticación funcionen correctamente
con la migración async.
"""
import pytest
import httpx
import asyncio
from typing import Dict, Any
from .test_config import config


class TestAuthModule:
    """Tests para el módulo de autenticación"""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup para cada test"""
        self.base_url = f"{config.base_url}/api/v1"
        self.timeout = config.request_timeout

    async def make_request(
        self,
        method: str,
        endpoint: str,
        headers: Dict[str, str] = None,
        json: Dict[str, Any] = None,
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
    async def test_get_current_user_profile(self):
        """Test: GET /api/v1/auth/me - Obtener perfil del usuario autenticado"""
        headers = config.get_headers("admin")
        response = await self.make_request("GET", "/auth/me", headers=headers)

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert "id" in data
        assert "email" in data
        assert "name" in data

        print(f"✅ Perfil obtenido: {data.get('email')}")

    @pytest.mark.asyncio
    async def test_get_current_user_without_token(self):
        """Test: GET /api/v1/auth/me - Sin token debe fallar"""
        response = await self.make_request(
            "GET", "/auth/me",
            headers={"Content-Type": "application/json"},
            expected_status=401
        )

        assert response.status_code == 401
        print(f"✅ Correctamente rechazado sin token")

    @pytest.mark.asyncio
    async def test_get_current_user_with_invalid_token(self):
        """Test: GET /api/v1/auth/me - Con token inválido debe fallar"""
        headers = {
            "Authorization": "Bearer invalid_token_12345",
            "Content-Type": "application/json"
        }
        response = await self.make_request(
            "GET", "/auth/me",
            headers=headers,
            expected_status=401
        )

        assert response.status_code == 401
        print(f"✅ Correctamente rechazado con token inválido")

    @pytest.mark.asyncio
    async def test_concurrent_auth_requests(self):
        """Test: Múltiples requests concurrentes al endpoint de auth"""
        headers = config.get_headers("admin")

        async def single_request():
            return await self.make_request("GET", "/auth/me", headers=headers)

        # Hacer 10 requests concurrentes
        tasks = [single_request() for _ in range(10)]
        responses = await asyncio.gather(*tasks)

        # Todos deben ser exitosos
        success_count = sum(1 for r in responses if r.status_code == 200)

        assert success_count == 10, f"Solo {success_count}/10 requests exitosos"
        print(f"✅ {success_count}/10 requests concurrentes exitosos")

    @pytest.mark.asyncio
    async def test_response_time_auth_me(self):
        """Test: Tiempo de respuesta de /auth/me debe ser <500ms"""
        headers = config.get_headers("admin")

        times = []
        for i in range(5):
            response = await self.make_request("GET", "/auth/me", headers=headers)
            times.append(response.elapsed.total_seconds())

        avg_time = sum(times) / len(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]

        print(f"📊 Tiempos de respuesta:")
        print(f"   Promedio: {avg_time*1000:.0f}ms")
        print(f"   P95: {p95_time*1000:.0f}ms")
        print(f"   Max: {max(times)*1000:.0f}ms")

        assert p95_time < 0.5, f"P95 {p95_time*1000:.0f}ms > 500ms target"
        print(f"✅ Tiempos de respuesta dentro del target")


@pytest.mark.asyncio
async def test_module_summary():
    """Summary de resultados del módulo Auth"""
    print("\n" + "="*60)
    print("📋 RESUMEN - AUTH MODULE")
    print("="*60)
    print("Módulo: Autenticación")
    print("Prioridad: 🔴 CRÍTICA")
    print("Tests ejecutados: Ver arriba")
    print("="*60)
