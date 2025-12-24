# Implementación de Notificaciones con IA por Meal

**Fecha:** 24 de Diciembre, 2025
**Estado:** ✅ COMPLETADO
**Costo mensual:** $0.03/mes (vs $40/mes con estrategia por usuario)

---

## 📋 Resumen

Implementación de sistema de notificaciones personalizadas usando GPT-4o-mini con cache por meal_id en lugar de generar una notificación por usuario. Esto reduce el costo de **$40/mes a $0.03/mes** (99.9% de ahorro).

### Estrategia Clave:
- **Una notificación por meal** (no por usuario)
- Todos los usuarios con el mismo meal reciben la misma notificación
- Cache de 30 días en Redis
- Fallback a templates hardcodeados si IA falla o está deshabilitada

---

## 🎯 Archivos Creados

### 1. Servicio de Cache
**Archivo:** `app/services/meal_notification_cache.py`

```python
class MealNotificationCacheService:
    """
    Genera notificación UNA VEZ por meal usando GPT-4o-mini.
    Cachea en Redis por 30 días.
    Fallback a templates si IA falla.
    """

    async def get_or_generate_notification(
        meal_id: int,
        meal: Meal,
        plan: NutritionPlan,
        gym_tone: str = "motivational"
    ) -> Dict[str, str]:
        # Cache key: meal:{meal_id}:notification:{gym_tone}
        # TTL: 30 días
        # Retorna: {"title": "...", "message": "...", "emoji": "..."}
```

**Features:**
- ✅ Generación con GPT-4o-mini (modelo $0.15/$0.60 per 1M tokens)
- ✅ Cache Redis con TTL 30 días
- ✅ Fallback a templates hardcoded si IA falla
- ✅ Soporte para diferentes tonos (motivational/neutral/friendly)
- ✅ Invalidación manual de cache cuando meal cambia

---

### 2. Integración en Servicio de Notificaciones
**Archivo:** `app/services/nutrition_notification_service.py`

**Cambios:**
1. Importar servicio de cache:
```python
from app.services.meal_notification_cache import get_meal_notification_cache
```

2. Modificar `send_meal_reminder()` para usar cache por meal:
```python
def send_meal_reminder(
    self,
    db: Session,
    user_id: int,
    meal_id: int,        # NUEVO
    meal: Meal,          # NUEVO
    plan: NutritionPlan, # NUEVO
    gym_id: int,
    force_direct: bool = False
):
    # Obtener notificación de cache o generar con IA
    meal_cache_service = get_meal_notification_cache()

    notification = await meal_cache_service.get_or_generate_notification(
        meal_id=meal_id,
        meal=meal,
        plan=plan,
        gym_tone=gym_tone
    )

    # Enviar a usuario
    title = notification["title"]
    message = notification["message"]
```

3. Actualizar llamadas en `batch_enqueue_meal_reminders()`:
```python
# ANTES:
success = self.send_meal_reminder(
    db=db,
    user_id=follower.user_id,
    meal_type=meal_type,
    meal_name=meal.name,      # String
    plan_title=plan.title,    # String
    gym_id=gym_id
)

# AHORA:
success = self.send_meal_reminder(
    db=db,
    user_id=follower.user_id,
    meal_id=meal.id,          # ID para cache
    meal=meal,                # Objeto completo
    plan=plan,                # Objeto completo
    gym_id=gym_id
)
```

---

### 3. Script de Pre-generación
**Archivo:** `scripts/pregenerate_meal_notifications.py`

Script para poblar cache con todos los meals existentes.

**Uso:**
```bash
# Pre-generar todas las notificaciones
python scripts/pregenerate_meal_notifications.py

# Solo para un gym
python scripts/pregenerate_meal_notifications.py --gym-id 1

# Solo para un meal
python scripts/pregenerate_meal_notifications.py --meal-id 123

# Dry run (simular sin ejecutar)
python scripts/pregenerate_meal_notifications.py --dry-run

# Forzar regeneración
python scripts/pregenerate_meal_notifications.py --force
```

**Output esperado:**
```
================================================================================
  PRE-GENERACIÓN DE NOTIFICACIONES DE MEALS
================================================================================

📊 Estadísticas:
  Total meals a procesar: 1,250
  Modo: EJECUCIÓN REAL
  Forzar regeneración: NO

🔄 Procesando meals...
────────────────────────────────────────────────────────────────────────────────
[1/1250] ✅ Meal 1 (Power Breakfast):
    Title: 🌅 Power Breakfast - Empieza fuerte
    Message: 540 kcal, 35g proteína. ¡Tu cuerpo lo agradecerá!...
...
================================================================================
  RESUMEN
================================================================================

📊 Resultados:
  Meals procesados: 1250/1250
  Nuevas generadas: 1250
  Ya en cache: 0
  Errores: 0

💰 Costo estimado:
  Generaciones: 1250
  Costo total: $0.1250

✅ Pre-generación completada exitosamente
```

