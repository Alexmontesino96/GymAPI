# Configuración de Seguridad para Stream Chat

## Resumen de Vulnerabilidad Corregida

Se identificó y corrigió una **vulnerabilidad crítica cross-gym** en el sistema de chat que permitía a usuarios de un gimnasio acceder a chats de otros gimnasios.

## Cambios Implementados

### 1. **Endpoint `/api/v1/chat/token` Securizado**
- ✅ Agregada verificación de gimnasio con `verify_gym_access`
- ✅ Tokens ahora incluyen `gym_id` y expiración de 1 hora
- ✅ Cache de tokens separado por gimnasio

### 2. **Validación de Acceso a Canales**
- ✅ Nuevas funciones de seguridad en `chat_service.py`:
  - `create_secure_channel_id()` - Crea IDs con prefijo de gimnasio
  - `validate_channel_access()` - Valida acceso por gym_id
  - `validate_user_gym_membership()` - Verifica membresía

### 3. **Webhooks de Autorización**
- ✅ Webhook de autorización en `/api/v1/webhooks/stream/auth`
- ✅ Validación en tiempo real de acceso a canales
- ✅ Logging de eventos de seguridad

## Configuración Requerida en Stream Chat Dashboard

Para completar la implementación de seguridad, es **CRÍTICO** configurar los siguientes webhooks en el Stream Chat Dashboard:

### 1. **Webhook de Autorización**
```
URL: https://gymapi-eh6m.onrender.com/api/v1/webhooks/stream/auth
Eventos: channel.join, message.new, channel.read, channel.query
Método: POST
```

### 2. **Configuración de Permisos**
En el Dashboard de Stream Chat, configurar las siguientes políticas:

```json
{
  "policies": {
    "channel.read": {
      "webhook": true,
      "webhook_url": "https://gymapi-eh6m.onrender.com/api/v1/webhooks/stream/auth"
    },
    "channel.join": {
      "webhook": true,
      "webhook_url": "https://gymapi-eh6m.onrender.com/api/v1/webhooks/stream/auth"
    },
    "message.send": {
      "webhook": true,
      "webhook_url": "https://gymapi-eh6m.onrender.com/api/v1/webhooks/stream/auth"
    }
  }
}
```

### 3. **Variables de Entorno**
Asegurar que estén configuradas:
```bash
STREAM_API_KEY=tu_api_key
STREAM_API_SECRET=tu_api_secret
STREAM_WEBHOOK_SECRET=tu_webhook_secret  # Opcional pero recomendado
```

## Migración de Canales Existentes

Los canales existentes siguen el formato legacy (sin prefijo de gimnasio). Para máxima seguridad, se recomienda:

### 1. **Migración Gradual**
```python
# Nuevos canales usarán formato seguro:
# gym_4_event_604_hash
# gym_4_direct_user_10_user_8
# gym_4_room_General_10
```

### 2. **Retrocompatibilidad Temporal**
El sistema actualmente permite acceso a canales legacy pero los registra como advertencias:
```
⚠️ Acceso a canal legacy detectado: event_604_hash por gym 4
```

### 3. **Bloqueo Futuro**
En el futuro, cambiar en `validate_channel_access()`:
```python
# Para producción: cambiar return True por return False
return False  # Bloquear acceso a canales legacy
```

## Verificación de Seguridad

### 1. **Test de Acceso Cross-Gym**
```bash
# Este test debería FALLAR después de la implementación
curl -X POST "https://api.getstream.io/chat/channels/messaging/gym_1_event_123/query" \
  -H "Authorization: Bearer TOKEN_DE_GYM_2"
```

### 2. **Logs de Seguridad**
Monitorear logs para eventos sospechosos:
```
🔐 EVENTO DE SEGURIDAD - access_denied: user=user_10, channel=gym_5_event_123
```

### 3. **Métricas Recomendadas**
- Número de intentos de acceso denegados por día
- Patrones de acceso cross-gym
- Canales legacy aún en uso

## Consideraciones Adicionales

### 1. **Rate Limiting**
Los webhooks pueden generar muchas llamadas. Considerar implementar:
- Cache de validaciones por sesión
- Rate limiting por usuario
- Optimización de consultas de membresía

### 2. **Alertas de Seguridad**
Configurar alertas para:
- Múltiples intentos de acceso denegados
- Patrones anómalos de acceso
- Errores en validación de webhooks

### 3. **Auditoría**
Mantener logs de:
- Todos los accesos denegados
- Cambios en membresías de gimnasio
- Creación/eliminación de canales

## Estado de Implementación

- ✅ **Endpoint de token securizado**
- ✅ **Validaciones de acceso implementadas** 
- ✅ **Webhooks de autorización creados**
- ⏳ **Configuración en Stream Dashboard** (PENDIENTE)
- ⏳ **Migración de canales legacy** (OPCIONAL)

## Próximos Pasos

1. **INMEDIATO**: Configurar webhooks en Stream Chat Dashboard
2. **CORTO PLAZO**: Monitorear logs de seguridad por 1 semana
3. **MEDIANO PLAZO**: Migrar canales legacy a formato seguro
4. **LARGO PLAZO**: Implementar alertas automatizadas de seguridad

---

**⚠️ IMPORTANTE**: Sin la configuración del webhook en Stream Dashboard, los usuarios aún pueden usar tokens directamente con Stream.io SDK para acceder a canales de otros gimnasios. La configuración del webhook es CRÍTICA para completar la securización.