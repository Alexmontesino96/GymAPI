# FIX: Stream Multi-Tenant ID Format

## Problema Identificado

El backend NO está creando correctamente los canales en Stream.io porque usa IDs en formato `user_{id}` en lugar de `gym_{gym_id}_user_{id}`.

### Evidencia:
- **Audit Log**: `audit_stream_sync_20251214_204250.json` muestra canales con miembros `user_4`, `user_8` (sin gym_id)
- **Error reportado**: "There is no ChannelDTO instance in the DB matching cid: messaging:direct_user_10_user_11"
- **Backend**: Crea registro en BD pero el canal NO existe en Stream.io

## Archivos a Modificar

### 1. `app/core/stream_utils.py` (CRÍTICO)

**Antes:**
```python
def get_stream_id_from_internal(internal_id: int) -> str:
    return f"user_{internal_id}"
```

**Después:**
```python
def get_stream_id_from_internal(internal_id: int, gym_id: int = None) -> str:
    """
    Convierte un ID interno a formato Stream multi-tenant.

    Args:
        internal_id: ID del usuario en la BD
        gym_id: ID del gimnasio (requerido para multi-tenant)

    Returns:
        str: ID en formato gym_{gym_id}_user_{id} o user_{id} (fallback)
    """
    if gym_id is not None:
        return f"gym_{gym_id}_user_{internal_id}"
    else:
        # Fallback para compatibilidad (deprecado)
        import logging
        logging.warning(
            f"get_stream_id_from_internal llamado sin gym_id para user {internal_id}. "
            f"Usando formato legacy 'user_{id}' - DEPRECADO"
        )
        return f"user_{internal_id}"
```

### 2. `app/services/chat.py` - Método `_get_stream_id_for_user`

**Antes:**
```python
def _get_stream_id_for_user(self, user: User) -> str:
    from app.core.stream_utils import get_stream_id_from_internal
    return get_stream_id_from_internal(user.id)
```

**Después:**
```python
def _get_stream_id_for_user(self, user: User, gym_id: int = None) -> str:
    """
    Obtiene stream_id para un usuario en formato multi-tenant.

    Args:
        user: Usuario de la BD
        gym_id: ID del gimnasio (requerido para multi-tenant)

    Returns:
        str: Stream ID en formato gym_{gym_id}_user_{user_id}
    """
    from app.core.stream_utils import get_stream_id_from_internal

    # Prioridad: gym_id pasado como parámetro, luego user.gym_id
    effective_gym_id = gym_id if gym_id is not None else getattr(user, 'gym_id', None)

    return get_stream_id_from_internal(user.id, gym_id=effective_gym_id)
```

### 3. `app/services/chat.py` - Actualizar llamadas en `create_room`

**Línea ~402:** Agregar gym_id al obtener creator_stream_id
```python
# ANTES:
creator_stream_id = self._get_stream_id_for_user(creator)

# DESPUÉS:
creator_stream_id = self._get_stream_id_for_user(creator, gym_id=gym_id)
```

**Línea ~416:** Agregar gym_id al procesar miembros
```python
# ANTES:
member_stream_id = self._get_stream_id_for_user(member)

# DESPUÉS:
member_stream_id = self._get_stream_id_for_user(member, gym_id=gym_id)
```

### 4. `app/services/chat.py` - Actualizar llamadas en `get_or_create_direct_chat`

**Línea ~809:** Actualizar query_stream_id
```python
# ANTES:
query_stream_id = self._get_stream_id_for_user(user1)

# DESPUÉS:
query_stream_id = self._get_stream_id_for_user(user1, gym_id=gym_id)
```

**Línea ~770:** Auto-unhide con gym_id
```python
# ANTES:
stream_id_user1 = self._get_stream_id_for_user(user1_obj)

# DESPUÉS:
stream_id_user1 = self._get_stream_id_for_user(user1_obj, gym_id=gym_id)
```

### 5. `app/services/chat.py` - Método `delete_conversation_for_user`

**Línea ~2163:**
```python
# ANTES:
stream_id = self._get_stream_id_for_user(user)

# DESPUÉS:
stream_id = self._get_stream_id_for_user(user, gym_id=gym_id)
```

## Plan de Migración

### Fase 1: Actualizar Código (INMEDIATO)
1. ✅ Modificar `stream_utils.py` con parámetro `gym_id`
2. ✅ Actualizar `_get_stream_id_for_user` para aceptar `gym_id`
3. ✅ Actualizar TODAS las llamadas en `chat.py` para pasar `gym_id`

### Fase 2: Script de Migración de Datos (URGENTE)
Crear script para:
1. Obtener todos los ChatRoom de la BD
2. Por cada room:
   - Obtener canal de Stream con formato actual
   - Si existe, verificar miembros
   - Crear nuevo canal con IDs multi-tenant correctos
   - Migrar mensajes (si es posible) o documentar pérdida
   - Actualizar BD con nuevo stream_channel_id
3. Limpiar canales legacy en Stream

### Fase 3: Testing (CRÍTICO)
1. ✅ Probar creación de nuevos chats directos
2. ✅ Verificar que canales se crean en Stream.io
3. ✅ Confirmar que iOS puede enviar/recibir mensajes
4. ✅ Validar auto-unhide con IDs correctos

## Impacto

### Usuarios Afectados:
- **TODOS los chats existentes** tienen IDs incorrectos
- Los chats **NO funcionan** porque el canal no existe en Stream.io

### Riesgo:
- **CRÍTICO** - Funcionalidad de chat completamente rota
- Requiere migración de datos inmediata

## Testing Inmediato

Después de aplicar el fix, ejecutar:

```bash
# 1. Test unitario del fix
pytest tests/chat/test_delete_conversation_unit.py -v

# 2. Crear nuevo chat directo y verificar
curl -X GET "https://gymapi-eh6m.onrender.com/api/v1/chat/rooms/direct/11" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-ID: 4"

# 3. Verificar en Stream.io que el canal fue creado con:
#    - Channel ID: direct_gym_4_user_10_gym_4_user_11
#    - Miembros: gym_4_user_10, gym_4_user_11
```

## Notas

1. El problema **NO es solo en iOS** - es un bug del backend
2. El backend **cree** que crea el canal, pero Stream.io lo rechaza
3. Los logs del backend probablemente muestran errores de Stream que fueron ignorados
4. Este fix es **BLOQUEANTE** para cualquier funcionalidad de chat
