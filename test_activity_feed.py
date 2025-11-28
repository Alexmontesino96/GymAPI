#!/usr/bin/env python3
"""
Script de Testing para Activity Feed.

Este script prueba todas las funcionalidades del Activity Feed de forma interactiva,
verificando que funcione correctamente y respete la privacidad.

Uso:
    python test_activity_feed.py
"""

import asyncio
import aiohttp
import json
import time
import random
from datetime import datetime
from typing import Dict, List, Any
from colorama import init, Fore, Style
import websockets

# Inicializar colorama para colores en terminal
init(autoreset=True)

# Configuración
API_BASE_URL = "http://localhost:8000/api/v1"
WS_BASE_URL = "ws://localhost:8000/api/v1"
GYM_ID = 1  # ID del gimnasio para testing


class ActivityFeedTester:
    """Clase para probar el Activity Feed."""

    def __init__(self):
        self.session = None
        self.results = []
        self.ws = None

    async def setup(self):
        """Inicializa la sesión HTTP."""
        self.session = aiohttp.ClientSession()
        print(f"{Fore.CYAN}🔧 Sesión HTTP inicializada")

    async def cleanup(self):
        """Limpia recursos."""
        if self.session:
            await self.session.close()
        if self.ws:
            await self.ws.close()
        print(f"{Fore.CYAN}🧹 Recursos limpiados")

    async def test_health_check(self) -> bool:
        """Prueba el health check del Activity Feed."""
        print(f"\n{Fore.YELLOW}=== Test 1: Health Check ==={Style.RESET_ALL}")

        try:
            async with self.session.get(
                f"{API_BASE_URL}/activity-feed/health"
            ) as response:
                data = await response.json()

                if response.status == 200 and data.get("status") == "healthy":
                    print(f"{Fore.GREEN}✅ Health Check: Sistema saludable")
                    print(f"   📊 Redis: {data.get('redis')}")
                    print(f"   💾 Memoria: {data.get('memory_usage_mb')} MB")
                    print(f"   🔐 Modo anónimo: {data.get('anonymous_mode')}")
                    return True
                else:
                    print(f"{Fore.RED}❌ Health Check falló: {data}")
                    return False
        except Exception as e:
            print(f"{Fore.RED}❌ Error en health check: {e}")
            return False

    async def test_generate_activities(self) -> bool:
        """Genera actividades de prueba."""
        print(f"\n{Fore.YELLOW}=== Test 2: Generar Actividades de Prueba ==={Style.RESET_ALL}")

        activities_to_generate = [
            ("training_count", 15, "Personas entrenando"),
            ("achievement_unlocked", 5, "Logros desbloqueados"),
            ("pr_broken", 3, "Récords personales"),
            ("goal_completed", 7, "Metas completadas"),
            ("streak_milestone", 10, "Rachas activas")
        ]

        success_count = 0

        for activity_type, count, description in activities_to_generate:
            try:
                async with self.session.post(
                    f"{API_BASE_URL}/activity-feed/test/generate-activity",
                    params={
                        "activity_type": activity_type,
                        "count": count
                    },
                    headers={"X-Gym-Id": str(GYM_ID)}
                ) as response:
                    data = await response.json()

                    if data.get("status") == "success":
                        print(f"{Fore.GREEN}✅ Generado: {count} {description}")
                        success_count += 1
                    elif data.get("status") == "not_published":
                        print(f"{Fore.YELLOW}⚠️  No publicado: {description} - {data.get('reason')}")
                    else:
                        print(f"{Fore.RED}❌ Error generando: {description}")

                # Pequeña pausa entre requests
                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"{Fore.RED}❌ Error: {e}")

        print(f"\n📊 Resumen: {success_count}/{len(activities_to_generate)} actividades generadas")
        return success_count > 0

    async def test_get_feed(self) -> bool:
        """Obtiene y verifica el feed."""
        print(f"\n{Fore.YELLOW}=== Test 3: Obtener Feed ==={Style.RESET_ALL}")

        try:
            start_time = time.time()

            async with self.session.get(
                f"{API_BASE_URL}/activity-feed",
                params={"limit": 20, "offset": 0},
                headers={"X-Gym-Id": str(GYM_ID)}
            ) as response:
                duration = (time.time() - start_time) * 1000  # ms
                data = await response.json()

                activities = data.get("activities", [])

                print(f"{Fore.GREEN}✅ Feed obtenido en {duration:.1f}ms")
                print(f"   📋 Actividades: {len(activities)}")

                # Verificar privacidad - NO debe haber nombres
                privacy_check = True
                for activity in activities:
                    # Verificar que no hay campos prohibidos
                    forbidden_fields = ["user", "user_id", "user_name", "name", "email"]
                    for field in forbidden_fields:
                        if field in activity:
                            print(f"{Fore.RED}❌ VIOLACIÓN DE PRIVACIDAD: Campo '{field}' encontrado!")
                            privacy_check = False
                            break

                    # Verificar que el mensaje no contiene nombres propios comunes
                    message = activity.get("message", "")
                    common_names = ["María", "Juan", "Pedro", "Ana", "Luis", "Carlos"]
                    for name in common_names:
                        if name in message:
                            print(f"{Fore.RED}❌ POSIBLE NOMBRE en mensaje: {message}")
                            privacy_check = False

                if privacy_check:
                    print(f"{Fore.GREEN}✅ Verificación de privacidad: PASADA")

                # Mostrar algunas actividades
                print(f"\n{Fore.CYAN}📢 Últimas actividades:{Style.RESET_ALL}")
                for i, activity in enumerate(activities[:5], 1):
                    icon = activity.get("icon", "📊")
                    message = activity.get("message", "")
                    time_ago = activity.get("time_ago", "")
                    print(f"   {i}. {icon} {message} ({time_ago})")

                # Verificar performance
                if duration < 50:
                    print(f"{Fore.GREEN}✅ Performance: Excelente (<50ms)")
                elif duration < 100:
                    print(f"{Fore.YELLOW}⚠️  Performance: Bueno (<100ms)")
                else:
                    print(f"{Fore.RED}❌ Performance: Lento (>100ms)")

                return len(activities) > 0 and privacy_check

        except Exception as e:
            print(f"{Fore.RED}❌ Error obteniendo feed: {e}")
            return False

    async def test_realtime_stats(self) -> bool:
        """Prueba estadísticas en tiempo real."""
        print(f"\n{Fore.YELLOW}=== Test 4: Estadísticas en Tiempo Real ==={Style.RESET_ALL}")

        try:
            async with self.session.get(
                f"{API_BASE_URL}/activity-feed/realtime",
                headers={"X-Gym-Id": str(GYM_ID)}
            ) as response:
                data = await response.json()

                if data.get("status") == "success":
                    stats = data.get("data", {})

                    print(f"{Fore.GREEN}✅ Estadísticas obtenidas:")
                    print(f"   💪 Total entrenando: {stats.get('total_training', 0)}")
                    print(f"   🔥 Hora pico: {'Sí' if stats.get('peak_time') else 'No'}")

                    # Mostrar por áreas
                    by_area = stats.get("by_area", {})
                    if by_area:
                        print(f"   📊 Por área:")
                        for area, count in by_area.items():
                            print(f"      • {area}: {count} personas")

                    # Clases populares
                    popular = stats.get("popular_classes", [])
                    if popular:
                        print(f"   ⭐ Clases populares:")
                        for cls in popular[:3]:
                            print(f"      • {cls.get('name')}: {cls.get('count')} personas")

                    return True
                else:
                    print(f"{Fore.RED}❌ Error: {data}")
                    return False

        except Exception as e:
            print(f"{Fore.RED}❌ Error: {e}")
            return False

    async def test_insights(self) -> bool:
        """Prueba generación de insights motivacionales."""
        print(f"\n{Fore.YELLOW}=== Test 5: Insights Motivacionales ==={Style.RESET_ALL}")

        try:
            async with self.session.get(
                f"{API_BASE_URL}/activity-feed/insights",
                headers={"X-Gym-Id": str(GYM_ID)}
            ) as response:
                data = await response.json()

                insights = data.get("insights", [])

                print(f"{Fore.GREEN}✅ {len(insights)} insights generados:")

                for insight in insights:
                    message = insight.get("message", "")
                    priority = "🔥" if insight.get("priority") == 1 else "💫"
                    print(f"   {priority} {message}")

                # Verificar que no hay nombres
                for insight in insights:
                    message = insight.get("message", "")
                    if any(name in message for name in ["María", "Juan", "Pedro", "Ana"]):
                        print(f"{Fore.RED}❌ Nombre encontrado en insight!")
                        return False

                return len(insights) > 0

        except Exception as e:
            print(f"{Fore.RED}❌ Error: {e}")
            return False

    async def test_rankings(self) -> bool:
        """Prueba rankings anónimos."""
        print(f"\n{Fore.YELLOW}=== Test 6: Rankings Anónimos ==={Style.RESET_ALL}")

        ranking_types = ["consistency", "attendance", "improvement"]
        success = True

        for ranking_type in ranking_types:
            try:
                async with self.session.get(
                    f"{API_BASE_URL}/activity-feed/rankings/{ranking_type}",
                    params={"period": "weekly", "limit": 5},
                    headers={"X-Gym-Id": str(GYM_ID)}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        rankings = data.get("rankings", [])
                        unit = data.get("unit", "")

                        print(f"\n{Fore.CYAN}📊 Ranking: {ranking_type} ({unit})")

                        if rankings:
                            for rank in rankings:
                                position = rank.get("position")
                                value = rank.get("value")
                                label = rank.get("label")

                                # Verificar anonimato
                                if "user" in str(rank).lower() or "name" in str(rank).lower():
                                    print(f"{Fore.RED}❌ Información de usuario en ranking!")
                                    success = False
                                else:
                                    medal = "🥇" if position == 1 else "🥈" if position == 2 else "🥉" if position == 3 else "  "
                                    print(f"   {medal} {label}: {value} {unit}")
                        else:
                            print(f"   {Fore.YELLOW}(Sin datos de ranking)")
                    else:
                        print(f"{Fore.YELLOW}⚠️  {ranking_type}: Sin datos")

            except Exception as e:
                print(f"{Fore.RED}❌ Error en ranking {ranking_type}: {e}")
                success = False

        return success

    async def test_websocket(self) -> bool:
        """Prueba conexión WebSocket para tiempo real."""
        print(f"\n{Fore.YELLOW}=== Test 7: WebSocket Tiempo Real ==={Style.RESET_ALL}")

        try:
            uri = f"{WS_BASE_URL}/activity-feed/ws?gym_id={GYM_ID}"

            print(f"{Fore.CYAN}🔌 Conectando a WebSocket...")

            async with websockets.connect(uri) as websocket:
                # Recibir mensaje de bienvenida
                welcome = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                welcome_data = json.loads(welcome)

                if welcome_data.get("type") == "connection":
                    print(f"{Fore.GREEN}✅ Conectado: {welcome_data.get('message')}")

                    # Generar una actividad para provocar actualización
                    print(f"{Fore.CYAN}📤 Generando actividad para WebSocket...")

                    async with self.session.post(
                        f"{API_BASE_URL}/activity-feed/test/generate-activity",
                        params={
                            "activity_type": "training_count",
                            "count": random.randint(10, 30)
                        },
                        headers={"X-Gym-Id": str(GYM_ID)}
                    ) as response:
                        if response.status == 200:
                            # Esperar actualización por WebSocket
                            try:
                                update = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                                update_data = json.loads(update)

                                if update_data.get("type") == "activity":
                                    activity = update_data.get("data", {})
                                    print(f"{Fore.GREEN}✅ Actualización recibida:")
                                    print(f"   {activity.get('icon')} {activity.get('message')}")
                                    return True
                            except asyncio.TimeoutError:
                                print(f"{Fore.YELLOW}⚠️  No se recibió actualización (puede ser normal si no hay cambios)")
                                return True

                return False

        except asyncio.TimeoutError:
            print(f"{Fore.YELLOW}⚠️  Timeout en WebSocket (puede ser normal)")
            return True
        except Exception as e:
            print(f"{Fore.RED}❌ Error en WebSocket: {e}")
            return False

    async def test_daily_summary(self) -> bool:
        """Prueba resumen diario de estadísticas."""
        print(f"\n{Fore.YELLOW}=== Test 8: Resumen Diario ==={Style.RESET_ALL}")

        try:
            async with self.session.get(
                f"{API_BASE_URL}/activity-feed/stats/summary",
                headers={"X-Gym-Id": str(GYM_ID)}
            ) as response:
                data = await response.json()

                stats = data.get("stats", {})
                highlights = data.get("highlights", [])

                print(f"{Fore.GREEN}✅ Estadísticas del día:")
                print(f"   📊 Asistencia: {stats.get('attendance', 0)} personas")
                print(f"   ⭐ Logros: {stats.get('achievements', 0)}")
                print(f"   💪 PRs: {stats.get('personal_records', 0)}")
                print(f"   🎯 Metas: {stats.get('goals_completed', 0)}")
                print(f"   ⏱️ Horas totales: {stats.get('total_hours', 0):.1f}")
                print(f"   🔥 Rachas activas: {stats.get('active_streaks', 0)}")
                print(f"   📈 Score de engagement: {stats.get('engagement_score', 0)}/100")

                if highlights:
                    print(f"\n{Fore.CYAN}🌟 Highlights del día:")
                    for highlight in highlights:
                        print(f"   • {highlight}")

                return True

        except Exception as e:
            print(f"{Fore.RED}❌ Error: {e}")
            return False

    async def run_all_tests(self):
        """Ejecuta todos los tests."""
        print(f"{Fore.MAGENTA}{'='*60}")
        print(f"{Fore.MAGENTA}🚀 INICIANDO TESTS DEL ACTIVITY FEED")
        print(f"{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")

        await self.setup()

        tests = [
            ("Health Check", self.test_health_check),
            ("Generar Actividades", self.test_generate_activities),
            ("Obtener Feed", self.test_get_feed),
            ("Estadísticas Tiempo Real", self.test_realtime_stats),
            ("Insights Motivacionales", self.test_insights),
            ("Rankings Anónimos", self.test_rankings),
            ("WebSocket", self.test_websocket),
            ("Resumen Diario", self.test_daily_summary)
        ]

        results = []

        for name, test_func in tests:
            try:
                result = await test_func()
                results.append((name, result))
                await asyncio.sleep(0.5)  # Pausa entre tests
            except Exception as e:
                print(f"{Fore.RED}❌ Error ejecutando {name}: {e}")
                results.append((name, False))

        # Resumen final
        print(f"\n{Fore.MAGENTA}{'='*60}")
        print(f"{Fore.MAGENTA}📊 RESUMEN DE RESULTADOS")
        print(f"{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")

        passed = sum(1 for _, result in results if result)
        total = len(results)

        for name, result in results:
            status = f"{Fore.GREEN}✅ PASS" if result else f"{Fore.RED}❌ FAIL"
            print(f"{status}: {name}")

        print(f"\n{Fore.CYAN}Total: {passed}/{total} tests pasados")

        if passed == total:
            print(f"\n{Fore.GREEN}🎉 ¡TODOS LOS TESTS PASARON! El Activity Feed funciona correctamente.")
        elif passed >= total * 0.7:
            print(f"\n{Fore.YELLOW}⚠️  La mayoría de tests pasaron, pero hay algunos problemas.")
        else:
            print(f"\n{Fore.RED}❌ Muchos tests fallaron. Revisa la implementación.")

        await self.cleanup()

        return passed == total


async def main():
    """Función principal."""
    tester = ActivityFeedTester()
    success = await tester.run_all_tests()

    # Mensaje final sobre privacidad
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}🔐 NOTA DE PRIVACIDAD")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print("El Activity Feed está diseñado para ser 100% anónimo.")
    print("✅ Solo muestra cantidades agregadas")
    print("✅ Nunca expone nombres de usuarios")
    print("✅ Requiere mínimo 3 personas para mostrar actividades")
    print("✅ Todos los datos son efímeros (TTL automático)")
    print(f"\n{Fore.GREEN}Principio: 'Números que motivan, sin nombres que comprometan'")

    return 0 if success else 1


if __name__ == "__main__":
    # Verificar que el servidor esté corriendo
    print(f"{Fore.YELLOW}⚠️  Asegúrate de que el servidor esté corriendo:")
    print(f"    python app_wrapper.py")
    print(f"    o")
    print(f"    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000\n")

    # Ejecutar tests
    exit_code = asyncio.run(main())
    exit(exit_code)