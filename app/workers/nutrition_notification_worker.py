"""
Worker para procesar notificaciones de nutrición desde SQS.

Este worker corre como un proceso separado y consume mensajes
de la cola SQS de forma continua.

Uso:
    python -m app.workers.nutrition_notification_worker

    O con múltiples workers:
    python -m app.workers.nutrition_notification_worker --workers 3
"""

import argparse
import logging
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

# Configurar logging antes de importar otros módulos
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NutritionNotificationWorker:
    """
    Worker que procesa notificaciones de nutrición desde SQS.

    Características:
    - Long polling para eficiencia
    - Graceful shutdown con signals
    - Métricas de procesamiento
    - Reintentos automáticos (manejados por SQS)
    """

    def __init__(
        self,
        worker_id: int = 0,
        batch_size: int = 10,
        poll_interval: int = 1
    ):
        """
        Inicializar worker.

        Args:
            worker_id: ID único del worker (para logs)
            batch_size: Mensajes a procesar por iteración (1-10)
            poll_interval: Segundos entre polls si no hay mensajes
        """
        self.worker_id = worker_id
        self.batch_size = min(batch_size, 10)  # SQS límite es 10
        self.poll_interval = poll_interval
        self.running = False
        self.processed_count = 0
        self.failed_count = 0
        self.start_time: Optional[datetime] = None

        # Importar servicio SQS
        from app.services.sqs_notification_service import sqs_notification_service
        self.sqs_service = sqs_notification_service

    def start(self):
        """Iniciar el worker"""
        if not self.sqs_service.enabled:
            logger.error("SQS not configured. Worker cannot start.")
            return

        self.running = True
        self.start_time = datetime.now()

        logger.info(
            f"Worker {self.worker_id} started. "
            f"Batch size: {self.batch_size}, Poll interval: {self.poll_interval}s"
        )

        # Registrar handler para señales de shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self._run_loop()

    def stop(self):
        """Detener el worker de forma graceful"""
        logger.info(f"Worker {self.worker_id} stopping...")
        self.running = False

    def _signal_handler(self, signum, frame):
        """Handler para señales de sistema"""
        logger.info(f"Received signal {signum}")
        self.stop()

    def _run_loop(self):
        """Loop principal del worker"""
        consecutive_empty = 0

        while self.running:
            try:
                # Procesar mensajes
                results = self.sqs_service.process_messages(
                    max_messages=self.batch_size
                )

                processed = results.get("processed", 0)
                failed = results.get("failed", 0)

                self.processed_count += processed
                self.failed_count += failed

                if processed > 0 or failed > 0:
                    consecutive_empty = 0
                    logger.info(
                        f"Worker {self.worker_id}: Processed {processed}, Failed {failed}. "
                        f"Total: {self.processed_count} processed, {self.failed_count} failed"
                    )
                else:
                    consecutive_empty += 1
                    # Log cada 10 iteraciones vacías
                    if consecutive_empty % 10 == 0:
                        logger.debug(f"Worker {self.worker_id}: No messages ({consecutive_empty} empty polls)")

                # Si no hay mensajes, esperar antes del siguiente poll
                if processed == 0 and failed == 0:
                    time.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Worker {self.worker_id} error: {e}", exc_info=True)
                time.sleep(5)  # Esperar antes de reintentar

        self._print_stats()

    def _print_stats(self):
        """Imprimir estadísticas del worker"""
        if self.start_time:
            runtime = (datetime.now() - self.start_time).total_seconds()
            rate = self.processed_count / runtime if runtime > 0 else 0

            logger.info(
                f"\n{'='*50}\n"
                f"Worker {self.worker_id} Statistics\n"
                f"{'='*50}\n"
                f"Runtime: {runtime:.1f}s\n"
                f"Processed: {self.processed_count}\n"
                f"Failed: {self.failed_count}\n"
                f"Rate: {rate:.2f} msg/s\n"
                f"{'='*50}"
            )

    def get_stats(self) -> dict:
        """Obtener estadísticas actuales"""
        runtime = 0
        if self.start_time:
            runtime = (datetime.now() - self.start_time).total_seconds()

        return {
            "worker_id": self.worker_id,
            "running": self.running,
            "runtime_seconds": runtime,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "messages_per_second": self.processed_count / runtime if runtime > 0 else 0
        }


class WorkerPool:
    """Pool de workers para procesamiento paralelo"""

    def __init__(self, num_workers: int = 3, batch_size: int = 10):
        self.num_workers = num_workers
        self.batch_size = batch_size
        self.workers = []
        self.executor: Optional[ThreadPoolExecutor] = None

    def start(self):
        """Iniciar pool de workers"""
        logger.info(f"Starting worker pool with {self.num_workers} workers")

        self.executor = ThreadPoolExecutor(max_workers=self.num_workers)

        for i in range(self.num_workers):
            worker = NutritionNotificationWorker(
                worker_id=i,
                batch_size=self.batch_size
            )
            self.workers.append(worker)
            self.executor.submit(worker.start)

        # Esperar a que se termine (bloqueante)
        try:
            while any(w.running for w in self.workers):
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Detener todos los workers"""
        logger.info("Stopping worker pool...")

        for worker in self.workers:
            worker.stop()

        if self.executor:
            self.executor.shutdown(wait=True)

        logger.info("Worker pool stopped")

    def get_stats(self) -> dict:
        """Obtener estadísticas agregadas"""
        total_processed = sum(w.processed_count for w in self.workers)
        total_failed = sum(w.failed_count for w in self.workers)

        return {
            "num_workers": self.num_workers,
            "total_processed": total_processed,
            "total_failed": total_failed,
            "workers": [w.get_stats() for w in self.workers]
        }


def main():
    """Punto de entrada principal"""
    parser = argparse.ArgumentParser(
        description='Nutrition Notification Worker - Procesa notificaciones desde SQS'
    )
    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=1,
        help='Número de workers (default: 1)'
    )
    parser.add_argument(
        '--batch-size', '-b',
        type=int,
        default=10,
        help='Mensajes por batch (default: 10, max: 10)'
    )
    parser.add_argument(
        '--single', '-s',
        action='store_true',
        help='Ejecutar un solo worker (sin pool)'
    )

    args = parser.parse_args()

    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║     Nutrition Notification Worker                         ║
    ║     Amazon SQS Consumer                                   ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    if args.single or args.workers == 1:
        # Modo single worker
        worker = NutritionNotificationWorker(
            worker_id=0,
            batch_size=args.batch_size
        )
        worker.start()
    else:
        # Modo pool de workers
        pool = WorkerPool(
            num_workers=args.workers,
            batch_size=args.batch_size
        )
        pool.start()


if __name__ == "__main__":
    main()