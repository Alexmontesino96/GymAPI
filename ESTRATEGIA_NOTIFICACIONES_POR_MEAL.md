# Estrategia Optimizada: Notificaciones IA por Meal (no por Usuario)

**Fecha:** 24 de Diciembre, 2025
**Contexto:** Reducir costo de IA generando una notificación por meal en lugar de por usuario
**Impacto:** Costo de ~$40/mes → ~$0.03/mes (99.9% reducción) 🔥

---

## 🎯 Concepto Clave

### ❌ Estrategia Original (Costosa)
```
Para cada notificación:
  - Generar con IA para CADA usuario individualmente
  - 50 gyms × 100 usuarios × 3 comidas/día = 15,000 generaciones/día
  - Costo: ~$40/mes (sin cache) o $8/mes (con cache 80%)
```

### ✅ Estrategia Optimizada (Casi Gratis)
```
Para cada meal único:
  - Generar con IA UNA VEZ por meal
  - Cachear por meal_id (TTL: 30 días)
  - TODOS los usuarios con ese meal reciben la MISMA notificación
  - 50 gyms × ~25 meals/gym = 1,250 meals totales (one-time)
  - Mantenimiento: ~10 meals nuevos/día
  - Costo: ~$0.15 inicial + ~$0.03/mes mantenimiento
```

---

## 💰 Análisis de Costos

### Escenario Real

**Suposiciones:**
- 50 gyms activos
- Cada gym tiene ~20-30 meals únicos en sus planes de nutrición
- Total meals en sistema: ~1,250 meals únicos
- Nuevos meals: ~10/día promedio (gyms agregan/modifican meals)

### Costo Inicial (One-time Setup)

**Primera generación de todas las notificaciones:**
```
Generaciones: 1,250 meals
Input tokens/meal: ~450 tokens (prompt con contexto del meal)
Output tokens/meal: ~50 tokens (JSON con title + message)

Costo input: 1,250 × 450 × ($0.15/1M) = $0.084
Costo output: 1,250 × 50 × ($0.60/1M) = $0.038
Total: ~$0.12 (ONE TIME) ✅
```

### Costo Mensual (Mantenimiento)

**Nuevos meals + regeneraciones:**
```
Nuevos meals/día: ~10
Meals/mes: ~300

Costo mensual: 300 × $0.0001 = $0.03/mes ✅
```

### Comparación con Estrategia Original

| Métrica | Original (por usuario) | Optimizada (por meal) | **Ahorro** |
|---------|------------------------|----------------------|------------|
| Generaciones/día | 15,000 | 10 | **99.9%** |
| Costo inicial | N/A | $0.12 | - |
| Costo mensual | $40 (sin cache) | **$0.03** | **99.9%** 🔥 |
| Costo mensual | $8 (con cache) | **$0.03** | **99.6%** 🔥 |
| **Costo anual** | **$480 (sin cache)** | **$0.48** | **$479.52** 💰 |

---

## 🏗️ Arquitectura de Implementación

### 1. Cache por Meal ID

