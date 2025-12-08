"""
Tests de Integración - Schedule Module (Prioridad 1 - CRÍTICO)

Valida funcionalidad de clases y reservas.
"""
import pytest
import httpx
from datetime import datetime, timedelta
from .test_config import config


class TestScheduleModule:
    """Tests para el módulo de schedule (CRÍTICO)"""

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
    async def test_get_categories(self):
        """Test: GET /api/v1/schedule/categories - Categorías de clases"""
        headers = config.get_headers("admin")
        response = await self.make_request("GET", "/schedule/categories", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Categorías obtenidas: {len(data)}")

    @pytest.mark.asyncio
    async def test_get_classes(self):
        """Test: GET /api/v1/schedule/classes - Clases disponibles"""
        headers = config.get_headers("admin")
        response = await self.make_request("GET", "/schedule/classes?limit=10", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Clases obtenidas: {len(data)}")

    @pytest.mark.asyncio
    async def test_get_sessions_by_date_range(self):
        """Test: GET /api/v1/schedule/sessions - Sesiones por rango de fechas

        Este endpoint usa async_schedule_service.get_sessions_by_date_range_cached()
        que fue corregido en la migración.
        """
        headers = config.get_headers("admin")

        # Obtener sesiones de hoy hasta dentro de 7 días
        today = datetime.now().date()
        end_date = today + timedelta(days=7)

        response = await self.make_request(
            "GET",
            f"/schedule/sessions?start_date={today}&end_date={end_date}&limit=20",
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Sesiones obtenidas: {len(data)}")
        print(f"   Rango: {today} a {end_date}")

    @pytest.mark.asyncio
    async def test_get_session_details(self):
        """Test: GET /api/v1/schedule/sessions/{session_id} - Detalles de sesión"""
        headers = config.get_headers("admin")

        # Primero obtener una sesión disponible
        today = datetime.now().date()
        end_date = today + timedelta(days=7)

        sessions_response = await self.make_request(
            "GET",
            f"/schedule/sessions?start_date={today}&end_date={end_date}&limit=1",
            headers=headers
        )

        if sessions_response.status_code == 200:
            sessions = sessions_response.json()
            if sessions:
                session_id = sessions[0]["id"]

                # Obtener detalles
                response = await self.make_request(
                    "GET",
                    f"/schedule/sessions/{session_id}",
                    headers=headers
                )

                assert response.status_code == 200
                data = response.json()
                assert "id" in data
                print(f"✅ Detalles de sesión obtenidos: ID {session_id}")
            else:
                print(f"⚠️  No hay sesiones disponibles para probar detalles")
        else:
            print(f"⚠️  No se pudieron obtener sesiones")

    @pytest.mark.asyncio
    async def test_get_my_participations(self):
        """Test: GET /api/v1/schedule/sessions/my-participations - Mis reservas"""
        headers = config.get_headers("member")
        response = await self.make_request(
            "GET",
            "/schedule/sessions/my-participations",
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Mis participaciones obtenidas: {len(data)}")

    @pytest.mark.asyncio
    async def test_schedule_response_times(self):
        """Test: Tiempos de respuesta de endpoints críticos de schedule"""
        headers = config.get_headers("admin")
        today = datetime.now().date()
        end_date = today + timedelta(days=7)

        # Test 1: GET sessions
        times_sessions = []
        for _ in range(3):
            response = await self.make_request(
                "GET",
                f"/schedule/sessions?start_date={today}&end_date={end_date}&limit=20",
                headers=headers
            )
            times_sessions.append(response.elapsed.total_seconds())

        avg_sessions = sum(times_sessions) / len(times_sessions)

        # Test 2: GET categories
        times_categories = []
        for _ in range(3):
            response = await self.make_request("GET", "/schedule/categories", headers=headers)
            times_categories.append(response.elapsed.total_seconds())

        avg_categories = sum(times_categories) / len(times_categories)

        print(f"\n📊 TIEMPOS DE RESPUESTA:")
        print(f"   GET /sessions: {avg_sessions*1000:.0f}ms promedio")
        print(f"   GET /categories: {avg_categories*1000:.0f}ms promedio")

        assert avg_sessions < 0.5, f"Sessions {avg_sessions*1000:.0f}ms > 500ms"
        assert avg_categories < 0.5, f"Categories {avg_categories*1000:.0f}ms > 500ms"
        print(f"✅ Todos los tiempos dentro del target (<500ms)")

    @pytest.mark.asyncio
    async def test_schedule_async_fixes(self):
        """Test: Verificar que las correcciones async funcionan

        Endpoints que fueron corregidos:
        - get_by_date_range_async → get_by_date_range
        - check_user_gym_membership_cached (ahora usa AsyncSession)
        """
        headers = config.get_headers("admin")
        today = datetime.now().date()
        end_date = today + timedelta(days=7)

        # Este endpoint internamente usa get_by_date_range que fue corregido
        response = await self.make_request(
            "GET",
            f"/schedule/sessions?start_date={today}&end_date={end_date}&limit=10",
            headers=headers
        )

        assert response.status_code == 200
        print(f"✅ get_by_date_range funcionando correctamente (async)")

        # Este endpoint usa check_user_gym_membership_cached que fue corregido
        response2 = await self.make_request(
            "GET",
            "/schedule/sessions/my-participations",
            headers=config.get_headers("member")
        )

        assert response2.status_code == 200
        print(f"✅ check_user_gym_membership_cached funcionando correctamente (async)")
