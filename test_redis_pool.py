import asyncio
from app.db.redis_client import initialize_redis_pool, get_redis_client

async def test_redis_pool():
    print("Inicializando Redis connection pool...")
    await initialize_redis_pool()
    
    print("Obteniendo cliente Redis desde el pool...")
    redis = await get_redis_client()
    
    # Probar ping básico
    ping_result = await redis.ping()
    print(f'Conexión Redis exitosa: {ping_result}')
    
    # Probar múltiples operaciones concurrentes
    print("Ejecutando 10 operaciones ping concurrentes...")
    start_time = asyncio.get_event_loop().time()
    await asyncio.gather(*[redis.ping() for _ in range(10)])
    elapsed = asyncio.get_event_loop().time() - start_time
    print(f'10 operaciones ping ejecutadas exitosamente en {elapsed:.4f} segundos')
    print(f'Tiempo promedio por operación: {(elapsed / 10) * 1000:.2f} ms')
    
    # Probar reutilización del pool
    print("\nProbando reutilización del pool...")
    redis2 = await get_redis_client()
    print(f'¿Mismo objeto Redis? {redis is redis2}')
    
    print("\nPrueba completada exitosamente!")

if __name__ == "__main__":
    asyncio.run(test_redis_pool()) 