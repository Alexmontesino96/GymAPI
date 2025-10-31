"""
Tests para la funcionalidad de cancelación de eventos con reembolsos automáticos.

Este módulo prueba:
- Cancelación de eventos de pago con reembolsos automáticos 100%
- Cancelación de Payment Intents pendientes
- Notificaciones multi-canal
- Auditoría de cancelaciones
- Manejo de errores en reembolsos parciales
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

from app.models.event import Event, EventParticipation, EventStatus, EventParticipationStatus, PaymentStatusType, RefundPolicyType
from app.models.user import User
from app.models.stripe_profile import GymStripeAccount
from app.services.event_payment_service import event_payment_service


class TestEventCancellationWithRefunds:
    """Tests unitarios para cancelación de eventos con reembolsos."""

    @pytest.fixture
    def mock_db(self):
        """Mock de sesión de base de datos."""
        db = MagicMock(spec=Session)
        db.commit = Mock()
        db.rollback = Mock()
        db.query = Mock()
        return db

    @pytest.fixture
    def mock_event(self):
        """Mock de evento de pago."""
        event = Mock(spec=Event)
        event.id = 1
        event.title = "Workshop de Yoga Avanzado"
        event.gym_id = 1
        event.is_paid = True
        event.price_cents = 2999  # €29.99
        event.currency = "EUR"
        event.status = EventStatus.SCHEDULED
        event.refund_policy = RefundPolicyType.PARTIAL_REFUND
        event.refund_deadline_hours = 24
        event.cancellation_date = None
        event.cancelled_by_user_id = None
        event.cancellation_reason = None
        event.total_refunded_cents = None
        return event

    @pytest.fixture
    def mock_stripe_account(self):
        """Mock de cuenta Stripe del gimnasio."""
        account = Mock(spec=GymStripeAccount)
        account.gym_id = 1
        account.stripe_account_id = "acct_test123"
        account.charges_enabled = True
        return account

    @pytest.fixture
    def mock_participations_paid(self):
        """Mock de participaciones con pago completado."""
        participations = []
        for i in range(3):
            p = Mock(spec=EventParticipation)
            p.id = i + 1
            p.event_id = 1
            p.member_id = 100 + i
            p.gym_id = 1
            p.status = EventParticipationStatus.REGISTERED
            p.payment_status = PaymentStatusType.PAID
            p.stripe_payment_intent_id = f"pi_test_{i}"
            p.amount_paid_cents = 2999
            p.payment_date = datetime.now(timezone.utc) - timedelta(days=2)
            p.refund_date = None
            p.refund_amount_cents = None
            participations.append(p)
        return participations

    @pytest.fixture
    def mock_participations_pending(self):
        """Mock de participaciones con pago pendiente."""
        participations = []
        for i in range(2):
            p = Mock(spec=EventParticipation)
            p.id = 10 + i
            p.event_id = 1
            p.member_id = 200 + i
            p.gym_id = 1
            p.status = EventParticipationStatus.PENDING_PAYMENT
            p.payment_status = PaymentStatusType.PENDING
            p.stripe_payment_intent_id = f"pi_pending_{i}"
            p.amount_paid_cents = None
            p.payment_date = None
            p.refund_date = None
            p.refund_amount_cents = None
            participations.append(p)
        return participations

    @pytest.mark.asyncio
    @patch('app.services.event_payment_service.stripe.Refund.create')
    @patch('app.services.event_payment_service.stripe.PaymentIntent.cancel')
    async def test_cancel_event_with_full_refunds_success(
        self,
        mock_pi_cancel,
        mock_refund_create,
        mock_db,
        mock_event,
        mock_stripe_account,
        mock_participations_paid,
        mock_participations_pending
    ):
        """Test de cancelación exitosa con reembolsos completos."""
        # Configurar mocks
        all_participations = mock_participations_paid + mock_participations_pending

        # Mock de query para obtener Stripe account
        mock_db.query.return_value.filter.return_value.first.return_value = mock_stripe_account

        # Mock de query para obtener participaciones
        mock_query_participations = Mock()
        mock_query_participations.filter.return_value.all.return_value = all_participations
        mock_db.query.side_effect = [
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_stripe_account)))),
            mock_query_participations
        ]

        # Mock de respuestas de Stripe
        mock_refund_create.side_effect = [
            {"id": f"re_test_{i}", "amount": 2999, "status": "succeeded"}
            for i in range(len(mock_participations_paid))
        ]

        # Ejecutar cancelación
        result = await event_payment_service.cancel_event_with_full_refunds(
            db=mock_db,
            event=mock_event,
            gym_id=1,
            cancelled_by_user_id=999,
            reason="Evento cancelado por problemas de logística"
        )

        # Verificaciones
        assert result["participants_count"] == 5
        assert result["refunds_processed"] == 3
        assert result["refunds_failed"] == 0
        assert result["payments_cancelled"] == 2
        assert result["total_refunded_cents"] == 3 * 2999  # 3 reembolsos de €29.99

        # Verificar que se llamó a Stripe Refund.create 3 veces (uno por cada participante pagado)
        assert mock_refund_create.call_count == 3

        # Verificar que se cancelaron 2 Payment Intents pendientes
        assert mock_pi_cancel.call_count == 2

        # Verificar que se actualizó el evento
        assert mock_event.status == EventStatus.CANCELLED
        assert mock_event.cancelled_by_user_id == 999
        assert mock_event.cancellation_reason == "Evento cancelado por problemas de logística"
        assert mock_event.total_refunded_cents == 3 * 2999

        # Verificar commit
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.services.event_payment_service.stripe.Refund.create')
    async def test_cancel_event_with_partial_refund_failures(
        self,
        mock_refund_create,
        mock_db,
        mock_event,
        mock_stripe_account,
        mock_participations_paid
    ):
        """Test de cancelación con algunos reembolsos fallidos."""
        import stripe as stripe_lib

        # Configurar mocks - primer reembolso falla, los demás exitosos
        mock_refund_create.side_effect = [
            stripe_lib.error.StripeError("Insufficient funds in connected account"),
            {"id": "re_test_2", "amount": 2999, "status": "succeeded"},
            {"id": "re_test_3", "amount": 2999, "status": "succeeded"}
        ]

        # Mock de queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_stripe_account

        mock_query_participations = Mock()
        mock_query_participations.filter.return_value.all.return_value = mock_participations_paid
        mock_db.query.side_effect = [
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_stripe_account)))),
            mock_query_participations
        ]

        # Ejecutar cancelación
        result = await event_payment_service.cancel_event_with_full_refunds(
            db=mock_db,
            event=mock_event,
            gym_id=1,
            cancelled_by_user_id=999,
            reason="Test de fallos parciales"
        )

        # Verificaciones
        assert result["participants_count"] == 3
        assert result["refunds_processed"] == 2  # Solo 2 exitosos
        assert result["refunds_failed"] == 1  # 1 falló
        assert result["payments_cancelled"] == 0
        assert result["total_refunded_cents"] == 2 * 2999  # Solo 2 reembolsos

        # Verificar que hay un error registrado
        assert len(result["failed_refunds"]) == 1
        assert result["failed_refunds"][0]["participation_id"] == 1
        assert "Insufficient funds" in result["failed_refunds"][0]["error"]

        # Verificar que se intentaron los 3 reembolsos
        assert mock_refund_create.call_count == 3

        # Verificar que el evento se marcó como cancelado de todas formas
        assert mock_event.status == EventStatus.CANCELLED
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_event_without_stripe_account_fails(
        self,
        mock_db,
        mock_event
    ):
        """Test que verifica que falla si no hay cuenta de Stripe."""
        # Mock de query que devuelve None (sin cuenta Stripe)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Verificar que se lanza excepción
        with pytest.raises(ValueError, match="No se encontró cuenta de Stripe"):
            await event_payment_service.cancel_event_with_full_refunds(
                db=mock_db,
                event=mock_event,
                gym_id=1,
                cancelled_by_user_id=999,
                reason="Test sin Stripe"
            )

        # Verificar que se hizo rollback
        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.services.event_payment_service.stripe.Refund.create')
    async def test_cancel_event_with_participations_without_payment_intent(
        self,
        mock_refund_create,
        mock_db,
        mock_event,
        mock_stripe_account
    ):
        """Test con participaciones PAID pero sin stripe_payment_intent_id (caso edge)."""
        # Participación pagada pero sin payment_intent_id (inconsistencia de datos)
        participation = Mock(spec=EventParticipation)
        participation.id = 999
        participation.event_id = 1
        participation.member_id = 500
        participation.gym_id = 1
        participation.status = EventParticipationStatus.REGISTERED
        participation.payment_status = PaymentStatusType.PAID
        participation.stripe_payment_intent_id = None  # Sin Payment Intent ID
        participation.amount_paid_cents = 2999

        # Mock queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_stripe_account

        mock_query_participations = Mock()
        mock_query_participations.filter.return_value.all.return_value = [participation]
        mock_db.query.side_effect = [
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_stripe_account)))),
            mock_query_participations
        ]

        # Ejecutar
        result = await event_payment_service.cancel_event_with_full_refunds(
            db=mock_db,
            event=mock_event,
            gym_id=1,
            cancelled_by_user_id=999,
            reason="Test edge case"
        )

        # Verificaciones
        assert result["participants_count"] == 1
        assert result["refunds_processed"] == 0
        assert result["refunds_failed"] == 1
        assert result["failed_refunds"][0]["error"] == "Sin Payment Intent ID"

        # No debe haber llamado a Stripe
        mock_refund_create.assert_not_called()

        # Evento debe seguir cancelándose
        assert mock_event.status == EventStatus.CANCELLED
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_free_event_no_refunds(
        self,
        mock_db,
        mock_event
    ):
        """Test de cancelación de evento gratuito (sin reembolsos)."""
        # Configurar evento como gratuito
        mock_event.is_paid = False
        mock_event.price_cents = None

        # Participaciones sin pago
        participations = []
        for i in range(3):
            p = Mock(spec=EventParticipation)
            p.id = i + 1
            p.status = EventParticipationStatus.REGISTERED
            p.payment_status = None
            participations.append(p)

        # Mock queries
        mock_query_participations = Mock()
        mock_query_participations.filter.return_value.all.return_value = participations
        mock_db.query.return_value = mock_query_participations

        # Ejecutar (evento gratuito no necesita Stripe account)
        result = await event_payment_service.cancel_event_with_full_refunds(
            db=mock_db,
            event=mock_event,
            gym_id=1,
            cancelled_by_user_id=999,
            reason="Cancelación de evento gratuito"
        )

        # Verificaciones - evento gratuito no procesa reembolsos
        assert result["participants_count"] == 3
        assert result["refunds_processed"] == 0
        assert result["refunds_failed"] == 0
        assert result["payments_cancelled"] == 0
        assert result["total_refunded_cents"] == 0

        # Todas las participaciones deben estar canceladas
        for p in participations:
            assert p.status == EventParticipationStatus.CANCELLED

        assert mock_event.status == EventStatus.CANCELLED
        mock_db.commit.assert_called_once()


class TestEventCancellationAudit:
    """Tests para auditoría de cancelaciones."""

    @pytest.mark.asyncio
    @patch('app.services.event_payment_service.stripe.Refund.create')
    async def test_event_audit_fields_populated(
        self,
        mock_refund_create,
        mock_db,
        mock_event,
        mock_stripe_account,
        mock_participations_paid
    ):
        """Verificar que los campos de auditoría se populan correctamente."""
        # Configurar mocks
        mock_refund_create.return_value = {"id": "re_test", "amount": 2999, "status": "succeeded"}

        mock_db.query.return_value.filter.return_value.first.return_value = mock_stripe_account

        mock_query_participations = Mock()
        mock_query_participations.filter.return_value.all.return_value = mock_participations_paid
        mock_db.query.side_effect = [
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_stripe_account)))),
            mock_query_participations
        ]

        cancellation_reason = "Instructor enfermo"
        admin_user_id = 777

        # Ejecutar
        await event_payment_service.cancel_event_with_full_refunds(
            db=mock_db,
            event=mock_event,
            gym_id=1,
            cancelled_by_user_id=admin_user_id,
            reason=cancellation_reason
        )

        # Verificar campos de auditoría
        assert mock_event.status == EventStatus.CANCELLED
        assert mock_event.cancelled_by_user_id == admin_user_id
        assert mock_event.cancellation_reason == cancellation_reason
        assert mock_event.cancellation_date is not None
        assert mock_event.total_refunded_cents == 3 * 2999

    # Fixtures reutilizadas de la clase anterior
    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=Session)
        db.commit = Mock()
        db.rollback = Mock()
        db.query = Mock()
        return db

    @pytest.fixture
    def mock_event(self):
        event = Mock(spec=Event)
        event.id = 1
        event.title = "Workshop de Yoga Avanzado"
        event.gym_id = 1
        event.is_paid = True
        event.price_cents = 2999
        event.currency = "EUR"
        event.status = EventStatus.SCHEDULED
        event.refund_policy = RefundPolicyType.PARTIAL_REFUND
        event.refund_deadline_hours = 24
        event.cancellation_date = None
        event.cancelled_by_user_id = None
        event.cancellation_reason = None
        event.total_refunded_cents = None
        return event

    @pytest.fixture
    def mock_stripe_account(self):
        account = Mock(spec=GymStripeAccount)
        account.gym_id = 1
        account.stripe_account_id = "acct_test123"
        account.charges_enabled = True
        return account

    @pytest.fixture
    def mock_participations_paid(self):
        participations = []
        for i in range(3):
            p = Mock(spec=EventParticipation)
            p.id = i + 1
            p.event_id = 1
            p.member_id = 100 + i
            p.gym_id = 1
            p.status = EventParticipationStatus.REGISTERED
            p.payment_status = PaymentStatusType.PAID
            p.stripe_payment_intent_id = f"pi_test_{i}"
            p.amount_paid_cents = 2999
            p.payment_date = datetime.now(timezone.utc) - timedelta(days=2)
            p.refund_date = None
            p.refund_amount_cents = None
            participations.append(p)
        return participations
