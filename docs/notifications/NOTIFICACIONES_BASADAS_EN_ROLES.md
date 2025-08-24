# Sistema de Notificaciones Basado en Roles

## 🎯 Objetivo
Implementar notificaciones inteligentes que solo se envíen cuando el autor del mensaje tiene la autoridad apropiada según el tipo de contenido.

## 🚀 Implementación Completada

### Lógica de Notificaciones por Tipo de Contenido:

#### 📅 EVENTOS:
- **Condición**: Solo notifica si el autor tiene rol `TRAINER`, `ADMIN` o `OWNER`
- **Razón**: Solo personal autorizado puede anunciar eventos oficiales del gimnasio
- **Filtro**: Se verifica autoridad antes de enviar notificaciones

#### 💬 CHAT:
- **Condición**: Notificación normal (usuarios offline con mensajes no leídos)
- **Razón**: Conversaciones abiertas para todos los miembros
- **Filtro**: Solo se aplica el filtro inteligente estándar

## 🔧 Funciones Implementadas

### 1. `determine_content_type(chat_room, message_text)`
```python
def determine_content_type(chat_room: ChatRoom, message_text: str) -> str:
    """
    Determina si un mensaje es tipo "event" o "chat" basado en:
    - Nombre del canal (contiene: evento, event, clase, class, schedule)
    - Palabras clave del mensaje (clase, sesion, entrenamiento, etc.)
    """
```

**Palabras clave de eventos:**
- clase, sesion, session
- entrenamiento, training
- evento, event
- reserva, booking
- cancelar, cancel
- horario, schedule
- gimnasio, gym
- instructor, trainer

### 2. `check_user_authority_in_gym(db, user_id, gym_id)`
```python
async def check_user_authority_in_gym(db: Session, user_id: int, gym_id: int) -> bool:
    """
    Verifica si un usuario tiene autoridad en el gimnasio:
    - TRAINER ✅
    - ADMIN ✅  
    - OWNER ✅
    - MEMBER ❌
    """
```

### 3. `send_targeted_notifications(..., content_type)`
```python
async def send_targeted_notifications(
    db: Session,
    users_to_notify: list,
    chat_room: ChatRoom,
    message_text: str,
    sender_id: int,
    content_type: str = "chat"  # "chat" o "event"
):
    """
    Aplica lógica de notificación según el tipo de contenido:
    - Para eventos: verifica autoridad del remitente
    - Para chat: notificación normal
    """
```

## 📋 Flujo de Procesamiento

```
Mensaje recibido
       ↓
1. Determinar tipo de contenido (event/chat)
       ↓
2. Filtrar usuarios elegibles (offline + unread)
       ↓
3. Si es EVENTO: verificar autoridad del remitente
       ↓
4. Si tiene autoridad O es CHAT: enviar notificaciones
       ↓
5. Personalizar título según tipo de contenido
```

## 🎭 Ejemplos de Comportamiento

### Escenario 1: Trainer anuncia clase
```
👤 Remitente: TRAINER (autorizado)
📝 Mensaje: "Nueva clase de yoga mañana a las 8am"
🎭 Tipo: EVENTO (contiene "clase")
✅ Resultado: Notificaciones enviadas
📱 Título: "📅 Juan (Trainer) - Evento en Fitness Center"
```

### Escenario 2: Member intenta anunciar evento
```
👤 Remitente: MEMBER (no autorizado)
📝 Mensaje: "Cancelé la clase de spinning"
🎭 Tipo: EVENTO (contiene "clase" y "cancelé")
🚫 Resultado: Notificaciones NO enviadas
📝 Log: "Evento NO notificado: Pedro (ID: 5) no tiene autoridad"
```

### Escenario 3: Chat normal
```
👤 Remitente: MEMBER
📝 Mensaje: "Hola, alguien quiere entrenar conmigo?"
🎭 Tipo: CHAT (sin palabras clave de evento)
✅ Resultado: Notificaciones enviadas normalmente
📱 Título: "💬 Pedro en Chat General"
```

## 🔍 Logging Detallado

El sistema incluye logs específicos para debugging:

```
🎭 Mensaje detectado como EVENTO: canal='eventos-gym', keywords=True
🎭 Usuario 8 role: TRAINER, autoridad: True
✅ Evento SÍ notificado: Juan tiene autoridad (True)
📤 Enviando notificación event a 3 usuarios

🎭 Mensaje detectado como CHAT normal
📤 Enviando notificación chat a 2 usuarios
```

## 📱 Títulos de Notificaciones

### Para Eventos:
```
📅 {sender_name} - Evento en {chat_name}
```

### Para Chat:
```
💬 {sender_name} en {chat_name}
```

## ⚙️ Configuración Personalizable

### Variables que se pueden ajustar:

1. **Palabras clave de eventos**:
   ```python
   event_keywords = [
       "clase", "sesion", "session", "entrenamiento", "training",
       "evento", "event", "reserva", "booking", "cancelar", "cancel",
       "horario", "schedule", "gimnasio", "gym", "instructor", "trainer"
   ]
   ```

2. **Patrones de canales de eventos**:
   ```python
   event_channel_patterns = ["evento", "event", "clase", "class", "schedule"]
   ```

3. **Roles con autoridad**:
   ```python
   authority_roles = [GymRoleType.TRAINER, GymRoleType.ADMIN, GymRoleType.OWNER]
   ```

## 📊 Beneficios

### 🔒 Seguridad:
- Solo personal autorizado puede enviar notificaciones de eventos
- Previene spam de anuncios no oficiales
- Mantiene autoridad de comunicación institucional

### 👥 Experiencia de Usuario:
- Los miembros reciben solo eventos oficiales
- Chat personal sigue funcionando normalmente
- Notificaciones más relevantes y confiables

### 📈 Control de Calidad:
- Eventos anunciados solo por staff calificado
- Reduce confusión por información incorrecta
- Mejora comunicación oficial del gimnasio

## 🧪 Testing

### Para probar el sistema:

1. **Como TRAINER/ADMIN/OWNER**:
   - Enviar mensaje con palabras como "clase", "evento", "horario"
   - Verificar que se envían notificaciones
   - Confirmar título "📅 Evento"

2. **Como MEMBER**:
   - Enviar mensaje con palabras de evento
   - Verificar que NO se envían notificaciones
   - Revisar logs de "no tiene autoridad"

3. **Chat normal**:
   - Enviar mensaje sin palabras clave de evento
   - Verificar notificaciones normales
   - Confirmar título "💬 Chat"

## 🚀 Próximas Mejoras

### Funcionalidades futuras:
- **Canales específicos**: Diferentes reglas por tipo de sala
- **Configuración por gimnasio**: Roles personalizables
- **Notificaciones prioritarias**: Urgencia para emergencias
- **Programación**: Eventos programados automáticamente
- **Aprobación**: Workflow para eventos propuestos por miembros

¡El sistema ahora respeta la jerarquía de roles y mantiene la autoridad de comunicación oficial!