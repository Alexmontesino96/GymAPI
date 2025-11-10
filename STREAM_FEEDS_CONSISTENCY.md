# 🔄 Consistencia de Stream Feeds entre Stories y Posts

**Fecha:** 2025-11-10
**Issue:** Inconsistencia en formato de IDs entre StoryFeedRepository y PostFeedRepository
**Estado:** ✅ RESUELTO

---

## 🐛 Problema Identificado

Los dos sistemas usaban patrones diferentes para generar IDs en Stream Feeds, causando inconsistencias y potenciales bugs.

### Antes de la Corrección ❌

**StoryFeedRepository (Correcto):**
```python
def _sanitize_user_id(self, user_id: Any) -> str:
    user_id_str = str(user_id)
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', user_id_str)
    return sanitized  # Ej: 123 → "123"

# Feed ID: "gym_1_user_123"
feed_id = f"gym_{gym_id}_user_{safe_user_id}"

# Actor: "gym_1_user_123"
actor = f"gym_{gym_id}_user_{safe_user_id}"
```

**PostFeedRepository (Inconsistente):**
```python
def _sanitize_user_id(self, user_id: int) -> str:
    return f"u{user_id}"  # Ej: 123 → "u123"

# Feed ID: "gym_1_u123"  ❌ Falta "user_"
feed_id = f"gym_{gym_id}_{sanitized_user_id}"

# Actor: "gym_1_user_u123"  ❌❌ Doble prefijo
actor = f"gym_{gym_id}_user_{sanitized_user_id}"
```

**Problemas detectados:**
1. ❌ Feed ID de posts: `gym_1_u123` (falta `user_`)
2. ❌ Actor de posts: `gym_1_user_u123` (doble prefijo: `user_` + `u`)
3. ❌ Feed ID y Actor no coincidían en posts
4. ❌ Patrón diferente entre stories y posts
5. ❌ Potencial bug: mismo usuario crearía feeds diferentes en stories vs posts

---

## ✅ Solución Implementada

Unificamos ambos repositorios al patrón de StoryFeedRepository que es más robusto y consistente.

### PostFeedRepository Corregido ✅

```python
def _sanitize_user_id(self, user_id: int) -> str:
    """
    Sanitiza el user_id para cumplir con restricciones de Stream.
    Stream solo permite letras, números y guiones bajos.

    Nota: Unificado con StoryFeedRepository para consistencia.
    """
    # Convertir a string y sanitizar caracteres no permitidos
    user_id_str = str(user_id)
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', user_id_str)
    return sanitized

def _get_feed(self, gym_id: int, user_id: int, feed_slug: str):
    """
    Obtiene un feed de Stream Feeds.

    Feed ID unificado: gym_{gym_id}_user_{safe_user_id}
    """
    sanitized_user_id = self._sanitize_user_id(user_id)
    feed_id = f"gym_{gym_id}_user_{sanitized_user_id}"
    return self.client.feed(feed_slug, feed_id)

async def create_post_activity(...):
    sanitized_user_id = self._sanitize_user_id(user_id)

    activity_data = {
        "actor": f"gym_{gym_id}_user_{sanitized_user_id}",
        # ... resto de datos
    }
```

---

## 🎯 Patrón Unificado

### Formato Estándar

**Patrón:** `gym_{gym_id}_user_{user_id}`

**Ejemplos:**
```
Gym 1, User 123  → gym_1_user_123
Gym 2, User 456  → gym_2_user_456
Gym 5, User 1000 → gym_5_user_1000
```

### Consistencia Garantizada

✅ **StoryFeedRepository:**
- Feed ID: `gym_{gym_id}_user_{user_id}`
- Actor: `gym_{gym_id}_user_{user_id}`

✅ **PostFeedRepository:**
- Feed ID: `gym_{gym_id}_user_{user_id}`
- Actor: `gym_{gym_id}_user_{user_id}`

**Resultado:** El mismo usuario genera el mismo formato de ID en ambos sistemas.

---

## 🧪 Verificación

### Test de Consistencia

Creado script `test_stream_consistency.py` que verifica:

```python
def test_id_consistency():
    story_repo = StoryFeedRepository()
    post_repo = PostFeedRepository()

    # Verifica que ambos generen el mismo ID
    story_safe_id = story_repo._sanitize_user_id(user_id)
    post_safe_id = post_repo._sanitize_user_id(user_id)

    assert story_safe_id == post_safe_id
```