```python
class MealNotificationCache:
    """Cache de notificaciones generadas por meal."""

    async def get_or_generate_notification(
        self,
        meal_id: int,
        meal: Meal,
        plan: NutritionPlan,
        gym_tone: str = "motivational"
    ) -> dict:
        """
        Obtiene notificación de cache o genera nueva si no existe.

        Cache key: meal:{meal_id}:notification
        TTL: 30 días (se regenera solo si meal cambia)
        """
        cache_key = f"meal:{meal_id}:notification:{gym_tone}"

        # 1. Intentar obtener de cache
        cached = await redis_client.get(cache_key)
        if cached:
            logger.debug(f"Cache HIT para meal {meal_id}")
            return json.loads(cached)

        logger.info(f"Cache MISS para meal {meal_id} - generando con IA...")

        # 2. Generar con IA
        notification = await self._generate_with_ai(meal, plan, gym_tone)

        # 3. Cachear (TTL 30 días = 2,592,000 segundos)
        await redis_client.setex(
            cache_key,
            2592000,  # 30 días
            json.dumps(notification)
        )

        return notification

    async def _generate_with_ai(
        self,
        meal: Meal,
        plan: NutritionPlan,
        gym_tone: str
    ) -> dict:
        """Genera notificación con OpenAI GPT-4o-mini."""

        prompt = f"""
Genera una notificación de recordatorio para esta comida:

**Comida:**
- Nombre: {meal.name}
- Tipo: {meal.meal_type} (breakfast/lunch/dinner/snack)
- Descripción: {meal.description or 'N/A'}
- Calorías: {meal.calories or 'N/A'} kcal
- Proteínas: {meal.protein or 'N/A'}g

**Plan nutricional:**
- Título: {plan.title}
- Objetivo: {plan.goal or 'N/A'}
- Tipo: {plan.plan_type}

**Tono:** {gym_tone} (motivational/neutral/friendly)

**Reglas:**
1. Título: Máximo 50 caracteres, incluir emoji relevante al tipo de comida
2. Mensaje: Máximo 100 caracteres, motivacional y específico
3. Mencionar el nombre de la comida
4. Tono: {gym_tone}
5. NO mencionar nombres de usuarios (esto va a TODOS los usuarios con este meal)
6. Enfocarse en el meal específico, no en racha o logros individuales

**Emojis por tipo:**
- breakfast: 🌅, ☀️, 🍳
- lunch: 🌮, 🥗, 🍽️
- dinner: 🌙, 🍲, 🥘
- snack: 🍎, 🥤, 🍪

Retorna solo JSON (sin markdown):
{{
    "title": "...",
    "message": "...",
    "emoji": "..."
}}
"""

        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Eres un asistente de nutrición que crea notificaciones "
                        "motivacionales para recordatorios de comidas. "
                        "Sé breve, específico y motivacional."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        return json.loads(response.choices[0].message.content)
```

### 2. Integración en Servicio de Notificaciones

```python
# En nutrition_notification_service.py

from app.services.meal_notification_cache import MealNotificationCache

meal_notification_cache = MealNotificationCache()

async def send_meal_reminder(
    user_id: int,
    gym_id: int,
    meal_id: int,
    meal_type: str
):
    """
    Envía recordatorio de comida a un usuario.
    Usa notificación cacheada por meal_id (no genera por usuario).
    """
    # 1. Obtener meal y plan
    meal = await meal_repository.get_by_id(meal_id)
    plan = await nutrition_plan_repository.get_active_by_user(user_id)

    # 2. Obtener notificación de cache o generar (UNA VEZ por meal)
    gym = await gym_repository.get_by_id(gym_id)
    notification = await meal_notification_cache.get_or_generate_notification(
        meal_id=meal_id,
        meal=meal,
        plan=plan,
        gym_tone=gym.notification_tone or "motivational"
    )

    # 3. Enviar a usuario (misma notificación para TODOS con este meal)
    await send_onesignal_notification(
        user_id=user_id,
        gym_id=gym_id,
        title=notification["title"],
        message=notification["message"],
        data={
            "type": "meal_reminder",
            "meal_id": meal_id,
            "meal_type": meal_type
        }
    )

    logger.info(
        f"Notificación enviada a user {user_id} para meal {meal_id} "
        f"(cached: {cached})"
    )
```

### 3. Job de Recordatorios (Sin Cambios)

```python
def send_meal_reminders_job_single_gym(gym_id: int, meal_type: str, scheduled_time: str):
    """
    Job que envía recordatorios a usuarios de un gym.
    Ahora usa cache por meal_id, no genera por usuario.
    """
    # Obtener usuarios con ese meal_type configurado para scheduled_time
    users = get_users_with_meal_at_time(gym_id, meal_type, scheduled_time)

    for user in users:
        # Obtener meal del día para este usuario
        meal = get_meal_for_user_today(user.id, meal_type)

        if meal:
            # Enviar (usa cache automáticamente)
            await send_meal_reminder(
                user_id=user.id,
                gym_id=gym_id,
                meal_id=meal.id,  # Key para cache
                meal_type=meal_type
            )
```

---

## ✅ Ventajas de esta Estrategia

