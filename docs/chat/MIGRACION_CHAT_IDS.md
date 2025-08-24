# Migración de auth0_user_id a user_id en el módulo de Chat - COMPLETADA

Este documento detalla los cambios realizados para migrar el módulo de chat de usar `auth0_user_id` (string) a usar `user_id` (entero) como identificador principal de usuarios.

## Motivación

La migración de `auth0_user_id` a `user_id` se realiza por varias razones:

1. **Abstracción del proveedor de autenticación**: Desacoplar la lógica de negocio del proveedor específico (Auth0)
2. **Consistencia en la base de datos**: Usar los mismos IDs internos en toda la aplicación
3. **Rendimiento**: Los IDs numéricos enteros tienen mejor rendimiento en consultas SQL que los strings largos
4. **Mantenibilidad**: Facilitar futuros cambios en el sistema de autenticación

## Cambios realizados

### 1. Estructura de base de datos

Se modificó la tabla `chat_members` para:
- Eliminar la columna `auth0_user_id`
- Eliminar el índice asociado `ix_chat_members_auth0_user_id`
- Asegurar que `user_id` sea una clave foránea apropiada referenciando a `user.id`

### 2. Servicio de Chat

Se actualizaron varios métodos en `app/services/chat.py`:

- `get_channel_members`: Ahora devuelve una lista de IDs internos (enteros) en lugar de IDs de Stream (strings)
- `add_user_to_channel` y `remove_user_from_channel`: Eliminadas las referencias redundantes a `auth0_user_id`
- Se mantiene la conversión de IDs internos a IDs de Stream solo para la comunicación con Stream Chat

### 3. Endpoint de Webhooks

En `app/api/v1/endpoints/webhooks/stream_webhooks.py`:

- Se actualizó para recibir IDs de Stream pero usar IDs internos para el procesamiento de notificaciones
- Se agregó la conversión de ID de Stream (auth0_id) a ID interno en el procesador de webhooks

### 4. Scripts de prueba

Se actualizó el script de prueba `scripts/test_chat_webhook.py` para:

- Usar IDs internos para crear chats directos
- Mantener la lógica necesaria para convertir entre IDs internos y IDs de Stream
- Actualizar la forma de enviar mensajes de prueba y simular webhooks

## Estado actual del sistema

✅ **La migración ha sido completada exitosamente (COMPLETADA)**

Actualmente:

- Toda la lógica interna usa IDs enteros (`user_id`)
- La comunicación con Stream sigue usando strings sanitizados (basados en `auth0_id`)
- La conversión entre ambos tipos ocurre en los límites del sistema (endpoints de API y webhooks)
- Los datos en la base de datos son consistentes y usan únicamente `user_id`
- Se han eliminado todos los scripts de migración temporales
- Los eventos se han limpiado de la base de datos y se pueden crear nuevos con la estructura actualizada

## Consideraciones para el futuro

En caso de cambiar el proveedor de autenticación en el futuro, solo será necesario:

1. Actualizar la lógica de obtención del ID de autenticación externo (ahora es `auth0_id`)
2. Mantener la función adaptadora `_get_stream_id_for_user` en `chat_service.py` para que siga funcionando correctamente

La migración ha simplificado significativamente la arquitectura del sistema y reducido la dependencia de Auth0. 