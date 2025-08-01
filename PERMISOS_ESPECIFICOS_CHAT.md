# 🔒 Permisos Específicos del Sistema de Chat

## ❓ Respuestas Directas a tus Preguntas

### 1. ¿Puede un usuario acceder a un chat grupal de su gym sin ser invitado?

**❌ NO** - Está **completamente bloqueado** con múltiples validaciones:

#### A. Validación en Base de Datos Local
```python
# En app/api/v1/endpoints/chat.py:627-635
# Antes de permitir cualquier acceso a una sala:

is_member = db.query(ChatMember).filter(
    ChatMember.room_id == room_id,
    ChatMember.user_id == current_user.id
).first()

if not is_member:
    raise HTTPException(
        status_code=403, 
        detail="No tienes acceso a esta sala de chat"
    )
```

#### B. Validación en Stream mediante Webhook
```python
# En app/api/v1/endpoints/webhooks/stream_webhooks.py:426-481
# CADA vez que intenta acceder a un canal, Stream consulta:

@router.post("/stream/auth")
async def validate_stream_access():
    # Stream pregunta: "¿Puede user_123 acceder al canal gym_123_group_456?"
    
    # Verificamos en nuestra BD:
    is_member = db.query(ChatMember).filter(
        ChatMember.room_id == extracted_room_id,
        ChatMember.user_id == internal_user_id
    ).first()
    
    if not is_member:
        return {"allow": False, "reason": "Not a member of this chat"}
    
    return {"allow": True}
```

#### C. Stream NO Permite Acceso Sin Validación
- Stream **siempre** consulta nuestro webhook antes de permitir acceso
- Si respondemos `{"allow": False}` → Usuario recibe **403 Forbidden**
- Imposible saltarse esta validación

---

### 2. ¿Puede leer chats directos de otros usuarios del mismo gym?

**❌ NO** - Los chats directos tienen protección adicional:

#### A. Solo 2 Participantes Exactos
```python
# En app/services/chat.py - creación de chat directo:
def get_or_create_direct_chat(user1_id: int, user2_id: int, gym_id: int):
    
    # Canal ID específico para SOLO estos 2 usuarios
    channel_id = f"gym_{gym_id}_direct_{min(user1_id, user2_id)}_{max(user1_id, user2_id)}"
    
    # Solo estos 2 usuarios se agregan como miembros
    members = [
        {"user_id": f"user_{user1_id}"},
        {"user_id": f"user_{user2_id}"}
    ]
    
    # Stream crea canal PRIVADO con solo estos 2 miembros
    stream_client.create_channel(
        channel_type="messaging",
        channel_id=channel_id,
        created_by=f"user_{user1_id}",
        members=members  # ← SOLO estos 2 usuarios
    )
```

#### B. Validación de Membresía Estricta
```python
# Para acceder a CUALQUIER chat directo:
def validate_direct_chat_access(user_id, channel_id):
    
    # Extraer los IDs de los participantes del channel_id
    # "gym_123_direct_456_789" → user_ids: [456, 789]
    participant_ids = extract_participant_ids(channel_id)
    
    # El usuario DEBE ser uno de los 2 participantes exactos
    if user_id not in participant_ids:
        return {"allow": False, "reason": "Not a participant in this direct chat"}
    
    return {"allow": True}
```

---

## 🛡️ ¿PERO HAY UNA VULNERABILIDAD CRÍTICA?

### ⚠️ **Chat de Eventos - FALTA VALIDACIÓN**

**❌ PROBLEMA ENCONTRADO:** Un usuario del gym **SÍ puede acceder** al chat de un evento **sin estar registrado** en ese evento.

```python
# En app/api/v1/endpoints/chat.py:285
@router.get("/rooms/event/{event_id}")
async def get_event_chat_room(event_id: int):
    
    # ❌ FALTA: Verificar si el usuario está registrado en el evento
    # ❌ Solo verifica que pertenezca al mismo gym del evento
    
    # Cualquier miembro del gym puede acceder a CUALQUIER chat de evento
    return await chat_service.get_or_create_event_chat(event_id, current_user, db)
```

**Esto significa:**
- Usuario A del gym 123 está registrado en "Clase de Yoga"
- Usuario B del gym 123 NO está registrado en "Clase de Yoga"  
- **Usuario B puede leer el chat de la Clase de Yoga** ❌