| Ventaja | Descripción | Impacto |
|---------|-------------|---------|
| **Costo ultra-bajo** | $0.03/mes vs $40/mes | ⭐⭐⭐⭐⭐ |
| **Cache efectivo** | Hit rate ~99% (mismo meal = mismo cache) | ⭐⭐⭐⭐⭐ |
| **Escalable** | Mismo costo para 10 o 10,000 usuarios | ⭐⭐⭐⭐⭐ |
| **Personalizado** | Mensaje adapta al contenido del meal | ⭐⭐⭐⭐ |
| **Simple** | Menos complejidad que por usuario | ⭐⭐⭐⭐ |
| **Predecible** | Todos con mismo meal ven mismo mensaje | ⭐⭐⭐⭐ |
| **Performance** | Cache hit ~99% = sin latencia | ⭐⭐⭐⭐⭐ |
| **Mantenible** | Auto-regenera solo cuando meal cambia | ⭐⭐⭐⭐ |

---

## ⚠️ Trade-offs (Consideraciones)

### ❌ Pierdes:
1. **Personalización por usuario individual:**
   - No menciona racha personal del usuario
   - No menciona progreso individual
   - No menciona nombre del usuario

### ✅ Mantienes:
1. **Personalización por meal:**
   - Mensaje específico al contenido del meal
   - Nombre del meal en la notificación
   - Emoji relevante al tipo de comida
   - Contexto del plan nutricional
2. **Calidad superior a hardcoded:**
   - Mejor redacción
   - Tono configurable por gym
   - Adaptado al contenido real

---

## 📊 Ejemplos de Notificaciones Generadas

### Meal: "Power Breakfast"
**Plan:** Ganancia Muscular
**Tipo:** breakfast
**Generado por IA:**
```json
{
  "title": "🌅 Power Breakfast - Empieza fuerte",
  "message": "540 kcal, 35g proteína. ¡Tu cuerpo lo agradecerá!",
  "emoji": "🌅"
}
```
**Usado por:** TODOS los usuarios con "Power Breakfast" en su plan

---

### Meal: "Ensalada Mediterránea"
**Plan:** Pérdida de Grasa
**Tipo:** lunch
**Generado por IA:**
```json
{
  "title": "🥗 Hora de tu Ensalada Mediterránea",
  "message": "Ligera, nutritiva y deliciosa. 380 kcal perfectas.",
  "emoji": "🥗"
}
```
**Usado por:** TODOS los usuarios con "Ensalada Mediterránea"

---

### Meal: "Snack Proteico"
**Plan:** Mantenimiento
**Tipo:** snack
**Generado por IA:**
```json
{
  "title": "🍎 Snack Proteico - Recarga energía",
  "message": "20g de proteína para mantener tus músculos activos.",
  "emoji": "🍎"
}
```
**Usado por:** TODOS los usuarios con "Snack Proteico"

---

## 🔄 Invalidación de Cache (Cuando Re-generar)

### Triggers para Regenerar:

```python
class MealNotificationCache:

    async def invalidate_meal_notification(self, meal_id: int):
        """
        Invalida cache cuando meal cambia.
        Llamar desde:
        - Endpoint de actualización de meal
        - Webhook si meal se modifica
        """
        # Invalidar para todos los tonos
        for tone in ["motivational", "neutral", "friendly"]:
            cache_key = f"meal:{meal_id}:notification:{tone}"
            await redis_client.delete(cache_key)

        logger.info(f"Cache invalidado para meal {meal_id}")

# En endpoint de update meal:
@router.put("/meals/{meal_id}")
async def update_meal(meal_id: int, meal_update: MealUpdate):
    # Actualizar meal
    updated_meal = await meal_repository.update(meal_id, meal_update)

    # Invalidar cache de notificación
    await meal_notification_cache.invalidate_meal_notification(meal_id)

    return updated_meal
```

---

## 🚀 Plan de Implementación

### Fase 1: Core (1 día)
1. ✅ Crear `MealNotificationCache` service
2. ✅ Integrar en `nutrition_notification_service.py`
3. ✅ Modificar `send_meal_reminder()` para usar cache por meal_id
4. ✅ Tests básicos

**Esfuerzo:** 1 día
**Resultado:** Sistema funcionando con cache por meal

---