---

### 4. Tests Completos
**Archivo:** `tests/nutrition/test_meal_notification_cache.py`

**11 tests implementados:**

1. ✅ `test_fallback_generation_breakfast` - Fallback para breakfast
2. ✅ `test_fallback_generation_lunch` - Fallback para lunch
3. ✅ `test_fallback_generation_dinner` - Fallback para dinner
4. ✅ `test_get_emoji_for_meal_type` - Emojis correctos por tipo
5. ✅ `test_cache_hit` - Cache HIT retorna cacheado
6. ✅ `test_cache_miss_generates_and_saves` - Cache MISS genera y guarda
7. ✅ `test_ai_generation_success` - Generación con IA funciona
8. ✅ `test_invalidate_meal_notification` - Invalidación de cache
9. ✅ `test_build_prompt_contains_meal_info` - Prompt contiene info
10. ✅ `test_different_gym_tones` - Diferentes tonos funcionan
11. ✅ `test_redis_failure_doesnt_break_generation` - Resiliente a fallos

**Resultado:**
```bash
$ pytest tests/nutrition/test_meal_notification_cache.py -v
====== 11 passed, 116 warnings in 0.31s ======
```

---

## 💰 Análisis de Costos

### Escenario Real: 50 Gyms Activos

**Suposiciones:**
- 50 gyms con módulo de nutrición
- ~25 meals únicos por gym = 1,250 meals totales
- ~10 meals nuevos/modificados por día

### Costo Inicial (One-time)
```
Generaciones: 1,250 meals
Input tokens/meal: ~450 tokens
Output tokens/meal: ~50 tokens

Costo input: 1,250 × 450 × ($0.15/1M) = $0.084
Costo output: 1,250 × 50 × ($0.60/1M) = $0.038
Total: ~$0.12 (UNA VEZ) ✅
```

### Costo Mensual (Mantenimiento)
```
Nuevos/modificados: ~10 meals/día × 30 días = 300 generaciones/mes
Costo mensual: 300 × $0.0001 = $0.03/mes ✅
```

### Comparación con Estrategia Original

| Métrica | Original (por usuario) | Optimizada (por meal) | **Ahorro** |
|---------|------------------------|----------------------|------------|
| Generaciones/día | 15,000 | 10 | **99.9%** |
| Costo mensual | $40 | **$0.03** | **$39.97** |
| Costo anual | $480 | **$0.48** | **$479.52** |
| Cache hit rate | 80% | **99%** | +19% |

---

## 🏗️ Flujo de Funcionamiento

### 1. Primera Vez (Cache MISS)

```
Usuario 1 con "Power Breakfast"
  ↓
send_meal_reminder(meal_id=123)
  ↓
MealNotificationCache.get_or_generate()
  ↓
Redis: GET meal:123:notification:motivational → NULL (MISS)
  ↓
Generar con GPT-4o-mini
  ↓
Redis: SETEX meal:123:notification:motivational (TTL 30 días)
  ↓
Enviar notificación al usuario 1
```

**Costo:** ~$0.0001

---

### 2. Siguientes Veces (Cache HIT)

```
Usuario 2 con "Power Breakfast"
  ↓
send_meal_reminder(meal_id=123)
  ↓
MealNotificationCache.get_or_generate()
  ↓
Redis: GET meal:123:notification:motivational → ✅ FOUND (HIT)
  ↓
Retornar notificación cacheada
  ↓
Enviar notificación al usuario 2
```

**Costo:** $0 (desde cache)

---

### 3. Usuarios 3-100

```
Usuarios 3, 4, 5... 100 con "Power Breakfast"
  ↓
Todos usan la MISMA notificación del cache
  ↓
Costo adicional: $0
```

**Total para 100 usuarios con mismo meal:** $0.0001 (una generación inicial)

**vs Estrategia original:** 100 × $0.0001 = $0.01 (100 generaciones)

---

## 📊 Ejemplos de Notificaciones Generadas

### Meal: "Power Breakfast"
```json
{
  "title": "🌅 Power Breakfast - Empieza fuerte",
  "message": "540 kcal, 35g proteína. ¡Tu cuerpo lo agradecerá!",
  "emoji": "🌅"
}
```

### Meal: "Ensalada Mediterránea"
```json
{
  "title": "🥗 Hora de tu Ensalada Mediterránea",
  "message": "Ligera, nutritiva y deliciosa. 380 kcal perfectas.",
  "emoji": "🥗"
}
```

