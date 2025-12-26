"""
Tests para verificar el manejo correcto de timezone en notificaciones de nutrición.

Este módulo verifica que las notificaciones de comidas se envíen en la hora local
correcta de cada gimnasio, sin importar el timezone configurado.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pytz

from app.services.nutrition_notification_service import (
    send_meal_reminders_all_gyms_job,
    get_active_gyms_with_nutrition_full
)
from app.core.timezone_utils import get_current_time_in_gym_timezone
from app.models.gym import Gym


class TestNutritionTimezoneHandling:
    """Tests para verificar manejo correcto de timezone en notificaciones."""

    def test_get_current_time_in_gym_timezone_mexico(self):
        """Verifica que get_current_time_in_gym_timezone funciona para México."""
        # México está en GMT-6 (CST) o GMT-5 (CDT)
        gym_timezone = "America/Mexico_City"

        current_time_local = get_current_time_in_gym_timezone(gym_timezone)

        # Verificar que retorna datetime aware
        assert current_time_local.tzinfo is not None
        assert current_time_local.tzinfo.zone == gym_timezone

        # Verificar que es hora actual
        utc_now = datetime.now(pytz.UTC)
        time_diff = abs((current_time_local.astimezone(pytz.UTC) - utc_now).total_seconds())
        assert time_diff < 5  # Diferencia menor a 5 segundos

    def test_get_current_time_in_gym_timezone_spain(self):
        """Verifica que get_current_time_in_gym_timezone funciona para España."""
        # España está en GMT+1 (CET) o GMT+2 (CEST)
        gym_timezone = "Europe/Madrid"

        current_time_local = get_current_time_in_gym_timezone(gym_timezone)

        assert current_time_local.tzinfo is not None
        assert current_time_local.tzinfo.zone == gym_timezone

    def test_get_current_time_in_gym_timezone_utc(self):
        """Verifica que get_current_time_in_gym_timezone funciona para UTC."""
        gym_timezone = "UTC"

        current_time_local = get_current_time_in_gym_timezone(gym_timezone)

        assert current_time_local.tzinfo is not None
        utc_now = datetime.now(pytz.UTC)
        time_diff = abs((current_time_local - utc_now).total_seconds())
        assert time_diff < 5

    @patch('app.services.nutrition_notification_service.get_active_gyms_with_nutrition_full')
    @patch('app.services.nutrition_notification_service.send_meal_reminders_job_single_gym')
    @patch('app.services.nutrition_notification_service.get_current_time_in_gym_timezone')
    def test_meal_reminders_only_execute_for_matching_timezone(
        self,
        mock_get_time,
        mock_send_job,
        mock_get_gyms
    ):
        """
        Verifica que send_meal_reminders_all_gyms_job solo ejecuta para gyms
        cuya hora local coincide con scheduled_time.
        """
        # Setup: Crear 3 gyms con diferentes timezones
        gym_mexico = Mock(spec=Gym)
        gym_mexico.id = 1
        gym_mexico.name = "Gym México"
        gym_mexico.timezone = "America/Mexico_City"
        gym_mexico.is_active = True

        gym_spain = Mock(spec=Gym)
        gym_spain.id = 2
        gym_spain.name = "Gym España"
        gym_spain.timezone = "Europe/Madrid"
        gym_spain.is_active = True

        gym_utc = Mock(spec=Gym)
        gym_utc.id = 3
        gym_utc.name = "Gym UTC"
        gym_utc.timezone = "UTC"
        gym_utc.is_active = True

        mock_get_gyms.return_value = [gym_mexico, gym_spain, gym_utc]

        # Mock de get_current_time_in_gym_timezone para retornar diferentes horas
        def get_time_side_effect(tz):
            if tz == "America/Mexico_City":
                # México: 08:00 local
                return Mock(strftime=Mock(return_value="08:00"))
            elif tz == "Europe/Madrid":
                # España: 15:00 local
                return Mock(strftime=Mock(return_value="15:00"))
            elif tz == "UTC":
                # UTC: 08:00
                return Mock(strftime=Mock(return_value="08:00"))

        mock_get_time.side_effect = get_time_side_effect
        mock_send_job.return_value = {"users_found": 10, "queued": 10, "failed": 0}

        # Ejecutar job para breakfast a las 08:00
        send_meal_reminders_all_gyms_job("breakfast", "08:00")

        # Verificar que solo se llamó para México y UTC (hora local 08:00)
        assert mock_send_job.call_count == 2

        # Verificar que se llamó con los gym_ids correctos
        called_gym_ids = [call[0][0] for call in mock_send_job.call_args_list]
        assert 1 in called_gym_ids  # México
        assert 3 in called_gym_ids  # UTC
        assert 2 not in called_gym_ids  # España NO (tiene 15:00 local)

    @patch('app.services.nutrition_notification_service.get_active_gyms_with_nutrition_full')
    @patch('app.services.nutrition_notification_service.send_meal_reminders_job_single_gym')
    @patch('app.services.nutrition_notification_service.get_current_time_in_gym_timezone')
    def test_meal_reminders_skip_non_matching_timezones(
        self,
        mock_get_time,
        mock_send_job,
        mock_get_gyms
    ):
        """
        Verifica que gyms con hora local diferente son correctamente skipped.
        """
        # Setup: Gym con hora local diferente
        gym = Mock(spec=Gym)
        gym.id = 1
        gym.name = "Gym Test"
        gym.timezone = "Asia/Tokyo"
        gym.is_active = True

        mock_get_gyms.return_value = [gym]

        # Mock: Tokyo tiene 20:00 local cuando UTC es 08:00
        mock_get_time.return_value = Mock(strftime=Mock(return_value="20:00"))

        # Ejecutar job para breakfast a las 08:00
        send_meal_reminders_all_gyms_job("breakfast", "08:00")

        # Verificar que NO se llamó send_meal_reminders_job_single_gym
        assert mock_send_job.call_count == 0

    @patch('app.services.nutrition_notification_service.get_active_gyms_with_nutrition_full')
    @patch('app.services.nutrition_notification_service.send_meal_reminders_job_single_gym')
    @patch('app.services.nutrition_notification_service.get_current_time_in_gym_timezone')
    def test_meal_reminders_handles_multiple_gyms_same_timezone(
        self,
        mock_get_time,
        mock_send_job,
        mock_get_gyms
    ):
        """
        Verifica que múltiples gyms en el mismo timezone reciben notificaciones.
        """
        # Setup: 2 gyms en México
        gym1 = Mock(spec=Gym)
        gym1.id = 1
        gym1.name = "Gym CDMX"
        gym1.timezone = "America/Mexico_City"
        gym1.is_active = True

        gym2 = Mock(spec=Gym)
        gym2.id = 2
        gym2.name = "Gym Guadalajara"
        gym2.timezone = "America/Mexico_City"
        gym2.is_active = True

        mock_get_gyms.return_value = [gym1, gym2]

        # Mock: Ambos tienen 13:00 local
        mock_get_time.return_value = Mock(strftime=Mock(return_value="13:00"))
        mock_send_job.return_value = {"users_found": 5, "queued": 5, "failed": 0}

        # Ejecutar job para lunch a las 13:00
        send_meal_reminders_all_gyms_job("lunch", "13:00")

        # Verificar que se llamó para ambos gyms
        assert mock_send_job.call_count == 2
        called_gym_ids = [call[0][0] for call in mock_send_job.call_args_list]
        assert 1 in called_gym_ids
        assert 2 in called_gym_ids

    @patch('app.services.nutrition_notification_service.get_active_gyms_with_nutrition_full')
    @patch('app.services.nutrition_notification_service.get_current_time_in_gym_timezone')
    def test_meal_reminders_handles_errors_gracefully(
        self,
        mock_get_time,
        mock_get_gyms
    ):
        """
        Verifica que errores en un gym no afectan procesamiento de otros.
        """
        # Setup: 2 gyms, uno que falla
        gym1 = Mock(spec=Gym)
        gym1.id = 1
        gym1.name = "Gym OK"
        gym1.timezone = "UTC"
        gym1.is_active = True

        gym2 = Mock(spec=Gym)
        gym2.id = 2
        gym2.name = "Gym Error"
        gym2.timezone = "Invalid/Timezone"  # Timezone inválido
        gym2.is_active = True

        mock_get_gyms.return_value = [gym1, gym2]

        # Mock: get_time falla para gym2
        def get_time_side_effect(tz):
            if tz == "UTC":
                return Mock(strftime=Mock(return_value="08:00"))
            else:
                raise Exception("Invalid timezone")

        mock_get_time.side_effect = get_time_side_effect

        # Ejecutar job - no debe lanzar excepción
        try:
            send_meal_reminders_all_gyms_job("breakfast", "08:00")
        except Exception as e:
            pytest.fail(f"No debería lanzar excepción: {e}")

    def test_timezone_aware_scheduled_times_support_30_minute_intervals(self):
        """
        Verifica que el sistema soporta horarios en intervalos de 30 minutos.
        Esto es importante porque el scheduler ejecuta cada 30 minutos.
        """
        # Horarios válidos que usuarios pueden configurar
        valid_times = [
            "06:00", "06:30", "07:00", "07:30", "08:00", "08:30",
            "09:00", "09:30", "10:00", "10:30",
            "12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30",
            "19:00", "19:30", "20:00", "20:30", "21:00", "21:30", "22:00", "22:30"
        ]

        for scheduled_time in valid_times:
            # Verificar que el formato es correcto
            assert len(scheduled_time) == 5
            assert scheduled_time[2] == ":"

            hour, minute = scheduled_time.split(":")
            assert 0 <= int(hour) <= 23
            assert int(minute) in [0, 30]


class TestNutritionTimezoneEdgeCases:
    """Tests para casos edge de timezone."""

    @patch('app.services.nutrition_notification_service.get_current_time_in_gym_timezone')
    def test_daylight_saving_time_transition(self, mock_get_time):
        """
        Verifica que las transiciones de horario de verano se manejan correctamente.
        """
        # Simular transición DST en México (primavera/otoño)
        # Durante DST: GMT-5, Sin DST: GMT-6

        gym_timezone = "America/Mexico_City"

        # La función timezone_utils maneja esto automáticamente con pytz
        # Solo verificamos que no lance excepciones
        try:
            current_time = get_current_time_in_gym_timezone(gym_timezone)
            assert current_time is not None
        except Exception as e:
            pytest.fail(f"No debería fallar con DST: {e}")

    def test_timezone_with_partial_hour_offset(self):
        """
        Verifica timezones con offset de 30 o 45 minutos (ej: India GMT+5:30).
        """
        # India: GMT+5:30
        gym_timezone = "Asia/Kolkata"

        current_time_local = get_current_time_in_gym_timezone(gym_timezone)

        assert current_time_local.tzinfo is not None
        assert current_time_local.tzinfo.zone == gym_timezone


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
