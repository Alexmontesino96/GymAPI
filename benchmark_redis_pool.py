import asyncio
import time
import redis.asyncio as redis
from app.db.redis_client import initialize_redis_pool, get_redis_client
from app.core.config import get_settings

async def benchmark_without_pool(operations=100):
    """Benchmark sin connection pooling (crea una conexión nueva cada vez)."""
    settings = get_settings()
    start_time = time.time()
    
    for _ in range(operations):
        # Crear una nueva conexión para cada operación
        client = await redis.from_url(
            settings.REDIS_URL, 
            encoding="utf-8", 
            decode_responses=True
        )
        await client.ping()
        await client.close()  # Cerrar la conexión después de usarla
    
    total_time = time.time() - start_time
    return total_time, total_time / operations

async def benchmark_with_pool(operations=100):
    """Benchmark con connection pooling."""
    # Asegurar que el pool esté inicializado
    await initialize_redis_pool()
    
    start_time = time.time()
    
    for _ in range(operations):
        # Obtener conexión del pool
        client = await get_redis_client()
        await client.ping()
        # No cerrar el cliente, solo devolverlo al pool (implícito)
    
    total_time = time.time() - start_time
    return total_time, total_time / operations

async def benchmark_with_pool_parallel(operations=100, concurrency=10):
    """Benchmark con connection pooling y operaciones en paralelo."""
    # Asegurar que el pool esté inicializado
    await initialize_redis_pool()
    
    # Crear una lista de tareas para ejecutar en paralelo
    async def do_ping():
        client = await get_redis_client()
        await client.ping()
    
    start_time = time.time()
    
    # Dividir las operaciones en lotes según la concurrencia
    batches = [operations // concurrency] * concurrency
    if operations % concurrency:
        batches[-1] += operations % concurrency
    
    for batch_size in batches:
        # Ejecutar un lote de operaciones en paralelo
        await asyncio.gather(*[do_ping() for _ in range(batch_size)])
    
    total_time = time.time() - start_time
    return total_time, total_time / operations

async def run_benchmarks():
    # Número de operaciones para probar
    operations = 50
    
    print(f"Ejecutando benchmarks con {operations} operaciones:")
    
    # Benchmark sin pooling
    print("\n1. Sin connection pooling (una conexión nueva por operación):")
    total_time_no_pool, avg_time_no_pool = await benchmark_without_pool(operations)
    print(f"   Tiempo total: {total_time_no_pool:.4f} segundos")
    print(f"   Tiempo promedio por operación: {avg_time_no_pool * 1000:.2f} ms")
    
    # Benchmark con pooling (secuencial)
    print("\n2. Con connection pooling (operaciones secuenciales):")
    total_time_pool, avg_time_pool = await benchmark_with_pool(operations)
    print(f"   Tiempo total: {total_time_pool:.4f} segundos")
    print(f"   Tiempo promedio por operación: {avg_time_pool * 1000:.2f} ms")
    
    # Benchmark con pooling (paralelo)
    print("\n3. Con connection pooling (operaciones en paralelo, 10 concurrentes):")
    total_time_parallel, avg_time_parallel = await benchmark_with_pool_parallel(operations, 10)
    print(f"   Tiempo total: {total_time_parallel:.4f} segundos")
    print(f"   Tiempo promedio por operación: {avg_time_parallel * 1000:.2f} ms")
    
    # Mostrar mejora
    improvement_sequential = (total_time_no_pool - total_time_pool) / total_time_no_pool * 100
    improvement_parallel = (total_time_no_pool - total_time_parallel) / total_time_no_pool * 100
    
    print("\nResultados:")
    print(f"- Mejora con pooling secuencial: {improvement_sequential:.2f}%")
    print(f"- Mejora con pooling paralelo: {improvement_parallel:.2f}%")
    print(f"- Reducción de latencia por operación: {(avg_time_no_pool - avg_time_pool) * 1000:.2f} ms")

if __name__ == "__main__":
    asyncio.run(run_benchmarks()) 