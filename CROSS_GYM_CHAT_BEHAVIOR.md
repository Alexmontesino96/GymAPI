# 🔄 Comportamiento Cross-Gym de Chats Directos

**Fecha:** 2025-12-14
**Feature:** Chats directos visibles desde todos los gimnasios compartidos

---

## 📋 Resumen

Los chats directos entre usuarios que comparten múltiples gimnasios ahora son **visibles desde todos los gimnasios compartidos**, sin importar en qué gimnasio se creó originalmente el chat.

---

## 🎯 Comportamiento Implementado

### Escenario Ejemplo

**Setup:**
- `User A` pertenece a: `gym_1`, `gym_2`
- `User B` pertenece a: `gym_1`, `gym_2`

**Flujo:**

1. **User A** desde `gym_2` → `GET /chat/rooms/direct/user_b` con `X-Gym-ID: 2`
   - Backend crea chat directo con `gym_id=2`
   - Backend retorna ChatRoom

2. **User A** desde `gym_1` → `GET /my-rooms` con `X-Gym-ID: 1`
   - Backend detecta que es un chat directo
   - Backend verifica que **ambos usuarios** (A y B) están en `gym_1`
   - ✅ Backend **incluye el chat** en la respuesta (aunque `gym_id=2`)

3. **User A** desde `gym_2` → `GET /my-rooms` con `X-Gym-ID: 2`
   - Backend encuentra chat con `gym_id=2`
   - ✅ Backend **incluye el chat** en la respuesta

**Resultado:** El chat directo aparece en **ambos gimnasios** (gym_1 y gym_2)

---

## 🔧 Cambios Implementados

### 1. Validación Cross-Gym en `/chat/rooms/direct/{user_id}`

**Archivo:** `app/api/v1/endpoints/chat.py:210-235`

```python
# Verificar que ambos usuarios comparten al menos un gimnasio
common_gyms = current_user_gym_ids & other_user_gym_ids

if not common_gyms:
    raise HTTPException(403, "No compartes ningún gimnasio con este usuario")

# Usar gym_id del request si está en común, sino el primero compartido
shared_gym_id = current_gym.id if current_gym.id in common_gyms else list(common_gyms)[0]
```

**Antes:**
- ❌ Requería que ambos usuarios estuvieran en el **mismo gym exacto**
- ❌ Bloqueaba chats entre usuarios multi-gym

**Después:**
- ✅ Permite chats si comparten **al menos un gimnasio**
- ✅ Usa el gym del request si es compartido, sino usa el primero compartido

---

### 2. Filtro gym_id Opcional en Repository

**Archivo:** `app/repositories/chat.py:70-96`

```python
def get_direct_chat(
    self,
    db: Session,
    *,
    user1_id: int,
    user2_id: int,
    gym_id: Optional[int] = None  # ← Nuevo parámetro
) -> Optional[ChatRoom]:
    # Si gym_id se especifica, filtrar por él
    if gym_id is not None:
        query = query.filter(ChatRoom.gym_id == gym_id)
```

**Antes:**
- ❌ Buscaba chats sin filtrar por gym_id
- ❌ Retornaba el primer chat encontrado (inconsistente)

**Después:**
- ✅ Filtra por gym_id cuando se especifica
- ✅ Comportamiento predecible y consistente

---

### 3. Visibilidad Cross-Gym en `/my-rooms`

**Archivo:** `app/api/v1/endpoints/chat.py:931-977`

```python
# Filtrar por gym:
# 1. Chats con gym_id == current_gym (comportamiento normal)
# 2. Chats directos donde TODOS los miembros están en current_gym (cross-gym)

for room in user_rooms_query.all():
    # Incluir si está en el gym actual
    if room.gym_id == current_gym.id:
        filtered_rooms.append(room)

    # Incluir si es chat directo Y todos los miembros están en el gym actual
    elif room.is_direct:
        member_ids = [member.user_id for member in room.members]

        # Verificar que TODOS los miembros estén en current_gym
        members_in_gym = db.query(UserGym).filter(
            and_(
                UserGym.user_id.in_(member_ids),
                UserGym.gym_id == current_gym.id
            )
        ).count()

        if members_in_gym == len(member_ids):
            filtered_rooms.append(room)  # ✅ Incluir chat cross-gym
```

**Antes:**
- ❌ Solo mostraba chats con `gym_id == current_gym`
- ❌ Chats cross-gym desaparecían de la lista

**Después:**
- ✅ Muestra chats con `gym_id == current_gym` (normal)
- ✅ **Además** muestra chats directos donde todos los miembros están en `current_gym`

---

## 📊 Tabla de Comportamiento

| Situación | gym_id del Chat | User A en | User B en | Gym Actual (request) | ¿Aparece en /my-rooms? |
|-----------|-----------------|-----------|-----------|----------------------|------------------------|
| Normal | 1 | gym_1 | gym_1 | gym_1 | ✅ SÍ (match directo) |
| Normal | 1 | gym_1 | gym_1 | gym_2 | ❌ NO (gym_id diferente) |
| Cross-gym | 2 | gym_1, gym_2 | gym_1, gym_2 | gym_1 | ✅ SÍ (ambos en gym_1) |
| Cross-gym | 2 | gym_1, gym_2 | gym_1, gym_2 | gym_2 | ✅ SÍ (match directo) |
| Cross-gym | 2 | gym_1, gym_2 | gym_2, gym_3 | gym_1 | ❌ NO (User B no en gym_1) |
| Cross-gym | 2 | gym_1, gym_2 | gym_2, gym_3 | gym_3 | ❌ NO (User A no en gym_3) |

