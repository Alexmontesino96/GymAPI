# app/core/request_cache.py - NUEVO ARCHIVO
"""
Cache a nivel de request para evitar consultas redundantes.
Soluciona el problema de 14 cache hits del mismo usuario.
"""
from typing import Optional, Any, Dict
from fastapi import Request

class RequestCache:
    """Cache que vive durante el request actual"""

    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Obtener valor del cache"""
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        """Guardar valor en cache"""
        self.cache[key] = value

    def get_stats(self) -> Dict:
        """Obtener estadísticas del cache"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "keys_cached": len(self.cache)
        }


def get_request_cache(request: Request) -> RequestCache:
    """Obtener o crear cache para el request actual"""
    if not hasattr(request.state, "cache"):
        request.state.cache = RequestCache()
    return request.state.cache


# app/services/user.py - MODIFICAR get_user_by_auth0_id
async def get_user_by_auth0_id_optimized(
    db,
    auth0_id: str,
    request: Optional[Request] = None
):
    """Versión optimizada que usa request cache"""

    # 1. Check request cache first
    if request:
        cache = get_request_cache(request)
        cache_key = f"user:{auth0_id}"
        cached_user = cache.get(cache_key)
        if cached_user:
            return cached_user

    # 2. Check Redis cache (si está disponible)
    redis_client = get_redis()
    if redis_client:
        redis_key = f"user_by_auth0_id:{auth0_id}"
        cached = await redis_client.get(redis_key)
        if cached:
            user = json.loads(cached)
            # Guardar en request cache
            if request:
                cache.set(cache_key, user)
            return user

    # 3. Query database
    user = db.query(User).filter(User.auth0_id == auth0_id).first()

    # 4. Save to both caches
    if user:
        user_dict = user.to_dict()  # Serializar

        # Save to Redis
        if redis_client:
            await redis_client.setex(redis_key, 300, json.dumps(user_dict))

        # Save to request cache
        if request:
            cache.set(cache_key, user_dict)

    return user
