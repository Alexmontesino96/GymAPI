# Sistema de Notificaciones de Nutrición con Amazon SQS

## Resumen

Este documento describe la arquitectura de notificaciones de nutrición basada en Amazon SQS, diseñada para manejar alto volumen de notificaciones de forma escalable y resiliente.

## Arquitectura

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   APScheduler   │───>│  SQS Producer   │───>│   SQS Queue     │
│   (Jobs)        │    │  (enqueue)      │    │   (messages)    │
└─────────────────┘    └─────────────────┘    └────────┬────────┘
                                                       │
                       ┌───────────────────────────────┘
                       │
                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   SQS Worker    │───>│  Notification   │───>│   OneSignal     │
│   (consumer)    │    │  Service        │    │   (push)        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                       │
                       ▼
               ┌─────────────────┐
               │  Dead Letter    │
               │  Queue (DLQ)    │
               └─────────────────┘
```

## Componentes

### 1. Productor (`app/services/sqs_notification_service.py`)

Encola mensajes de notificación en SQS:

```python
from app.services.sqs_notification_service import sqs_notification_service

# Encolar recordatorio individual
sqs_notification_service.enqueue_meal_reminder(
    user_id=123,
    gym_id=1,
    meal_type="lunch",
    meal_name="Ensalada César",
    plan_title="Plan Saludable"
)

# Encolar en batch (más eficiente)
messages = [msg1, msg2, msg3, ...]
results = sqs_notification_service.enqueue_batch(messages)
```

### 2. Consumidor/Worker (`app/workers/nutrition_notification_worker.py`)

Procesa mensajes de la cola y envía notificaciones:

```bash
# Ejecutar un worker
python -m app.workers.nutrition_notification_worker

# Ejecutar múltiples workers en paralelo
python -m app.workers.nutrition_notification_worker --workers 3

# Opciones
--workers, -w    Número de workers (default: 1)
--batch-size, -b Mensajes por batch (default: 10, max: 10)
--single, -s     Ejecutar un solo worker sin pool
```

### 3. Jobs del Scheduler (`app/core/scheduler.py`)

Los jobs de APScheduler usan automáticamente SQS si está configurado:

- **Desayuno**: 6:00, 7:00, 8:00, 9:00, 10:00
- **Almuerzo**: 12:00, 13:00, 14:00, 15:00
- **Cena**: 19:00, 20:00, 21:00, 22:00

### 4. Servicio de Notificaciones (`app/services/nutrition_notification_service.py`)

Integra SQS con fallback a envío directo:

```python
from app.services.nutrition_notification_service import NutritionNotificationService

service = NutritionNotificationService(use_sqs=True)

# Envia via SQS si está disponible, si no envía directamente
service.send_meal_reminder(
    db=db,
    user_id=123,
    meal_type="breakfast",
    meal_name="Avena con frutas",
    plan_title="Plan Energético",
    gym_id=1
)

# Forzar envío directo (sin SQS)
service.send_meal_reminder(..., force_direct=True)

# Batch enqueue para el scheduler
service.batch_enqueue_meal_reminders(
    db=db,
    gym_id=1,
    meal_type="lunch",
    scheduled_time="13:00"
)
```

## Configuración

### 1. Variables de Entorno

```bash
# AWS Credentials
AWS_ACCESS_KEY_ID=tu_access_key
AWS_SECRET_ACCESS_KEY=tu_secret_key
AWS_REGION=us-east-1

# SQS Queue URLs
SQS_NUTRITION_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789/gymapi-nutrition-notifications
SQS_NUTRITION_DLQ_URL=https://sqs.us-east-1.amazonaws.com/123456789/gymapi-nutrition-notifications-dlq
```

### 2. Crear Colas en AWS

```bash
# Script automático
python scripts/setup_sqs_queues.py

# Con opciones
python scripts/setup_sqs_queues.py --region us-east-1 --test

# Personalizar nombres
python scripts/setup_sqs_queues.py \
    --queue-name my-gym-notifications \
    --dlq-name my-gym-notifications-dlq
```

### 3. Configuración de Colas

**Cola Principal:**
- `VisibilityTimeout`: 60s (tiempo para procesar)
- `MessageRetentionPeriod`: 4 días
- `ReceiveMessageWaitTimeSeconds`: 20s (long polling)
- `RedrivePolicy`: 3 intentos antes de ir a DLQ

**Dead Letter Queue:**
- `MessageRetentionPeriod`: 14 días
- Para análisis de mensajes fallidos

## Deployment

### Desarrollo Local (sin SQS)

SQS es opcional. Sin configuración, el sistema envía directamente:

```python
# El servicio detecta automáticamente si SQS está disponible
notification_service = NutritionNotificationService()
# use_sqs será False si no hay credenciales
```

### Producción (con SQS)

1. **Configurar credenciales AWS**
2. **Ejecutar script de setup**: `python scripts/setup_sqs_queues.py`
3. **Agregar variables a .env**
4. **Iniciar workers**:

```bash
# Docker Compose (recomendado)
services:
  worker:
    command: python -m app.workers.nutrition_notification_worker --workers 3

