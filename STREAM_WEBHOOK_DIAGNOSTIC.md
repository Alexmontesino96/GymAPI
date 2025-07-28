# Stream Webhook Diagnóstico - Implementación Completa

## 🎯 Objetivo
Implementar logging completo en el webhook de Stream para diagnosticar por qué no se ven logs de mensajes de Stream en el servidor.

## ✅ Cambios Implementados

### 1. Logging Mejorado en Verificación de Firma
- ✅ Log detallado de signature recibida vs esperada
- ✅ Log del tamaño del body
- ✅ Log del API secret (parcial por seguridad)
- ✅ Logs de éxito/error en verificación

### 2. Logging Completo en Endpoint Principal
- ✅ Log de TODOS los headers recibidos
- ✅ Log del payload completo de Stream
- ✅ Log de datos extraídos (canal, usuario, mensaje)
- ✅ Log detallado de cada paso del procesamiento
- ✅ Emojis para fácil identificación en logs

### 3. Endpoints de Diagnóstico Nuevos

#### `/webhooks/stream/test` (POST)
- ✅ Sin verificación de firma
- ✅ Acepta cualquier payload
- ✅ Logs completos de headers y body
- ✅ Ideal para testing inicial

#### `/webhooks/stream/health` (GET)
- ✅ Health check simple
- ✅ Lista todos los endpoints disponibles
- ✅ No requiere payload

#### `/webhooks/stream/debug` (POST)
- ✅ Logs TODOS los headers y body raw
- ✅ Sin procesamiento, solo logging
- ✅ Útil para ver exactamente qué envía Stream

### 4. Script de Testing
- ✅ `test_stream_webhook.py` para probar conectividad
- ✅ Prueba todos los endpoints nuevos
- ✅ Simula payloads de Stream
- ✅ Reporta resultados detallados

## 🔧 URLs de Testing

### Endpoints Disponibles:
```
GET  https://gymapi-eh6m.onrender.com/api/v1/webhooks/stream/health
POST https://gymapi-eh6m.onrender.com/api/v1/webhooks/stream/test
POST https://gymapi-eh6m.onrender.com/api/v1/webhooks/stream/debug
POST https://gymapi-eh6m.onrender.com/api/v1/webhooks/stream/new-message (principal)
```

### Configuración en Stream Dashboard:
```
URL: https://gymapi-eh6m.onrender.com/api/v1/webhooks/stream/new-message
```

## 🔍 Diagnóstico Step-by-Step

### Paso 1: Verificar Conectividad
```bash
# Ejecutar script de testing
python test_stream_webhook.py
```

### Paso 2: Revisar Logs del Servidor
Buscar en logs por estos patrones:
- `🔔 ========== WEBHOOK STREAM NEW MESSAGE RECIBIDO ==========`
- `🔐 Iniciando verificación de firma de webhook Stream`
- `🧪 ========== TEST WEBHOOK STREAM ==========`

### Paso 3: Probar Endpoint Manualmente
```bash
# Test básico
curl -X POST https://gymapi-eh6m.onrender.com/api/v1/webhooks/stream/test \
  -H "Content-Type: application/json" \
  -d '{"test": true}'

# Health check
curl https://gymapi-eh6m.onrender.com/api/v1/webhooks/stream/health
```

## 🚨 Posibles Problemas y Soluciones

### 1. No hay logs en absoluto
**Problema**: Stream no está enviando webhooks
**Solución**: 
- Verificar configuración en Stream Dashboard
- Probar endpoints de test manualmente
- Verificar que URL esté accesible desde internet

### 2. Logs de verificación de firma fallan
**Problema**: Signature inválida
**Solución**:
- Verificar STREAM_API_SECRET en variables de entorno
- Comparar con configuración en Stream Dashboard
- Usar endpoint `/stream/debug` para ver signature enviada

### 3. Logs llegan pero fallan después de verificación
**Problema**: Payload inválido o error en procesamiento
**Solución**:
- Revisar estructura del payload en logs
- Verificar base de datos y modelos
- Usar endpoint `/stream/test` para simular payloads

### 4. Endpoint no accesible
**Problema**: 404 o timeout
**Solución**:
- Verificar que FastAPI esté funcionando
- Confirmar routing en `/app/api/v1/api.py`
- Verificar que Render esté desplegado correctamente

## 📋 Checklist de Verificación

- [ ] Ejecutar `python test_stream_webhook.py`
- [ ] Verificar health check: `GET /webhooks/stream/health`
- [ ] Probar endpoint test: `POST /webhooks/stream/test`
- [ ] Revisar logs del servidor en Render
- [ ] Verificar configuración en Stream Dashboard
- [ ] Enviar mensaje real en la app y buscar logs
- [ ] Confirmar que STREAM_API_SECRET está configurado

## 🎯 Próximos Pasos

1. **Ejecutar pruebas**: Usar el script de testing
2. **Revisar logs**: Buscar los patrones específicos implementados
3. **Identificar problema**: Determinar en qué paso falla
4. **Ajustar configuración**: Según lo que muestren los logs

## 📝 Notas

- Todos los logs tienen emojis para fácil identificación
- La verificación de firma es muy detallada
- Los endpoints de diagnóstico no requieren autenticación
- El script de testing cubre todos los casos de uso

¡Con esta implementación deberías poder ver exactamente qué está pasando con los webhooks de Stream!