**Resultado del test:**
```
✅ Gym ID: 1, User ID: 123
   Story Feed ID: gym_1_user_123
   Post Feed ID:  gym_1_user_123
   ✅ CONSISTENTE

✅ Gym ID: 2, User ID: 456
   Story Feed ID: gym_2_user_456
   Post Feed ID:  gym_2_user_456
   ✅ CONSISTENTE

✅ TODOS LOS IDS SON CONSISTENTES
   Patrón unificado: gym_{gym_id}_user_{user_id}
```

---

## 📋 Beneficios de la Unificación

1. **Consistencia:** Mismo formato en todos los sistemas
2. **Mantenibilidad:** Un solo patrón para recordar
3. **Debugging:** Más fácil rastrear actividades entre sistemas
4. **Escalabilidad:** Patrón robusto con regex para sanitización
5. **Sin Bugs:** Evita duplicación de feeds o actividades perdidas

---

## 🔍 Sanitización de User IDs

### Por qué se necesita sanitización

Stream Feeds tiene restricciones en los caracteres permitidos en IDs:
- ✅ Permitidos: letras (a-z, A-Z), números (0-9), guión bajo (_)
- ❌ No permitidos: espacios, caracteres especiales, símbolos

### Implementación

```python
def _sanitize_user_id(self, user_id: int) -> str:
    user_id_str = str(user_id)
    # Reemplaza cualquier caracter no permitido con "_"
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', user_id_str)
    return sanitized
```

**Ejemplos:**
```
123       → "123"        ✅
456       → "456"        ✅
"test-1"  → "test_1"     ✅ (guión reemplazado)
"user@1"  → "user_1"     ✅ (@ reemplazado)
```

---

## 🚀 Impacto en Producción

### Sistemas Afectados

✅ **Stories:**
- Sin cambios (ya estaba correcto)
- Continúa funcionando normalmente

✅ **Posts:**
- Corregido para usar el mismo patrón
- Nuevo código genera IDs consistentes

### Migración

**No se requiere migración** si el sistema de posts es nuevo y no tiene datos en Stream Feeds aún.

**Si ya existen posts en Stream Feeds:**
- Los posts antiguos mantendrán sus IDs originales
- Los nuevos posts usarán el patrón correcto
- Considerar script de migración si es crítico (opcional)

---

## 📝 Archivos Modificados

1. **app/repositories/post_feed_repository.py**
   - `_sanitize_user_id()`: Cambiado de prefijo simple a regex
   - `_get_feed()`: Feed ID ahora usa `user_` consistentemente
   - Comentarios actualizados para indicar unificación

2. **test_stream_consistency.py** (nuevo)
   - Script de verificación de consistencia
   - Prueba ambos repositorios con múltiples casos

3. **STREAM_FEEDS_CONSISTENCY.md** (este documento)
   - Documentación del problema y solución
   - Guía para futuros desarrolladores

---

## 🎓 Lecciones Aprendidas

1. **Consistencia es clave:** Usar el mismo patrón en todo el sistema
2. **Documentar decisiones:** Explicar por qué se eligió un patrón
3. **Testing:** Siempre verificar consistencia entre módulos relacionados
4. **Code Review:** Revisar implementaciones similares antes de crear nuevas

---

## 🔮 Recomendaciones Futuras

1. **Extraer a una clase base:** Crear `BaseStreamFeedRepository` con métodos comunes
2. **Tests automatizados:** Agregar test de consistencia al CI/CD
3. **Documentar en CLAUDE.md:** Agregar sección sobre Stream Feeds
4. **Type hints:** Considerar TypedDict para structure de activity_data

### Ejemplo de Refactoring Sugerido

```python
# app/repositories/base_stream_feed_repository.py

class BaseStreamFeedRepository:
    """Base class for Stream Feeds repositories."""

    @staticmethod
    def sanitize_user_id(user_id: int) -> str:
        """Sanitiza user_id para Stream Feeds."""
        user_id_str = str(user_id)
        return re.sub(r'[^a-zA-Z0-9_]', '_', user_id_str)

    @staticmethod
    def build_feed_id(gym_id: int, user_id: int) -> str:
        """Construye feed ID estándar."""
        safe_user_id = BaseStreamFeedRepository.sanitize_user_id(user_id)
        return f"gym_{gym_id}_user_{safe_user_id}"

    @staticmethod
    def build_actor(gym_id: int, user_id: int) -> str:
        """Construye actor estándar."""
        return BaseStreamFeedRepository.build_feed_id(gym_id, user_id)

# Luego ambos repositorios heredarían de esta clase
```

---

## ✅ Estado Final

**Consistencia verificada:** ✅
**Tests pasando:** ✅
**Documentación completa:** ✅
**Listo para producción:** ✅

---

**Última actualización:** 2025-11-10 03:45:00
**Verificado por:** test_stream_consistency.py
**Estado:** RESUELTO ✅