### Fase 2: Generación Inicial (1 hora)
1. ✅ Script para pre-generar notificaciones de meals existentes
2. ✅ Poblar cache con todos los meals actuales

```python
# scripts/pregenerate_meal_notifications.py

async def pregenerate_all_meal_notifications():
    """Pre-genera notificaciones para todos los meals existentes."""

    meals = await db.query(Meal).filter(Meal.is_active == True).all()
    total = len(meals)

    print(f"Pre-generando notificaciones para {total} meals...")

    for idx, meal in enumerate(meals, 1):
        plan = await get_plan_for_meal(meal.id)

        notification = await meal_notification_cache.get_or_generate_notification(
            meal_id=meal.id,
            meal=meal,
            plan=plan,
            gym_tone="motivational"
        )

        print(f"[{idx}/{total}] Meal {meal.id} ({meal.name}): {notification['title']}")

    print(f"✅ Pre-generación completada: {total} meals")
```

**Esfuerzo:** 1 hora
**Costo:** ~$0.12 (one-time)

---

### Fase 3: Optimizaciones (Opcional - 2-3 horas)
1. ✅ Invalidación automática al actualizar meal
2. ✅ Métricas de cache hit/miss
3. ✅ Dashboard de notificaciones generadas

**Esfuerzo:** 2-3 horas (opcional)

---

## 📈 Métricas y Monitoreo

### Métricas Clave:

```python
class NotificationMetrics:
    """Métricas de notificaciones."""

    async def track_notification_sent(
        self,
        meal_id: int,
        user_id: int,
        cache_hit: bool
    ):
        """Trackea envío de notificación."""

        # Incrementar contadores en Redis
        await redis_client.incr(f"metrics:meal:{meal_id}:notifications_sent")

        if cache_hit:
            await redis_client.incr(f"metrics:notifications:cache_hits")
        else:
            await redis_client.incr(f"metrics:notifications:cache_misses")
            await redis_client.incr(f"metrics:notifications:ai_generations")

    async def get_stats(self) -> dict:
        """Obtiene estadísticas."""

        cache_hits = int(await redis_client.get("metrics:notifications:cache_hits") or 0)
        cache_misses = int(await redis_client.get("metrics:notifications:cache_misses") or 0)
        ai_generations = int(await redis_client.get("metrics:notifications:ai_generations") or 0)

        total = cache_hits + cache_misses
        hit_rate = (cache_hits / total * 100) if total > 0 else 0

        return {
            "total_notifications_sent": total,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "cache_hit_rate": f"{hit_rate:.2f}%",
            "ai_generations_total": ai_generations,
            "estimated_cost_saved": ai_generations * 0.0001  # vs generar por usuario
        }
```

### Dashboard Esperado:

```
📊 Notificaciones - Últimos 30 días
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total enviadas:        450,000
Cache hits:           445,500 (99.0%)
Cache misses:           4,500 (1.0%)
Generaciones IA:          300

💰 Costo estimado:      $0.03
💰 Ahorro vs por-user:  $39.97 (99.9%)

📈 Top meals por notificaciones:
1. Power Breakfast      45,000 envíos
2. Lunch Proteico       38,000 envíos
3. Cena Light           32,000 envíos
```

---

## 🏁 Conclusión

### ✅ Estrategia Ganadora:

**Una notificación por meal (no por usuario) con cache de 30 días**

**Beneficios:**
- 💰 **Costo:** $0.03/mes (vs $40/mes)
- ⚡ **Performance:** 99% cache hit rate
- 📈 **Escalable:** Mismo costo para cualquier volumen
- 🎨 **Personalizado:** Mejor que hardcoded
- 🔧 **Simple:** Fácil de implementar y mantener

**Trade-off aceptable:**
- ❌ Pierde personalización individual (racha, nombre)
- ✅ Mantiene personalización por meal (contenido específico)

---

**Recomendación final:** ✅ **IMPLEMENTAR esta estrategia**

- Tiempo: 1 día de desarrollo
- Costo: $0.12 setup + $0.03/mes
- ROI: 99.9% ahorro vs estrategia original
- Mejor que templates hardcodeados pero casi gratis

---

**¿Próximo paso?** Implementar `MealNotificationCache` y pre-generar notificaciones para meals existentes.