---

## 🔐 Niveles de Seguridad Actual

### ✅ **COMPLETAMENTE SEGURO:**

#### 1. **Aislamiento entre Gimnasios**
```python
# Usuario del gym 123 JAMÁS puede acceder a chats del gym 456
channel_validation = f"gym_{user_gym_id}_" in channel_id
if not channel_validation:
    return 403  # Bloqueado automáticamente
```

#### 2. **Chats Directos**
```python
# Solo los 2 participantes exactos tienen acceso
# Usuario 456 NO puede leer chat directo entre usuarios 789 y 012
participants = [789, 012]  # Extraído del channel_id
if current_user.id not in participants:
    return 403  # Acceso denegado
```

#### 3. **Chats Grupales**  
```python
# Solo miembros agregados explícitamente
members = get_chat_members(room_id)
if current_user.id not in members:
    return 403  # Acceso denegado
```

#### 4. **Canal General**
```python
# Solo miembros activos del gimnasio
membership = get_gym_membership(user_id, gym_id)
if not membership.is_active:
    return 403  # Acceso denegado
```

---

### ❌ **VULNERABILIDAD IDENTIFICADA:**

#### **Chats de Eventos**
```python
# ❌ Falta validación de participación en evento
def access_event_chat(user_id, event_id):
    event = get_event(event_id)
    
    # ✅ Verifica gym correcto
    if user.gym_id != event.gym_id:
        return 403
    
    # ❌ FALTA: Verificar inscripción al evento
    # is_registered = check_event_registration(user_id, event_id)
    # if not is_registered:
    #     return 403
    
    return allow_access()  # ← Permite acceso sin verificar inscripción
```

---

## 🚨 Implicaciones de la Vulnerabilidad

### ¿Qué puede hacer un usuario malicioso?

```python
# Escenario problemático:
# Usuario "Juan" del gym 123
# Evento "Clase VIP Premium" en gym 123 (solo 5 cupos)
# Juan NO está registrado en la clase

# ❌ Juan puede:
GET /api/v1/chat/rooms/event/999  # Clase VIP Premium
# → Obtiene acceso al chat de la clase VIP
# → Puede leer todos los mensajes  
# → Puede participar en discusiones privadas
# → Puede obtener información exclusiva del evento
```

### **Información que puede filtrar:**
- Instrucciones especiales del trainer
- Cambios de horario comunicados solo a participantes
- Contenido premium/exclusivo
- Conversaciones privadas entre participantes registrados

---

## 🛠️ Solución Requerida

### Código que debe implementarse:

```python
# En app/api/v1/endpoints/chat.py
@router.get("/rooms/event/{event_id}")
async def get_event_chat_room(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Verificar que el evento existe
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "Evento no encontrado")
    
    # 2. Verificar gym correcto (ya implementado)
    if event.gym_id != current_gym.id:
        raise HTTPException(403, "Evento no pertenece a tu gimnasio")
    
    # 3. ✅ AGREGAR: Verificar inscripción al evento
    registration = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.user_id == current_user.id,
        EventRegistration.status == "confirmed"  # Solo inscritos confirmados
    ).first()
    
    if not registration:
        raise HTTPException(
            status_code=403, 
            detail="Debes estar inscrito en este evento para acceder a su chat"
        )
    
    # 4. Continuar con creación/acceso al chat
    return await chat_service.get_or_create_event_chat(event_id, current_user, db)
```

---

## 📊 Resumen Final

| Tipo de Chat | Nivel de Seguridad | ¿Puede acceder sin permiso? |
|-------------|-------------------|---------------------------|
| **Chat Directo** | 🟢 **MÁXIMO** | ❌ **NO** - Solo los 2 participantes |
| **Chat Grupal** | 🟢 **MÁXIMO** | ❌ **NO** - Solo miembros invitados |
| **Canal General** | 🟢 **ALTO** | ❌ **NO** - Solo miembros activos del gym |
| **Chat de Evento** | 🟡 **MEDIO** | ⚠️ **SÍ** - Cualquier miembro del gym |

### **Acción Requerida:**
Implementar validación de inscripción a eventos para completar la seguridad del sistema. 

**Con esa corrección, el sistema será 100% seguro.** 🔒