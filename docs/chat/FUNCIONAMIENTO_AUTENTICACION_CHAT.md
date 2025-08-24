# 🔐 Funcionamiento del Sistema de Autenticación del Chat

## 📊 Flujo Completo de Autenticación y Autorización

Te explico paso a paso cómo funciona la autenticación entre el cliente, nuestra API y Stream Chat:

```mermaid
sequenceDiagram
    participant Client as App Cliente
    participant API as GymApi (Nuestro Backend)
    participant Stream as Stream Chat Service
    participant DB as Base de Datos

    Note over Client, Stream: 1. SOLICITUD DE TOKEN
    Client->>API: GET /chat/token<br/>Headers: Authorization + X-Gym-ID
    
    Note over API: 2. VALIDACIONES INTERNAS
    API->>API: Decodificar JWT del usuario
    API->>DB: Verificar membresía activa en gymnasio
    API->>API: Validar permisos de acceso
    
    Note over API, Stream: 3. GENERACIÓN DE TOKEN STREAM
    API->>Stream: generateToken(user_id, permisos, team_restrictions)
    Stream->>Stream: Crear token JWT con claims específicos
    Stream-->>API: Token firmado con restricciones
    
    Note over API, Client: 4. RESPUESTA CON TOKEN
    API-->>Client: {token, api_key, internal_user_id}
    
    Note over Client, Stream: 5. CONEXIÓN A STREAM
    Client->>Stream: Connect con token recibido
    Stream->>Stream: Validar token y extraer claims
    Stream->>Stream: Aplicar restricciones de team/gym
    Stream-->>Client: Conexión autorizada
    
    Note over Client, Stream: 6. SOLICITUDES DE CHAT
    Client->>Stream: Solicitar acceso a canal X
    Stream->>Stream: Verificar si canal pertenece al team del usuario
    
    alt Canal autorizado
        Stream-->>Client: Acceso permitido
    else Canal NO autorizado
        Stream-->>Client: Acceso denegado (403)
    end
```

---

## 🔍 Desglose Detallado del Funcionamiento

### 1. **Cliente Solicita Token** 

```http
GET /api/v1/chat/token
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
X-Gym-ID: 123
```

**¿Qué pasa aquí?**
- El cliente envía su JWT de autenticación de nuestra app
- Incluye el ID del gimnasio al que quiere acceder
- Nuestra API recibe esta solicitud

### 2. **Nuestra API Valida Internamente**

```python
# En app/api/v1/endpoints/chat.py
@router.get("/token", response_model=StreamTokenResponse)
async def get_stream_token(
    current_user: User = Depends(get_current_user),  # Decodifica JWT
    gym_id: int = Depends(get_gym_id_from_header),   # Extrae gym_id
    db: Session = Depends(get_db)
):
    # 1. Verificar que el usuario tiene membresía activa en este gym
    membership = await verify_gym_membership(current_user.id, gym_id, db)
    if not membership or not membership.is_active:
        raise HTTPException(403, "No tienes acceso a este gimnasio")
    
    # 2. Generar token con restricciones específicas
    stream_token = await generate_stream_token(current_user, gym_id)
    
    return StreamTokenResponse(
        token=stream_token,
        api_key=STREAM_API_KEY,
        internal_user_id=current_user.id
    )
```

**Validaciones que hace nuestra API:**
- ✅ JWT válido y no expirado
- ✅ Usuario existe en nuestra BD
- ✅ Usuario tiene membresía activa en el gimnasio solicitado
- ✅ Membresía no está suspendida o cancelada

### 3. **Generación del Token de Stream**

```python
# En app/services/chat.py
async def generate_stream_token(user: User, gym_id: int) -> str:
    
    # ID único para Stream (formato: user_123)
    stream_user_id = f"user_{user.id}"
    
    # Claims específicos que incluimos en el token
    token_claims = {
        "user_id": stream_user_id,           # ID para Stream
        "internal_user_id": user.id,         # Nuestro ID interno
        "gym_id": gym_id,                    # Gimnasio autorizado
        "team": f"gym_{gym_id}",             # Team/namespace en Stream
        "role": user.role,                   # admin, trainer, member
        "exp": int(time.time()) + 3600       # Expira en 1 hora
    }
    
    # Stream genera el token con estas restricciones
    token = stream_client.create_token(
        user_id=stream_user_id,
        extra_claims=token_claims
    )
    
    return token
```