# Supervisor
[program:nutrition-worker]
command=python -m app.workers.nutrition_notification_worker --workers 3
directory=/app
autostart=true
autorestart=true

# systemd
[Service]
ExecStart=/usr/bin/python -m app.workers.nutrition_notification_worker --workers 3
Restart=always
```

## Monitoreo

### Estadísticas de Cola

```python
from app.services.sqs_notification_service import sqs_notification_service

stats = sqs_notification_service.get_queue_stats()
# {
#     "enabled": True,
#     "queue_url": "...",
#     "messages_available": 15,
#     "messages_in_flight": 3,
#     "messages_delayed": 0
# }
```

### Métricas en Redis

```python
from app.services.nutrition_notification_service import get_notification_analytics

analytics = get_notification_analytics(gym_id=1, days=7)
# Incluye: queued, sent, failed por tipo de comida
```

### CloudWatch

Métricas automáticas de SQS:
- `NumberOfMessagesReceived`
- `NumberOfMessagesSent`
- `ApproximateNumberOfMessagesVisible`
- `ApproximateAgeOfOldestMessage`

## Flujo de Datos

```
1. Scheduler ejecuta job (cada hora)
   │
2. batch_enqueue_meal_reminders()
   │
3. ¿SQS habilitado?
   ├─ SÍ: Encolar en SQS (batch de 10)
   │      │
   │      ▼
   │      Worker recibe mensajes (long polling)
   │      │
   │      ▼
   │      Procesa y envía via OneSignal
   │      │
   │      ├─ Éxito: Eliminar mensaje
   │      └─ Fallo: Reintentar (max 3 veces)
   │               └─ Después de 3 fallos: Mover a DLQ
   │
   └─ NO: Envío directo via OneSignal
```

## Manejo de Errores

### Reintentos Automáticos

SQS reintenta automáticamente:
1. Primer intento: inmediato
2. Segundo intento: después de 60s (visibility timeout)
3. Tercer intento: después de 60s más
4. Si falla: mensaje va a DLQ

### Dead Letter Queue

Mensajes en DLQ requieren análisis manual:

```bash
# Ver mensajes en DLQ
aws sqs receive-message \
    --queue-url $SQS_NUTRITION_DLQ_URL \
    --max-number-of-messages 10
```

### Fallback a Envío Directo

Si SQS falla temporalmente:

```python
# El servicio hace fallback automático
if not sqs_service.enqueue_meal_reminder(...):
    # Fallo SQS, enviando directamente
    notification_service.send_to_users(...)
```

## Beneficios vs Envío Directo

| Aspecto | Envío Directo | Con SQS |
|---------|--------------|---------|
| Latencia del scheduler | Alta | Baja |
| Escalabilidad | Limitada | Horizontal |
| Resiliencia | Baja | Alta |
| Reintentos | Manual | Automático |
| Monitoreo | Básico | CloudWatch |
| Costo | Gratis | ~$0.40/millón |

## Costos Estimados

- **SQS Standard**: $0.40 por millón de requests
- **Ejemplo**: 10,000 usuarios × 3 comidas × 30 días = 900,000 mensajes/mes ≈ $0.36/mes

## Troubleshooting

### Worker no procesa mensajes

```bash
# Verificar credenciales
aws sts get-caller-identity

# Verificar cola
aws sqs get-queue-attributes \
    --queue-url $SQS_NUTRITION_QUEUE_URL \
    --attribute-names All
```

### Mensajes acumulándose en DLQ

```bash
# Ver razón de fallo en el mensaje
aws sqs receive-message \
    --queue-url $SQS_NUTRITION_DLQ_URL \
    --attribute-names All \
    --message-attribute-names All
```

### SQS no se habilita

```python
# Verificar configuración
import os
print(os.environ.get('AWS_ACCESS_KEY_ID'))
print(os.environ.get('SQS_NUTRITION_QUEUE_URL'))

# Verificar servicio
from app.services.sqs_notification_service import sqs_notification_service
print(f"SQS enabled: {sqs_notification_service.enabled}")
```
