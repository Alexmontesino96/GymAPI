"""
Tests de integración para el endpoint de cancelación administrativa de eventos.

Prueba el flujo completo de DELETE /api/v1/events/admin/{event_id} con:
- Autenticación y autorización
- Reembolsos automáticos 100%
- Notificaciones multi-canal
- Respuesta con estadísticas detalladas
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, Mock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.event import Event, EventParticipation, EventStatus, EventParticipationStatus, PaymentStatusType, RefundPolicyType
from app.models.user import User
from app.models.stripe_profile import GymStripeAccount


class TestAdminEventCancellationEndpoint:
    """Tests de integración para endpoint de cancelación administrativa."""

    @pytest.fixture
    def client(self):
        """Cliente de prueba de FastAPI."""
        return TestClient(app)

    @pytest.fixture
    def admin_token(self):
        """Token de autenticación de admin (mock)."""
        return "Bearer test_admin_token_with_admin_scope"

    @pytest.fixture
    def mock_event_paid(self, db_session):
        """Crear evento de pago de prueba en DB."""
        event = Event(
            id=9999,
            gym_id=1,
            title="Workshop de Nutrición Premium",
            description="Workshop exclusivo sobre nutrición deportiva",
            start_time=datetime.now(timezone.utc) + timedelta(days=7),
            end_time=datetime.now(timezone.utc) + timedelta(days=7, hours=2),
            location="Sala principal",
            max_participants=20,
            status=EventStatus.SCHEDULED,
            creator_id=1,
            is_paid=True,
            price_cents=4999,  # €49.99
            currency="EUR",
            refund_policy=RefundPolicyType.PARTIAL_REFUND,
            refund_deadline_hours=48
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)
        return event

    @pytest.fixture
    def mock_participations(self, db_session, mock_event_paid):
        """Crear participaciones de prueba."""
        participations = []

        # 3 participantes que ya pagaron
        for i in range(3):
            p = EventParticipation(
                event_id=mock_event_paid.id,
                member_id=100 + i,
                gym_id=1,
                status=EventParticipationStatus.REGISTERED,
                payment_status=PaymentStatusType.PAID,
                stripe_payment_intent_id=f"pi_test_integration_{i}",
                amount_paid_cents=4999,
                payment_date=datetime.now(timezone.utc) - timedelta(days=1)
            )
            db_session.add(p)
            participations.append(p)

        # 1 participante con pago pendiente
        p_pending = EventParticipation(
            event_id=mock_event_paid.id,
            member_id=200,
            gym_id=1,
            status=EventParticipationStatus.PENDING_PAYMENT,
            payment_status=PaymentStatusType.PENDING,
            stripe_payment_intent_id="pi_pending_test",
            amount_paid_cents=None,
            payment_date=None
        )
        db_session.add(p_pending)
        participations.append(p_pending)

        db_session.commit()
        return participations

    @patch('app.services.event_payment_service.stripe.Refund.create')
    @patch('app.services.event_payment_service.stripe.PaymentIntent.cancel')
    @patch('app.services.notification_service.OneSignalService.send_to_users')
    @patch('app.core.auth0_fastapi.auth.get_user')
    @patch('app.core.tenant.verify_gym_access')
    def test_admin_cancel_paid_event_with_refunds(
        self,
        mock_verify_gym,
        mock_get_user,
        mock_onesignal,
        mock_pi_cancel,
        mock_refund_create,
        client,
        admin_token,
        mock_event_paid,
        mock_participations,
        db_session
    ):
        """Test de cancelación completa de evento de pago con reembolsos."""
        # Configurar mocks de autenticación
        mock_user = Mock()
        mock_user.id = "auth0|admin123"
        mock_user.permissions = ["resource:admin"]
        mock_get_user.return_value = mock_user

        mock_gym = Mock()
        mock_gym.id = 1
        mock_gym.name = "Test Gym"
        mock_verify_gym.return_value = mock_gym

        # Mock de respuestas de Stripe (3 reembolsos exitosos)
        mock_refund_create.side_effect = [
            {"id": f"re_integration_test_{i}", "amount": 4999, "status": "succeeded"}
            for i in range(3)
        ]

        # Mock de OneSignal
        mock_onesignal.return_value = {
            "success": True,
            "notification_id": "notif_test_123",
            "recipients": 4
        }

        # Mock de usuario admin en BD
        admin_db_user = User(
            id=999,
            auth0_id="auth0|admin123",
            email="admin@test.com",
            name="Admin Test"
        )
        db_session.add(admin_db_user)
        db_session.commit()

        # Mock de cuenta Stripe
        stripe_account = GymStripeAccount(
            gym_id=1,
            stripe_account_id="acct_integration_test",
            charges_enabled=True
        )
        db_session.add(stripe_account)
        db_session.commit()

        # Ejecutar request
        response = client.delete(
            f"/api/v1/events/admin/{mock_event_paid.id}?reason=Problemas+técnicos+en+el+local",
            headers={"Authorization": admin_token}
        )

        # Verificaciones de respuesta
        assert response.status_code == 200
        data = response.json()

        assert data["event_id"] == mock_event_paid.id
        assert data["event_title"] == "Workshop de Nutrición Premium"
        assert data["cancellation_reason"] == "Problemas técnicos en el local"
        assert data["participants_count"] == 4
        assert data["refunds_processed"] == 3
        assert data["refunds_failed"] == 0
        assert data["payments_cancelled"] == 1
        assert data["total_refunded_amount"] == 3 * 4999  # €149.97
        assert data["currency"] == "EUR"
        assert len(data["failed_refunds"]) == 0

        # Verificar notificaciones enviadas
        assert data["notifications_sent"]["push"] == 4

        # Verificar llamadas a Stripe
        assert mock_refund_create.call_count == 3
        assert mock_pi_cancel.call_count == 1

        # Verificar estado del evento en BD
        db_session.refresh(mock_event_paid)
        assert mock_event_paid.status == EventStatus.CANCELLED
        assert mock_event_paid.cancelled_by_user_id == admin_db_user.id
        assert mock_event_paid.cancellation_reason == "Problemas técnicos en el local"
        assert mock_event_paid.total_refunded_cents == 3 * 4999

    @patch('app.core.auth0_fastapi.auth.get_user')
    @patch('app.core.tenant.verify_gym_access')
    def test_admin_cancel_free_event_no_refunds(
        self,
        mock_verify_gym,
        mock_get_user,
        client,
        admin_token,
        db_session
    ):
        """Test de cancelación de evento gratuito (sin reembolsos)."""
        # Crear evento gratuito
        free_event = Event(
            id=8888,
            gym_id=1,
            title="Clase de Yoga Gratuita",
            description="Clase abierta para todos",
            start_time=datetime.now(timezone.utc) + timedelta(days=3),
            end_time=datetime.now(timezone.utc) + timedelta(days=3, hours=1),
            location="Sala 2",
            max_participants=30,
            status=EventStatus.SCHEDULED,
            creator_id=1,
            is_paid=False,
            price_cents=None
        )
        db_session.add(free_event)

        # Participantes sin pago
        for i in range(5):
            p = EventParticipation(
                event_id=free_event.id,
                member_id=300 + i,
                gym_id=1,
                status=EventParticipationStatus.REGISTERED,
                payment_status=None
            )
            db_session.add(p)

        db_session.commit()

        # Configurar mocks
        mock_user = Mock()
        mock_user.id = "auth0|admin123"
        mock_user.permissions = ["resource:admin"]
        mock_get_user.return_value = mock_user

        mock_gym = Mock()
        mock_gym.id = 1
        mock_verify_gym.return_value = mock_gym

        # Ejecutar request
        response = client.delete(
            f"/api/v1/events/admin/{free_event.id}",
            headers={"Authorization": admin_token}
        )

        # Verificaciones
        assert response.status_code == 200
        data = response.json()

        assert data["event_id"] == free_event.id
        assert data["participants_count"] == 5
        assert data["refunds_processed"] == 0
        assert data["refunds_failed"] == 0
        assert data["payments_cancelled"] == 0
        assert data["total_refunded_amount"] == 0

        # Verificar que participaciones están canceladas
        participations = db_session.query(EventParticipation).filter(
            EventParticipation.event_id == free_event.id
        ).all()
        for p in participations:
            assert p.status == EventParticipationStatus.CANCELLED

    @patch('app.core.auth0_fastapi.auth.get_user')
    @patch('app.core.tenant.verify_gym_access')
    def test_admin_cancel_nonexistent_event_404(
        self,
        mock_verify_gym,
        mock_get_user,
        client,
        admin_token
    ):
        """Test de error 404 para evento inexistente."""
        # Configurar mocks
        mock_user = Mock()
        mock_user.id = "auth0|admin123"
        mock_user.permissions = ["resource:admin"]
        mock_get_user.return_value = mock_user

        mock_gym = Mock()
        mock_gym.id = 1
        mock_verify_gym.return_value = mock_gym

        # Ejecutar request con ID inexistente
        response = client.delete(
            "/api/v1/events/admin/99999999",
            headers={"Authorization": admin_token}
        )

        # Verificaciones
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch('app.core.auth0_fastapi.auth.get_user')
    @patch('app.core.tenant.verify_gym_access')
    def test_admin_cancel_already_cancelled_event_400(
        self,
        mock_verify_gym,
        mock_get_user,
        client,
        admin_token,
        db_session
    ):
        """Test de error 400 para evento ya cancelado."""
        # Crear evento ya cancelado
        cancelled_event = Event(
            id=7777,
            gym_id=1,
            title="Evento Ya Cancelado",
            description="Test",
            start_time=datetime.now(timezone.utc) + timedelta(days=5),
            end_time=datetime.now(timezone.utc) + timedelta(days=5, hours=1),
            location="Sala 1",
            max_participants=10,
            status=EventStatus.CANCELLED,  # Ya cancelado
            creator_id=1,
            is_paid=False
        )
        db_session.add(cancelled_event)
        db_session.commit()

        # Configurar mocks
        mock_user = Mock()
        mock_user.id = "auth0|admin123"
        mock_user.permissions = ["resource:admin"]
        mock_get_user.return_value = mock_user

        mock_gym = Mock()
        mock_gym.id = 1
        mock_verify_gym.return_value = mock_gym

        # Ejecutar request
        response = client.delete(
            f"/api/v1/events/admin/{cancelled_event.id}",
            headers={"Authorization": admin_token}
        )

        # Verificaciones
        assert response.status_code == 400
        assert "already cancelled" in response.json()["detail"].lower()

    @patch('app.services.event_payment_service.stripe.Refund.create')
    @patch('app.core.auth0_fastapi.auth.get_user')
    @patch('app.core.tenant.verify_gym_access')
    def test_admin_cancel_with_partial_refund_failures(
        self,
        mock_verify_gym,
        mock_get_user,
        mock_refund_create,
        client,
        admin_token,
        mock_event_paid,
        mock_participations,
        db_session
    ):
        """Test de cancelación con algunos reembolsos fallidos."""
        import stripe as stripe_lib

        # Configurar mocks
        mock_user = Mock()
        mock_user.id = "auth0|admin123"
        mock_user.permissions = ["resource:admin"]
        mock_get_user.return_value = mock_user

        mock_gym = Mock()
        mock_gym.id = 1
        mock_verify_gym.return_value = mock_gym

        # Mock usuario admin en BD
        admin_db_user = User(
            id=999,
            auth0_id="auth0|admin123",
            email="admin@test.com",
            name="Admin Test"
        )
        db_session.add(admin_db_user)

        # Mock Stripe account
        stripe_account = GymStripeAccount(
            gym_id=1,
            stripe_account_id="acct_test",
            charges_enabled=True
        )
        db_session.add(stripe_account)
        db_session.commit()

        # Mock de Stripe - primer reembolso falla, otros exitosos
        mock_refund_create.side_effect = [
            stripe_lib.error.StripeError("Card was declined"),
            {"id": "re_test_2", "amount": 4999, "status": "succeeded"},
            {"id": "re_test_3", "amount": 4999, "status": "succeeded"}
        ]

        # Ejecutar request
        response = client.delete(
            f"/api/v1/events/admin/{mock_event_paid.id}",
            headers={"Authorization": admin_token}
        )

        # Verificaciones
        assert response.status_code == 200
        data = response.json()

        assert data["refunds_processed"] == 2  # Solo 2 exitosos
        assert data["refunds_failed"] == 1  # 1 falló
        assert len(data["failed_refunds"]) == 1
        assert "Card was declined" in data["failed_refunds"][0]["error"]

        # Evento debe seguir cancelándose
        db_session.refresh(mock_event_paid)
        assert mock_event_paid.status == EventStatus.CANCELLED


class TestEventCancellationPermissions:
    """Tests de permisos y autorización."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @patch('app.core.auth0_fastapi.auth.get_user')
    def test_member_cannot_cancel_event(
        self,
        mock_get_user,
        client,
        db_session
    ):
        """Test que verifica que un member no puede cancelar eventos."""
        # Mock de usuario sin permisos admin
        mock_user = Mock()
        mock_user.id = "auth0|member123"
        mock_user.permissions = ["resource:member"]  # Sin scope admin
        mock_get_user.return_value = mock_user

        # Crear evento
        event = Event(
            id=6666,
            gym_id=1,
            title="Evento Test",
            start_time=datetime.now(timezone.utc) + timedelta(days=1),
            end_time=datetime.now(timezone.utc) + timedelta(days=1, hours=1),
            status=EventStatus.SCHEDULED,
            creator_id=1,
            is_paid=False
        )
        db_session.add(event)
        db_session.commit()

        # Ejecutar request
        response = client.delete(
            f"/api/v1/events/admin/{event.id}",
            headers={"Authorization": "Bearer member_token"}
        )

        # Verificaciones - debe fallar con 403 Forbidden
        assert response.status_code == 403