---

## 🧪 Casos de Prueba

### Test 1: Chat Cross-Gym Visible desde Ambos Gyms

**Setup:**
```
User A: gym_1, gym_2
User B: gym_1, gym_2
```

**Steps:**
1. User A → `POST /chat/rooms/direct/user_b` con `X-Gym-ID: 2`
   - **Esperado:** ChatRoom creado con `gym_id=2`

2. User A → `GET /my-rooms` con `X-Gym-ID: 1`
   - **Esperado:** ✅ Chat aparece en lista

3. User A → `GET /my-rooms` con `X-Gym-ID: 2`
   - **Esperado:** ✅ Chat aparece en lista

---

### Test 2: Chat NO Visible si Usuario No en Gym

**Setup:**
```
User A: gym_1, gym_2
User B: gym_2, gym_3
Chat creado en: gym_2
```

**Steps:**
1. User A → `GET /my-rooms` con `X-Gym-ID: 1`
   - **Esperado:** ❌ Chat NO aparece (User B no está en gym_1)

2. User A → `GET /my-rooms` con `X-Gym-ID: 2`
   - **Esperado:** ✅ Chat aparece (ambos en gym_2)

---

### Test 3: Chats de Grupo NO Afectados

**Setup:**
```
User A: gym_1, gym_2
Chat de grupo en: gym_2
```

**Steps:**
1. User A → `GET /my-rooms` con `X-Gym-ID: 1`
   - **Esperado:** ❌ Chat de grupo NO aparece (solo gym_id=2)

2. User A → `GET /my-rooms` con `X-Gym-ID: 2`
   - **Esperado:** ✅ Chat de grupo aparece

**Razón:** Solo chats **directos** (`is_direct=True`) usan lógica cross-gym

---

## 🎨 Experiencia de Usuario en iOS

### Antes (Comportamiento Problemático)

```
User A selecciona User B → Tap "Message" (desde gym_1)
→ Backend crea chat en gym_2 (compartido)
→ Chat se abre correctamente ✅
→ User regresa a lista de chats
→ Chat NO aparece en lista ❌ ← PROBLEMA
```

### Después (Comportamiento Correcto)

```
User A selecciona User B → Tap "Message" (desde gym_1)
→ Backend crea chat en gym_1 (gym del request, si compartido)
→ Chat se abre correctamente ✅
→ User regresa a lista de chats
→ Chat SÍ aparece en lista ✅ ← CORREGIDO

User A cambia a gym_2
→ Mismo chat SÍ aparece también en gym_2 ✅ ← NUEVO
```

---

## 🚀 Ventajas del Nuevo Comportamiento

1. ✅ **Consistencia:** Chats no "desaparecen" después de crearse
2. ✅ **UX mejorada:** Usuarios multi-gym ven sus chats desde cualquier gym compartido
3. ✅ **Menos confusión:** No hay chats "fantasma"
4. ✅ **Cumple expectativas:** Comportamiento similar a WhatsApp/Telegram

---

## ⚠️ Consideraciones

### Chats de Grupo vs Chats Directos

- **Chats directos** (`is_direct=True`): Usan lógica cross-gym
- **Chats de grupo/evento** (`is_direct=False`): Solo visibles en su `gym_id` original

**Razón:** Los grupos están explícitamente asociados a un gimnasio específico (ej: evento de gym_2)

### Performance

La nueva lógica en `/my-rooms`:
- ✅ **Eficiente:** Solo 1 query adicional por chat directo cross-gym
- ✅ **Escalable:** No afecta chats de grupo (mayoría de casos)
- ⚠️ **Considerar:** Si hay muchos chats directos, podría optimizarse con un join

### Caché

- Los chats directos tienen caché de **5 minutos** en memoria
- Cambios en membresías de gym pueden tardar hasta 5 min en reflejarse

---

## 📝 Archivos Modificados

| Archivo | Función | Cambio |
|---------|---------|--------|
| `app/api/v1/endpoints/chat.py` | `get_or_create_direct_chat()` | Validación cross-gym con gyms compartidos |
| `app/api/v1/endpoints/chat.py` | `get_user_chat_rooms()` | Incluir chats directos cross-gym en lista |
| `app/repositories/chat.py` | `get_direct_chat()` | Parámetro `gym_id` opcional para filtrado |
| `app/services/chat.py` | `get_or_create_direct_chat()` | Pasar `gym_id` al repository |

---

## ✅ Verificación

### Auditoría Stream Chat

```bash
python scripts/audit_stream_sync.py --gym-id 5
```

**Resultado esperado:**
- ✅ 100% sincronización
- ✅ 0 canales huérfanos
- ✅ team == gym_id en todos los canales

### Tests de Integración

Crear tests en `tests/api/test_chat.py`:

```python
def test_cross_gym_direct_chat_visibility():
    """Test que chat directo aparece en ambos gyms compartidos"""
    # Setup: User A y B en gym_1 y gym_2
    # Crear chat en gym_2
    # Verificar que aparece en /my-rooms de gym_1 Y gym_2
```

---

## 🔗 Referencias

- **Análisis Root Cause:** `STREAM_SYNC_IOS_FLOW_ANALYSIS.md`
- **Script de Corrección:** `fix_chatroom_643_simple.py`
- **Documentación Chat API:** `docs/CHAT_MANAGEMENT_API.md`

---

## 📞 Contacto

Si encuentras algún comportamiento inesperado, reportar issue con:
- IDs de usuarios involucrados
- Gimnasios a los que pertenecen
- `gym_id` del chat
- `X-Gym-ID` usado en el request