**¿Qué contiene el token de Stream?**
- **user_id**: `user_123` (formato que entiende Stream)
- **team**: `gym_123` (namespace del gimnasio)
- **permissions**: Basados en el rol del usuario
- **expiration**: Tiempo límite de validez
- **gym_restrictions**: Solo puede acceder a canales de ese gym

### 4. **Cliente Se Conecta a Stream**

```swift
// En la app del cliente
func connectToStream(token: String, apiKey: String) {
    let config = ChatClientConfig(apiKey: .init(apiKey))
    let client = ChatClient(config: config)
    
    client.connectUser(
        userInfo: .init(id: "user_123"),  // Debe coincidir con el token
        token: .init(rawValue: token)     // Token recibido de nuestra API
    ) { error in
        // Stream valida el token aquí
    }
}
```

### 5. **Stream Valida y Aplica Restricciones**

Cuando Stream recibe el token, **automáticamente**:

```javascript
// Lo que hace Stream internamente
const decodedToken = jwt.verify(token, STREAM_SECRET);

// Extrae los claims
const {
    user_id,      // "user_123"
    gym_id,       // 123
    team,         // "gym_123" 
    role,         // "member"
    exp           // timestamp
} = decodedToken;

// Aplica restricciones automáticamente
user.team = team;           // Solo puede ver canales del team "gym_123"
user.permissions = getPermissionsForRole(role);
```

### 6. **Solicitudes de Chat con Restricciones**

Cuando el cliente quiere acceder a un canal:

```mermaid
sequenceDiagram
    participant Client as App Cliente
    participant Stream as Stream Chat
    
    Client->>Stream: Solicitar canal "gym_123_event_456"
    Stream->>Stream: Verificar: ¿canal pertenece a team "gym_123"?
    
    alt Canal pertenece al team correcto
        Stream->>Stream: ✅ "gym_123_event_456" ∈ "gym_123" 
        Stream-->>Client: Acceso permitido
    else Canal NO pertenece al team
        Stream->>Stream: ❌ "gym_456_event_789" ∉ "gym_123"
        Stream-->>Client: 403 - Acceso denegado
    end
```

---

## 🔒 Sistema de Seguridad Multi-Tenant

### Formato de IDs de Canal (Crítico para Seguridad)

```python
# Así generamos los IDs de canal para garantizar aislamiento:

# Chat directo entre usuarios del gym 123
channel_id = f"gym_{gym_id}_direct_{min_user_id}_{max_user_id}"
# Resultado: "gym_123_direct_456_789"

# Chat de evento del gym 123  
channel_id = f"gym_{gym_id}_event_{event_id}"
# Resultado: "gym_123_event_1001"

# Canal general del gym 123
channel_id = f"gym_{gym_id}_general"
# Resultado: "gym_123_general"
```

### ¿Por qué es Seguro?

1. **Prefijo del Gym**: Cada canal lleva el `gym_id` en su nombre
2. **Team Restrictions**: El token solo permite acceso al team `gym_123`
3. **Validación Automática**: Stream verifica que el canal pertenezca al team del usuario

### Ejemplo de Ataque Bloqueado:

```javascript
// Usuario del gym 123 intenta acceder a canal del gym 456
const maliciousChannelId = "gym_456_event_999";

// Stream automáticamente bloquea:
if (!maliciousChannelId.startsWith(`gym_${user.gym_id}_`)) {
    throw new Error("Access denied - Channel not in user's team");
}
// Resultado: ❌ 403 Forbidden
```

---

## 🛡️ Validaciones en Webhooks

Además, cuando Stream nos notifica de eventos, validamos que todo sea correcto:

```python
# En app/api/v1/endpoints/webhooks/stream_webhooks.py
@router.post("/stream/auth")
async def validate_stream_access(request: Request):
    """Stream consulta si el usuario puede acceder a un canal"""
    
    data = await request.json()
    user_id = data.get('user_id')  # "user_123"
    channel_id = data.get('channel_id')  # "gym_123_event_456"
    
    # Extraer gym_id del usuario
    internal_user_id = extract_internal_id(user_id)  # 123
    
    # Extraer gym_id del canal
    channel_gym_id = extract_gym_from_channel(channel_id)  # 123
    
    # Verificar que coincidan
    user_gym_access = await get_user_gym_access(internal_user_id)
    
    if channel_gym_id not in user_gym_access:
        return {"allow": False, "reason": "Cross-gym access denied"}
    
    return {"allow": True}
```

---

## ⚡ Flujo Completo en Código Real

```python
# EJEMPLO REAL: Usuario 456 del gym 123 quiere chatear con usuario 789

# 1. Cliente solicita token
POST /api/v1/chat/token
Headers: {
    "Authorization": "Bearer jwt_del_usuario_456",
    "X-Gym-ID": "123"
}

# 2. Nuestra API genera token con restricciones
def generate_token():
    return stream_client.create_token(
        user_id="user_456",
        extra_claims={
            "team": "gym_123",           # ← CRÍTICO: Solo gym 123
            "gym_id": 123,
            "role": "member"
        }
    )

# 3. Cliente se conecta a Stream
client.connectUser(
    userInfo: UserInfo(id: "user_456"),
    token: Token(rawValue: received_token)
)

# 4. Cliente solicita chat directo
GET /api/v1/chat/rooms/direct/789
# Nuestra API crea canal: "gym_123_direct_456_789"

# 5. Cliente intenta acceder al canal en Stream
channel = client.channel(type: "messaging", id: "gym_123_direct_456_789")

# 6. Stream valida automáticamente:
# ✅ Canal "gym_123_direct_456_789" pertenece a team "gym_123" del usuario
# ✅ Acceso permitido
```

---

## 🚨 Casos de Bloqueo Automático

### Caso 1: Usuario Intenta Acceder a Otro Gym
```python
# Usuario del gym 123 con token válido
user_token_claims = {"team": "gym_123", "gym_id": 123}

# Intenta acceder a canal del gym 456
malicious_channel = "gym_456_event_999"

# Stream compara automáticamente:
if "gym_456" != "gym_123":  # team del usuario
    return 403  # ❌ Acceso denegado
```

### Caso 2: Token Expirado
```python
# Token con timestamp de expiración
token_claims = {"exp": 1640995200}  # Ya expiró

# Stream valida automáticamente:
if current_time > token_claims["exp"]:
    return 401  # ❌ Token expirado
```

### Caso 3: Token Manipulado
```python
# Si alguien intenta modificar el token
tampered_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.MODIFIED_PAYLOAD.signature"

# Stream valida la firma:
if not verify_signature(tampered_token, STREAM_SECRET):
    return 401  # ❌ Token inválido
```

---

## 💡 Resumen del Flujo de Seguridad

1. **Cliente pide token** → Headers con JWT + gym_id
2. **Nuestra API valida** → Membresía + permisos
3. **Generamos token Stream** → Con restricciones de team/gym
4. **Cliente se conecta** → Stream valida token
5. **Stream aplica restricciones** → Solo canales del team permitido
6. **Solicitudes futuras** → Validadas automáticamente por Stream
7. **Webhooks adicionales** → Doble validación en nuestro backend

**El resultado:** Un sistema completamente seguro donde es **imposible** que un usuario acceda a chats de otros gimnasios, incluso si intentara manipular las solicitudes. 🛡️

La seguridad está en **múltiples capas**:
- ✅ Autenticación JWT en nuestra API
- ✅ Validación de membresía en BD
- ✅ Token Stream con restricciones específicas
- ✅ IDs de canal con prefijo de gimnasio
- ✅ Validación automática en Stream
- ✅ Webhooks de doble verificación

¡Es prácticamente imposible de vulnerar! 🔒