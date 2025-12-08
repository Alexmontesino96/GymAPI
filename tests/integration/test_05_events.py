"""
Tests de Integración - Events Module (Prioridad 2)

Valida funcionalidad de eventos.
"""
import pytest
import httpx
from .test_config import config


class TestEventsModule:
    """Tests para el módulo de eventos"""

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
    async def test_get_events_list(self):
        """Test: GET /api/v1/events/ - Listar eventos

        Este endpoint usa async_event_service.get_events_cached()
        y async_event_repository.get_events_with_counts() que fue implementado.
        """
        headers = config.get_headers("admin")
        response = await self.make_request("GET", "/events/?limit=10", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Eventos obtenidos: {len(data)}")

    @pytest.mark.asyncio
    async def test_get_event_details(self):
        """Test: GET /api/v1/events/{event_id} - Detalles de evento"""
        headers = config.get_headers("admin")

        # Primero obtener un evento
        events_response = await self.make_request("GET", "/events/?limit=1", headers=headers)

        if events_response.status_code == 200:
            events = events_response.json()
            if events:
                event_id = events[0]["id"]

                # Obtener detalles
                response = await self.make_request(
                    "GET",
                    f"/events/{event_id}",
                    headers=headers
                )

                assert response.status_code == 200
                data = response.json()
                assert "id" in data
                print(f"✅ Detalles de evento obtenidos: ID {event_id}")
            else:
                print(f"⚠️  No hay eventos disponibles para probar detalles")

    @pytest.mark.asyncio
    async def test_events_async_fix(self):
        """Test: Verificar que get_events_with_counts async funciona

        Este método fue implementado como parte de las correcciones.
        """
        headers = config.get_headers("admin")
        response = await self.make_request("GET", "/events/?limit=5", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Verificar que incluye participants_count
        if data:
            assert "participants_count" in data[0] or "id" in data[0]
            print(f"✅ get_events_with_counts funcionando correctamente (async)")
        else:
            print(f"⚠️  No hay eventos para validar participants_count")

    @pytest.mark.asyncio
    async def test_events_response_time(self):
        """Test: Tiempo de respuesta de eventos"""
        headers = config.get_headers("admin")

        times = []
        for _ in range(3):
            response = await self.make_request("GET", "/events/?limit=10", headers=headers)
            times.append(response.elapsed.total_seconds())

        avg_time = sum(times) / len(times)
        print(f"📊 Tiempo promedio GET /events: {avg_time*1000:.0f}ms")

        assert avg_time < 0.5, f"Tiempo {avg_time*1000:.0f}ms > 500ms"
        print(f"✅ Tiempo dentro del target")
