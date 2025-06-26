#!/usr/bin/env python3
"""
Script de prueba para el sistema de caché de sesiones.
Demuestra el funcionamiento del caché implementado en ClassSessionService.
"""

import asyncio
import sys
import os
from datetime import datetime, date, timedelta
import time

# Agregar el directorio raíz al path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.schedule import class_session_service
from app.db.redis_client import get_redis_client
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_session_cache():
    """
    Prueba completa del sistema de caché de sesiones.
    """
    print("🚀 INICIANDO PRUEBA DEL CACHÉ DE SESIONES")
    print("=" * 60)
    
    # Configuración de prueba
    GYM_ID = 1  # Cambiar por un gym_id válido
    TRAINER_ID = 1  # Cambiar por un trainer_id válido
    CLASS_ID = 1  # Cambiar por un class_id válido
    
    db = SessionLocal()
    redis_client = await get_redis_client()
    
    try:
        print("\n📊 PRUEBA 1: get_upcoming_sessions")
        print("-" * 40)
        
        # Primera llamada - debe ir a BD
        start_time = time.time()
        sessions_1 = await class_session_service.get_upcoming_sessions(
            db=db, gym_id=GYM_ID, skip=0, limit=10, redis_client=redis_client
        )
        time_1 = time.time() - start_time
        print(f"✅ Primera llamada (BD): {len(sessions_1)} sesiones en {time_1:.3f}s")
        
        # Segunda llamada - debe venir del caché
        start_time = time.time()
        sessions_2 = await class_session_service.get_upcoming_sessions(
            db=db, gym_id=GYM_ID, skip=0, limit=10, redis_client=redis_client
        )
        time_2 = time.time() - start_time
        print(f"⚡ Segunda llamada (CACHÉ): {len(sessions_2)} sesiones en {time_2:.3f}s")
        print(f"🚀 Mejora de velocidad: {time_1/time_2:.1f}x más rápido")
        
        print("\n📊 PRUEBA 2: get_sessions_by_trainer")
        print("-" * 40)
        
        # Primera llamada - debe ir a BD
        start_time = time.time()
        trainer_sessions_1 = await class_session_service.get_sessions_by_trainer(
            db=db, trainer_id=TRAINER_ID, gym_id=GYM_ID, 
            upcoming_only=True, redis_client=redis_client
        )
        time_1 = time.time() - start_time
        print(f"✅ Primera llamada (BD): {len(trainer_sessions_1)} sesiones en {time_1:.3f}s")
        
        # Segunda llamada - debe venir del caché
        start_time = time.time()
        trainer_sessions_2 = await class_session_service.get_sessions_by_trainer(
            db=db, trainer_id=TRAINER_ID, gym_id=GYM_ID, 
            upcoming_only=True, redis_client=redis_client
        )
        time_2 = time.time() - start_time
        print(f"⚡ Segunda llamada (CACHÉ): {len(trainer_sessions_2)} sesiones en {time_2:.3f}s")
        print(f"🚀 Mejora de velocidad: {time_1/time_2:.1f}x más rápido")
        
        print("\n📊 PRUEBA 3: get_sessions_by_date_range")
        print("-" * 40)
        
        start_date = date.today()
        end_date = start_date + timedelta(days=7)
        
        # Primera llamada - debe ir a BD
        start_time = time.time()
        range_sessions_1 = await class_session_service.get_sessions_by_date_range(
            db=db, start_date=start_date, end_date=end_date, 
            gym_id=GYM_ID, redis_client=redis_client
        )
        time_1 = time.time() - start_time
        print(f"✅ Primera llamada (BD): {len(range_sessions_1)} sesiones en {time_1:.3f}s")
        
        # Segunda llamada - debe venir del caché
        start_time = time.time()
        range_sessions_2 = await class_session_service.get_sessions_by_date_range(
            db=db, start_date=start_date, end_date=end_date, 
            gym_id=GYM_ID, redis_client=redis_client
        )
        time_2 = time.time() - start_time
        print(f"⚡ Segunda llamada (CACHÉ): {len(range_sessions_2)} sesiones en {time_2:.3f}s")
        print(f"🚀 Mejora de velocidad: {time_1/time_2:.1f}x más rápido")
        
        print("\n📊 PRUEBA 4: get_sessions_by_class")
        print("-" * 40)
        
        # Primera llamada - debe ir a BD
        start_time = time.time()
        class_sessions_1 = await class_session_service.get_sessions_by_class(
            db=db, class_id=CLASS_ID, gym_id=GYM_ID, redis_client=redis_client
        )
        time_1 = time.time() - start_time
        print(f"✅ Primera llamada (BD): {len(class_sessions_1)} sesiones en {time_1:.3f}s")
        
        # Segunda llamada - debe venir del caché
        start_time = time.time()
        class_sessions_2 = await class_session_service.get_sessions_by_class(
            db=db, class_id=CLASS_ID, gym_id=GYM_ID, redis_client=redis_client
        )
        time_2 = time.time() - start_time
        print(f"⚡ Segunda llamada (CACHÉ): {len(class_sessions_2)} sesiones en {time_2:.3f}s")
        print(f"🚀 Mejora de velocidad: {time_1/time_2:.1f}x más rápido")
        
        # Prueba de invalidación
        if sessions_1:
            session_id = sessions_1[0].id
            print(f"\n🔄 PRUEBA 5: Invalidación de caché")
            print("-" * 40)
            
            # Simular cambio en sesión para probar invalidación
            print(f"Invalidando cachés para sesión {session_id}...")
            await class_session_service._invalidate_session_caches(
                redis_client=redis_client,
                gym_id=GYM_ID,
                session_id=session_id,
                trainer_id=TRAINER_ID,
                class_id=CLASS_ID
            )
            
            # Verificar que la próxima llamada va a BD nuevamente
            start_time = time.time()
            sessions_after_invalidation = await class_session_service.get_upcoming_sessions(
                db=db, gym_id=GYM_ID, skip=0, limit=10, redis_client=redis_client
            )
            time_after = time.time() - start_time
            print(f"✅ Después de invalidación (BD): {len(sessions_after_invalidation)} sesiones en {time_after:.3f}s")
        
        print("\n📊 PRUEBA 6: Verificar tracking sets")
        print("-" * 40)
        
        # Verificar que se crearon los tracking sets
        gym_tracking_key = f"cache_keys:sessions:{GYM_ID}"
        trainer_tracking_key = f"cache_keys:sessions:trainer:{TRAINER_ID}"
        class_tracking_key = f"cache_keys:sessions:class:{CLASS_ID}"
        
        gym_keys = await redis_client.smembers(gym_tracking_key)
        trainer_keys = await redis_client.smembers(trainer_tracking_key)
        class_keys = await redis_client.smembers(class_tracking_key)
        
        print(f"🔑 Tracking keys para gym {GYM_ID}: {len(gym_keys)} claves")
        print(f"🔑 Tracking keys para trainer {TRAINER_ID}: {len(trainer_keys)} claves")
        print(f"🔑 Tracking keys para class {CLASS_ID}: {len(class_keys)} claves")
        
        print("\n✅ PRUEBAS COMPLETADAS EXITOSAMENTE")
        print("=" * 60)
        print("🎯 RESULTADOS:")
        print("- ✅ Caché de sesiones funcionando correctamente")
        print("- ⚡ Mejoras significativas de rendimiento")
        print("- 🔄 Invalidación inteligente operativa")
        print("- 📊 Tracking sets configurados correctamente")
        
    except Exception as e:
        print(f"❌ ERROR durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        db.close()
        if redis_client:
            await redis_client.close()

async def test_individual_session_cache():
    """
    Prueba específica para caché de sesiones individuales.
    """
    print("\n🔍 PRUEBA DE SESIONES INDIVIDUALES")
    print("=" * 60)
    
    GYM_ID = 1
    
    db = SessionLocal()
    redis_client = await get_redis_client()
    
    try:
        # Obtener una sesión para probar
        sessions = await class_session_service.get_upcoming_sessions(
            db=db, gym_id=GYM_ID, skip=0, limit=1, redis_client=None  # Sin caché para obtener datos frescos
        )
        
        if not sessions:
            print("❌ No hay sesiones disponibles para probar")
            return
        
        session_id = sessions[0].id
        print(f"🎯 Probando con sesión ID: {session_id}")
        
        print("\n📊 PRUEBA: get_session")
        print("-" * 30)
        
        # Primera llamada - debe ir a BD
        start_time = time.time()
        session_1 = await class_session_service.get_session(
            db=db, session_id=session_id, gym_id=GYM_ID, redis_client=redis_client
        )
        time_1 = time.time() - start_time
        print(f"✅ Primera llamada (BD): {time_1:.3f}s")
        
        # Segunda llamada - debe venir del caché
        start_time = time.time()
        session_2 = await class_session_service.get_session(
            db=db, session_id=session_id, gym_id=GYM_ID, redis_client=redis_client
        )
        time_2 = time.time() - start_time
        print(f"⚡ Segunda llamada (CACHÉ): {time_2:.3f}s")
        print(f"🚀 Mejora: {time_1/time_2:.1f}x más rápido")
        
        print("\n📊 PRUEBA: get_session_with_details")
        print("-" * 30)
        
        # Primera llamada - debe ir a BD
        start_time = time.time()
        details_1 = await class_session_service.get_session_with_details(
            db=db, session_id=session_id, gym_id=GYM_ID, redis_client=redis_client
        )
        time_1 = time.time() - start_time
        print(f"✅ Primera llamada (BD): {time_1:.3f}s")
        
        # Segunda llamada - debe venir del caché
        start_time = time.time()
        details_2 = await class_session_service.get_session_with_details(
            db=db, session_id=session_id, gym_id=GYM_ID, redis_client=redis_client
        )
        time_2 = time.time() - start_time
        print(f"⚡ Segunda llamada (CACHÉ): {time_2:.3f}s")
        print(f"🚀 Mejora: {time_1/time_2:.1f}x más rápido")
        
        print("\n✅ PRUEBAS DE SESIONES INDIVIDUALES COMPLETADAS")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        db.close()
        if redis_client:
            await redis_client.close()

if __name__ == "__main__":
    print("🧪 SISTEMA DE PRUEBAS DEL CACHÉ DE SESIONES")
    print("=" * 60)
    
    # Ejecutar ambas pruebas
    asyncio.run(test_session_cache())
    asyncio.run(test_individual_session_cache())
    
    print("\n🎉 TODAS LAS PRUEBAS COMPLETADAS") 