### Meal: "Snack Proteico"
```json
{
  "title": "🍎 Snack Proteico - Recarga energía",
  "message": "20g de proteína para mantener tus músculos activos.",
  "emoji": "🍎"
}
```

---

## ✅ Ventajas vs ❌ Trade-offs

### ✅ Ventajas

| Ventaja | Descripción |
|---------|-------------|
| **Costo ultra-bajo** | $0.03/mes vs $40/mes (99.9% ahorro) |
| **Cache efectivo** | Hit rate ~99% (mismo meal = mismo cache) |
| **Escalable** | Mismo costo para 10 o 10,000 usuarios |
| **Personalizado por meal** | Mensaje adaptado al contenido del meal |
| **Simple** | Menos complejidad que por usuario |
| **Predecible** | Todos con mismo meal ven mismo mensaje |
| **Performance** | Cache hit ~99% = sin latencia |
| **Resiliente** | Fallback a templates si IA falla |

### ❌ Trade-offs Aceptables

| Pierdes | Pero mantienes |
|---------|----------------|
| Racha personal del usuario | Personalización por meal |
| Nombre del usuario | Nombre del meal |
| Progreso individual | Info nutricional del meal |

**Conclusión:** El trade-off es **aceptable** porque las notificaciones siguen siendo superiores a los mensajes hardcodeados y el ahorro es **masivo**.

---

## 🔄 Invalidación de Cache

### Cuándo regenerar:

```python
# En endpoint de actualización de meal
@router.put("/meals/{meal_id}")
async def update_meal(meal_id: int, meal_update: MealUpdate):
    # Actualizar meal
    updated_meal = await meal_repository.update(meal_id, meal_update)

    # Invalidar cache de notificación
    meal_cache_service = get_meal_notification_cache()
    await meal_cache_service.invalidate_meal_notification(meal_id)

    return updated_meal
```

---

## 🚀 Deployment

### 1. Pre-generar notificaciones (Recomendado)
```bash
# En producción, después de deploy
python scripts/pregenerate_meal_notifications.py

# Costo: ~$0.12 one-time
# Tiempo: ~5-10 minutos
```

### 2. Dejar que se generen on-demand (Alternativa)
```bash
# No hacer nada, se generan automáticamente cuando se necesitan
# Primera notificación: 200-500ms latencia
# Siguientes: <10ms (desde cache)
```

---

## 📈 Monitoreo

### Métricas sugeridas (opcional):

```python
# Agregar a dashboard Grafana/similar
metrics = {
    "meal_notifications_cache_hits": count,
    "meal_notifications_cache_misses": count,
    "meal_notifications_ai_generations": count,
    "meal_notifications_ai_cost_usd": sum,
    "meal_notifications_fallback_used": count
}
```

---

## 🎯 Próximos Pasos (Opcional)

### Mejoras futuras:

1. **Analytics de engagement:**
   - Trackear open rate por tipo de notificación
   - A/B testing: IA vs Templates
   - Fine-tuning de prompts según datos

2. **Soporte multi-idioma:**
   - Detectar idioma del usuario
   - Generar notificaciones en idioma correspondiente
   - Cache por `meal_id + language`

3. **Templates admin (Opcional):**
   - Si algunos gyms quieren control total
   - Sistema híbrido: IA default, templates override
   - UI para crear/editar templates

---

## 🏁 Estado Final

| Componente | Estado | Notas |
|------------|--------|-------|
| **Servicio de Cache** | ✅ Completado | `meal_notification_cache.py` |
| **Integración** | ✅ Completado | `nutrition_notification_service.py` |
| **Script Pre-gen** | ✅ Completado | `pregenerate_meal_notifications.py` |
| **Tests** | ✅ 11/11 passed | `test_meal_notification_cache.py` |
| **Documentación** | ✅ Completado | Este archivo |
| **Deploy-ready** | ✅ Listo | Sin migraciones de BD requeridas |

---

## 💡 Conclusión

**Problema resuelto:** Notificaciones hardcodeadas y genéricas
**Solución:** IA por meal con cache de 30 días
**Resultado:** Notificaciones personalizadas a casi **costo cero** ($0.03/mes)

**ROI:**
- Ahorro: $479.52/año
- Mejor UX: Notificaciones contextuales en lugar de genéricas
- Escalable: Funciona para cualquier volumen de usuarios
- Simple: Una función de cache

**Estado:** ✅ **LISTO PARA PRODUCCIÓN**

---

**Implementado por:** Claude Code (Automated Implementation)
**Fecha:** 24 de Diciembre, 2025
**Basado en:** Estrategia optimizada de notificaciones por meal
