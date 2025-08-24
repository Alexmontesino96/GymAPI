# Variables de Entorno Requeridas - GymAPI

## 🔒 Variables Críticas de Seguridad

### ⚠️ STRIPE (BILLING)
```bash
# CRÍTICO: Estas claves nunca deben estar en el código fuente
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
STRIPE_SECRET_KEY=sk_test_your_secret_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here
```

### 🔐 AUTH0
```bash
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_API_AUDIENCE=https://your-api-audience
AUTH0_CLIENT_ID=your_client_id
AUTH0_CLIENT_SECRET=your_client_secret
AUTH0_WEBHOOK_SECRET=your_auth0_webhook_secret
```

## 📋 Variables Completas

### Configuración Básica
```bash
SECRET_KEY=your_secret_key_here
DEBUG_MODE=False
PROJECT_NAME=GymAPI
API_V1_STR=/api/v1
```

### Base de Datos
```bash
DATABASE_URL=postgresql://user:password@localhost/gymapi
```

### Auth0 Management API
```bash
AUTH0_MGMT_CLIENT_ID=your_mgmt_client_id
AUTH0_MGMT_CLIENT_SECRET=your_mgmt_client_secret
```

### Redis
```bash
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
```

### Stream.io (Chat)
```bash
STREAM_API_KEY=your_stream_api_key
STREAM_API_SECRET=your_stream_api_secret
STREAM_WEBHOOK_SECRET=your_stream_webhook_secret
```

### OneSignal (Notificaciones)
```bash
ONESIGNAL_APP_ID=your_onesignal_app_id
ONESIGNAL_REST_API_KEY=your_onesignal_rest_api_key
```

### AWS
```bash
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
SQS_QUEUE_URL=https://sqs.region.amazonaws.com/account/queue-name
```

### CORS y Redirects
```bash
BACKEND_CORS_ORIGINS=["http://localhost:3000","https://yourdomain.com"]
AUTH0_ALLOWED_REDIRECT_URIS=["http://localhost:3000","https://yourdomain.com"]
```

### Superusuario Inicial
```bash
FIRST_SUPERUSER=admin@example.com
FIRST_SUPERUSER_PASSWORD=secure_password_here
```

### Worker
```bash
WORKER_API_KEY=your_worker_api_key
```

## 🚨 Notas de Seguridad

### Variables que NUNCA deben estar en el código:
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET` ⚠️ **CORREGIDO** - Antes estaba hardcodeado
- `AUTH0_CLIENT_SECRET`
- `AUTH0_WEBHOOK_SECRET`
- `STREAM_API_SECRET`

### Configuración en Producción:
1. Usar variables de entorno del proveedor cloud
2. Rotar secretos regularmente
3. Usar diferentes valores para test/staging/production
4. Nunca loggear valores completos de secretos

### Verificación de Configuración:
```bash
# Ejecutar script de verificación
python scripts/verify_stripe_config.py
```

## 📝 Ejemplo de .env local:
```bash
# Copiar este contenido a un archivo .env en la raíz del proyecto
# y reemplazar los valores placeholder con los reales

SECRET_KEY=tu_secret_key_local
DEBUG_MODE=True
DATABASE_URL=postgresql://user:pass@localhost/gymapi_dev
AUTH0_DOMAIN=dev-tenant.auth0.com
# ... resto de variables
``` 