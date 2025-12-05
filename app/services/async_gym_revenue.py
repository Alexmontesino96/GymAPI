"""
AsyncGymRevenueService - Servicio async para tracking de ingresos por gimnasio.

Este módulo proporciona un servicio totalmente async para contabilidad de pagos
en arquitectura multi-tenant con Stripe.

Migrado en FASE 3 de la conversión sync → async.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
import logging
import stripe

from app.core.config import get_settings
from app.models.gym import Gym
from app.models.user_gym import UserGym
from app.models.membership import MembershipPlan

settings = get_settings()
logger = logging.getLogger(__name__)


class AsyncGymRevenueService:
    """
    Servicio async para gestionar ingresos y distribución de pagos por gimnasio.

    Todos los métodos son async y utilizan AsyncSession.

    Arquitectura Multi-tenant con Stripe:
    - Una sola cuenta Stripe para toda la plataforma
    - Cada pago incluye gym_id en metadata
    - Tracking separado de ingresos por gimnasio
    - Cálculo automático de comisiones de plataforma

    Métodos principales:
    - get_gym_revenue_summary() - Resumen de ingresos de un gimnasio
    - get_platform_revenue_summary() - Resumen total de la plataforma
    - calculate_gym_payout() - Calcular pago a gimnasio
    """

    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY

    async def get_gym_revenue_summary(
        self,
        db: AsyncSession,
        gym_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Obtener resumen de ingresos de un gimnasio específico.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            start_date: Fecha de inicio (default: último mes)
            end_date: Fecha de fin (default: ahora)

        Returns:
            Dict con resumen de ingresos:
            - revenue: total_gross, platform_fee, gym_net
            - transactions: total_count, by_plan
            - metrics: average_transaction, platform_fee_rate

        Raises:
            ValueError: Si el gimnasio no existe

        Note:
            Busca pagos en Stripe (charges + invoices) con gym_id en metadata.
            Comisión de plataforma: 5% (configurable).
        """
        try:
            # Fechas por defecto: último mes
            if not end_date:
                end_date = datetime.now(timezone.utc)
            if not start_date:
                start_date = end_date - timedelta(days=30)

            # Obtener información del gimnasio
            result = await db.execute(
                select(Gym).where(Gym.id == gym_id)
            )
            gym = result.scalar_one_or_none()

            if not gym:
                raise ValueError(f"Gimnasio {gym_id} no encontrado")

            # Buscar todos los pagos de este gimnasio en Stripe
            payments = await self._get_stripe_payments_for_gym(gym_id, start_date, end_date)

            # Calcular métricas
            total_revenue = sum(payment['amount'] for payment in payments) / 100  # Convertir de centavos
            total_transactions = len(payments)

            # Agrupar por tipo de plan
            revenue_by_plan = {}
            for payment in payments:
                plan_name = payment.get('metadata', {}).get('plan_name', 'Unknown')
                if plan_name not in revenue_by_plan:
                    revenue_by_plan[plan_name] = {'count': 0, 'revenue': 0}
                revenue_by_plan[plan_name]['count'] += 1
                revenue_by_plan[plan_name]['revenue'] += payment['amount'] / 100

            # Calcular comisión de la plataforma (ejemplo: 5%)
            platform_fee_rate = 0.05
            platform_fee = total_revenue * platform_fee_rate
            gym_net_revenue = total_revenue - platform_fee

            return {
                'gym_id': gym_id,
                'gym_name': gym.name,
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'revenue': {
                    'total_gross': total_revenue,
                    'platform_fee': platform_fee,
                    'gym_net': gym_net_revenue,
                    'currency': 'EUR'  # O la moneda que uses
                },
                'transactions': {
                    'total_count': total_transactions,
                    'by_plan': revenue_by_plan
                },
                'metrics': {
                    'average_transaction': total_revenue / total_transactions if total_transactions > 0 else 0,
                    'platform_fee_rate': platform_fee_rate
                }
            }

        except Exception as e:
            logger.error(f"Error obteniendo resumen de ingresos para gym {gym_id}: {str(e)}")
            raise

    async def _get_stripe_payments_for_gym(
        self,
        gym_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Obtener todos los pagos de Stripe para un gimnasio específico.

        Args:
            gym_id: ID del gimnasio
            start_date: Fecha de inicio
            end_date: Fecha de fin

        Returns:
            Lista de pagos de Stripe (charges + invoices)

        Note:
            Método async pero Stripe SDK es sync - ejecuta en thread separado
            si fuera necesario. Por ahora se mantiene sync dentro de async.
        """
        try:
            # Convertir fechas a timestamps
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())

            # Buscar charges (pagos únicos) y invoices (suscripciones)
            gym_payments = []

            # 1. Buscar charges (pagos únicos)
            charges = stripe.Charge.list(
                created={
                    'gte': start_timestamp,
                    'lte': end_timestamp
                },
                limit=100,
                expand=['data.metadata']
            )

            for charge in charges.data:
                if charge.metadata.get('gym_id') == str(gym_id) and charge.status == 'succeeded':
                    gym_payments.append({
                        'id': charge.id,
                        'type': 'charge',
                        'amount': charge.amount,
                        'currency': charge.currency,
                        'created': charge.created,
                        'metadata': charge.metadata,
                        'description': charge.description
                    })

            # 2. Buscar invoices (suscripciones)
            invoices = stripe.Invoice.list(
                created={
                    'gte': start_timestamp,
                    'lte': end_timestamp
                },
                status='paid',
                limit=100,
                expand=['data.metadata', 'data.subscription']
            )

            for invoice in invoices.data:
                # Verificar si pertenece al gimnasio (puede estar en metadata del invoice o subscription)
                gym_id_meta = invoice.metadata.get('gym_id')
                if not gym_id_meta and invoice.subscription:
                    # Buscar en metadata de la suscripción
                    subscription = stripe.Subscription.retrieve(invoice.subscription)
                    gym_id_meta = subscription.metadata.get('gym_id')

                if gym_id_meta == str(gym_id):
                    gym_payments.append({
                        'id': invoice.id,
                        'type': 'invoice',
                        'amount': invoice.amount_paid,
                        'currency': invoice.currency,
                        'created': invoice.created,
                        'metadata': invoice.metadata,
                        'description': f"Subscription payment - {invoice.subscription}"
                    })

            logger.info(f"Encontrados {len(gym_payments)} pagos para gym {gym_id}")
            return gym_payments

        except stripe.error.StripeError as e:
            logger.error(f"Error obteniendo pagos de Stripe para gym {gym_id}: {str(e)}")
            return []

    async def get_platform_revenue_summary(
        self,
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Obtener resumen de ingresos de toda la plataforma.

        Args:
            db: Sesión async de base de datos
            start_date: Fecha de inicio (default: último mes)
            end_date: Fecha de fin (default: ahora)

        Returns:
            Dict con resumen de plataforma:
            - totals: gross_revenue, platform_fees, gym_payouts
            - gyms: Lista con resumen por gimnasio

        Note:
            Agrega los ingresos de todos los gimnasios activos.
        """
        try:
            # Fechas por defecto: último mes
            if not end_date:
                end_date = datetime.now(timezone.utc)
            if not start_date:
                start_date = end_date - timedelta(days=30)

            # Obtener todos los gimnasios activos
            result = await db.execute(
                select(Gym).where(Gym.is_active == True)
            )
            active_gyms = result.scalars().all()

            platform_summary = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'totals': {
                    'gross_revenue': 0,
                    'platform_fees': 0,
                    'gym_payouts': 0,
                    'total_transactions': 0
                },
                'gyms': []
            }

            # Obtener resumen para cada gimnasio
            for gym in active_gyms:
                gym_summary = await self.get_gym_revenue_summary(
                    db, gym.id, start_date, end_date
                )

                # Agregar a totales de la plataforma
                platform_summary['totals']['gross_revenue'] += gym_summary['revenue']['total_gross']
                platform_summary['totals']['platform_fees'] += gym_summary['revenue']['platform_fee']
                platform_summary['totals']['gym_payouts'] += gym_summary['revenue']['gym_net']
                platform_summary['totals']['total_transactions'] += gym_summary['transactions']['total_count']

                # Agregar resumen del gimnasio
                platform_summary['gyms'].append({
                    'gym_id': gym.id,
                    'gym_name': gym.name,
                    'revenue': gym_summary['revenue'],
                    'transaction_count': gym_summary['transactions']['total_count']
                })

            return platform_summary

        except Exception as e:
            logger.error(f"Error obteniendo resumen de plataforma: {str(e)}")
            raise

    async def calculate_gym_payout(
        self,
        db: AsyncSession,
        gym_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Calcular el pago que debe recibir un gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            start_date: Fecha de inicio del período
            end_date: Fecha de fin del período

        Returns:
            Dict con detalles del payout:
            - payout_amount: Monto neto a pagar
            - gross_revenue: Ingresos brutos
            - platform_fee: Comisión de la plataforma
            - transaction_count: Número de transacciones
            - status: Estado del payout (pending)

        Note:
            Este método calcula el payout pero no lo ejecuta.
            Para ejecutar el payout se necesitaría integración con
            Stripe Connect o transferencias manuales.
        """
        try:
            # Obtener resumen de ingresos
            revenue_summary = await self.get_gym_revenue_summary(
                db, gym_id, start_date, end_date
            )

            # Obtener información bancaria del gimnasio (si la tienes almacenada)
            result = await db.execute(
                select(Gym).where(Gym.id == gym_id)
            )
            gym = result.scalar_one_or_none()

            payout_details = {
                'gym_id': gym_id,
                'gym_name': gym.name if gym else 'Unknown',
                'period': revenue_summary['period'],
                'payout_amount': revenue_summary['revenue']['gym_net'],
                'currency': revenue_summary['revenue']['currency'],
                'transaction_count': revenue_summary['transactions']['total_count'],
                'gross_revenue': revenue_summary['revenue']['total_gross'],
                'platform_fee': revenue_summary['revenue']['platform_fee'],
                'status': 'pending',
                'created_at': datetime.now(timezone.utc).isoformat()
            }

            logger.info(f"Payout calculado para gym {gym_id}: {payout_details['payout_amount']}")
            return payout_details

        except Exception as e:
            logger.error(f"Error calculando payout para gym {gym_id}: {str(e)}")
            raise


# Instancia singleton del servicio async
async_gym_revenue_service = AsyncGymRevenueService()
