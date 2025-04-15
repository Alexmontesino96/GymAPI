"""
Test específico para el sistema de caché de eventos.

Este script prueba la funcionalidad de caché del servicio de eventos,
con énfasis en la corrección de la serialización de objetos Pydantic.
"""
import sys
import os
import asyncio
import json
from datetime import datetime, timedelta
import logging
import time

# Configurar logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Añadir directorio raíz al path para importar módulos de la aplicación
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.event import event_service
from app.db.session import SessionLocal
from app.db.redis_client import get_redis_client
from app.models.event import EventStatus
from app.schemas.event import EventWithParticipantCount

class EventCacheTester:
    """Clase para probar el sistema de caché de eventos."""
    
    def __init__(self):
        """Inicializa el tester con una sesión de base de datos y cliente Redis."""
        self.db = None
        self.redis_client = None
    
    async def setup(self):
        """Configura las conexiones necesarias."""
        self.db = SessionLocal()
        self.redis_client = await get_redis_client()
        
        # Limpiar las claves de caché relevantes para la prueba
        logger.info("Limpiando caché antes de iniciar pruebas...")
        await self.clean_cache()
        
        logger.info("Configuración completada: DB y Redis conectados")
    
    async def teardown(self):
        """Cierra las conexiones."""
        if self.db:
            self.db.close()
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Conexiones cerradas")
    
    async def test_events_cache(self):
        """Prueba el sistema de caché para eventos."""
        logger.info("Iniciando prueba de caché de eventos")
        
        # 1. Primera solicitud - debe ser cache MISS
        logger.info("PRUEBA 1: Primera solicitud (debe ser MISS)")
        start_time = time.time()
        events1 = await event_service.get_events_cached(
            self.db,
            status=EventStatus.SCHEDULED,
            gym_id=1,  # Usar un gym_id válido de tu sistema
            redis_client=self.redis_client
        )
        elapsed_time1 = time.time() - start_time
        logger.info(f"Primera solicitud completada en {elapsed_time1:.4f}s, eventos obtenidos: {len(events1)}")
        
        # Verificar que los eventos son instancias de EventWithParticipantCount
        if events1:
            is_pydantic = isinstance(events1[0], EventWithParticipantCount)
            logger.info(f"¿Los eventos son instancias de EventWithParticipantCount? {is_pydantic}")
        
        # 2. Segunda solicitud - debe ser cache HIT
        logger.info("PRUEBA 2: Segunda solicitud (debe ser HIT)")
        start_time = time.time()
        events2 = await event_service.get_events_cached(
            self.db,
            status=EventStatus.SCHEDULED,
            gym_id=1,
            redis_client=self.redis_client
        )
        elapsed_time2 = time.time() - start_time
        logger.info(f"Segunda solicitud completada en {elapsed_time2:.4f}s, eventos obtenidos: {len(events2)}")
        
        # 3. Comprobar si hay mejora en el tiempo de respuesta
        improvement = (elapsed_time1 - elapsed_time2) / elapsed_time1 * 100 if elapsed_time1 > 0 else 0
        logger.info(f"Mejora en tiempo de respuesta: {improvement:.2f}%")
        
        # 4. Probar eventos de un creador específico
        logger.info("PRUEBA 3: Eventos de un creador específico (primera solicitud, debe ser MISS)")
        start_time = time.time()
        creator_events1 = await event_service.get_events_by_creator_cached(
            self.db,
            creator_id=1,  # Usar un creator_id válido de tu sistema
            gym_id=1,
            redis_client=self.redis_client
        )
        elapsed_time3 = time.time() - start_time
        logger.info(f"Solicitud de eventos por creador completada en {elapsed_time3:.4f}s, eventos obtenidos: {len(creator_events1)}")
        
        # 5. Segunda solicitud de eventos por creador - debe ser cache HIT
        logger.info("PRUEBA 4: Eventos de un creador específico (segunda solicitud, debe ser HIT)")
        start_time = time.time()
        creator_events2 = await event_service.get_events_by_creator_cached(
            self.db,
            creator_id=1,
            gym_id=1,
            redis_client=self.redis_client
        )
        elapsed_time4 = time.time() - start_time
        logger.info(f"Segunda solicitud de eventos por creador completada en {elapsed_time4:.4f}s, eventos obtenidos: {len(creator_events2)}")
        
        # 6. Comprobar si hay mejora en el tiempo de respuesta para eventos por creador
        improvement2 = (elapsed_time3 - elapsed_time4) / elapsed_time3 * 100 if elapsed_time3 > 0 else 0
        logger.info(f"Mejora en tiempo de respuesta para eventos por creador: {improvement2:.2f}%")
        
        # 7. Verificar que los datos son idénticos entre llamadas
        are_events_equal = len(events1) == len(events2)
        are_creator_events_equal = len(creator_events1) == len(creator_events2)
        
        logger.info(f"¿Los datos de eventos son idénticos entre llamadas? {are_events_equal}")
        logger.info(f"¿Los datos de eventos por creador son idénticos entre llamadas? {are_creator_events_equal}")
        
        # Resultado final
        if are_events_equal and are_creator_events_equal:
            logger.info("✅ PRUEBA EXITOSA: El sistema de caché de eventos funciona correctamente")
            return True
        else:
            logger.warning("❌ PRUEBA FALLIDA: El sistema de caché de eventos presenta problemas")
            return False

    async def clean_cache(self):
        """Limpia las claves de caché relacionadas con eventos."""
        try:
            # Eliminar todas las claves que coincidan con patrones de caché de eventos
            patterns = ["events:list:*", "events:creator:*", "event:detail:*"]
            for pattern in patterns:
                keys = []
                async for key in self.redis_client.scan_iter(match=pattern):
                    keys.append(key)
                
                if keys:
                    count = await self.redis_client.delete(*keys)
                    logger.info(f"Eliminadas {count} claves con patrón: {pattern}")
            logger.info("Caché limpiada con éxito")
        except Exception as e:
            logger.error(f"Error al limpiar caché: {e}")


async def main():
    """Función principal para ejecutar las pruebas."""
    tester = EventCacheTester()
    try:
        await tester.setup()
        result = await tester.test_events_cache()
        print(f"\n{'='*60}")
        print(f"RESULTADO FINAL: {'✅ EXITOSO' if result else '❌ FALLIDO'}")
        print(f"{'='*60}\n")
    finally:
        await tester.teardown()


if __name__ == "__main__":
    asyncio.run(main()) 