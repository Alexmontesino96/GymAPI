# 📚 GymAPI - Índice de Documentación

## Estructura de la Documentación

Esta documentación está organizada por categorías para facilitar la navegación y comprensión del sistema.

---

## 🏗️ Architecture
*Arquitectura del sistema, patrones de diseño y decisiones técnicas*

- [`api_permissions.md`](architecture/api_permissions.md) - Sistema de permisos y roles de la API
- [`module_documentation.md`](architecture/module_documentation.md) - Documentación de módulos del sistema
- [`SOLUCION_GYM_ID.md`](architecture/SOLUCION_GYM_ID.md) - Solución multi-tenant con gym_id
- [`AGENTS.md`](architecture/AGENTS.md) - Sistema de agentes y workers

## 💬 Chat
*Sistema de chat en tiempo real con Stream*

- [`CHAT_DOCUMENTATION_SWIFT.md`](chat/CHAT_DOCUMENTATION_SWIFT.md) - Integración con Swift/iOS
- [`FLUJOS_Y_ARGUMENTOS_CHAT.md`](chat/FLUJOS_Y_ARGUMENTOS_CHAT.md) - Flujos de chat y argumentos
- [`FUNCIONAMIENTO_AUTENTICACION_CHAT.md`](chat/FUNCIONAMIENTO_AUTENTICACION_CHAT.md) - Autenticación en el sistema de chat
- [`PERMISOS_ESPECIFICOS_CHAT.md`](chat/PERMISOS_ESPECIFICOS_CHAT.md) - Permisos y roles en chat
- [`MIGRACION_CHAT_IDS.md`](chat/MIGRACION_CHAT_IDS.md) - Migración de IDs de chat
- [`STREAM_SECURITY_SETUP.md`](chat/STREAM_SECURITY_SETUP.md) - Configuración de seguridad Stream
- [`STREAM_WEBHOOK_DIAGNOSTIC.md`](chat/STREAM_WEBHOOK_DIAGNOSTIC.md) - Diagnóstico de webhooks Stream

## ⚙️ Configuration
*Configuración del sistema y variables de entorno*

- [`environment_variables.md`](configuration/environment_variables.md) - Variables de entorno necesarias
- [`timezone_system.md`](configuration/timezone_system.md) - Sistema de zonas horarias

## 📊 Dashboard
*Sistema de dashboard y analytics*

- [`DASHBOARD_API_ENDPOINTS.md`](dashboard/DASHBOARD_API_ENDPOINTS.md) - Endpoints del dashboard
- [`DASHBOARD_IMPLEMENTATION_DOCS.md`](dashboard/DASHBOARD_IMPLEMENTATION_DOCS.md) - Documentación de implementación
- [`DASHBOARD_IMPLEMENTATION_SUMMARY.md`](dashboard/DASHBOARD_IMPLEMENTATION_SUMMARY.md) - Resumen de implementación
- [`DASHBOARD_SECURITY_REVIEW.md`](dashboard/DASHBOARD_SECURITY_REVIEW.md) - Revisión de seguridad

## 🎨 Frontend
*Guías para integración frontend*

- [`FRONTEND_INDEX.md`](frontend/FRONTEND_INDEX.md) - Índice de documentación frontend
- [`FRONTEND_SUMMARY.md`](frontend/FRONTEND_SUMMARY.md) - Resumen de integración frontend
- [`FRONTEND_LIMITED_CYCLES_GUIDE.md`](frontend/FRONTEND_LIMITED_CYCLES_GUIDE.md) - Guía de ciclos limitados
- [`frontend_timezone_migration.md`](frontend/frontend_timezone_migration.md) - Migración de timezones en frontend

## 🔔 Notifications
*Sistema de notificaciones push*

- [`SMART_NOTIFICATIONS.md`](notifications/SMART_NOTIFICATIONS.md) - Sistema de notificaciones inteligentes
- [`NOTIFICACIONES_BASADAS_EN_ROLES.md`](notifications/NOTIFICACIONES_BASADAS_EN_ROLES.md) - Notificaciones por roles

## 🥗 Nutrition
*Sistema de nutrición y planes alimenticios*

- [`nutrition_system.md`](nutrition/nutrition_system.md) - Sistema de nutrición principal
- [`CONSULTA_MEALS_SISTEMA.md`](nutrition/CONSULTA_MEALS_SISTEMA.md) - Sistema de consulta de comidas
- [`CRITERIOS_INCLUSION_PLANES.md`](nutrition/CRITERIOS_INCLUSION_PLANES.md) - Criterios para planes nutricionales
- [`SISTEMA_HIBRIDO_FLUJO.md`](nutrition/SISTEMA_HIBRIDO_FLUJO.md) - Flujo del sistema híbrido
- [`PUNTOS_CLAVE_SISTEMA.md`](nutrition/PUNTOS_CLAVE_SISTEMA.md) - Puntos clave del sistema
- [`frontend_nutrition_hybrid_guide.md`](nutrition/frontend_nutrition_hybrid_guide.md) - Guía híbrida para frontend

## 💳 Payments
*Integración con Stripe y sistema de pagos*

- [`stripe_multi_tenant_guide.md`](payments/stripe_multi_tenant_guide.md) - Guía multi-tenant para Stripe
- [`stripe_webhook_notifications.md`](payments/stripe_webhook_notifications.md) - Notificaciones webhook de Stripe
- [`payment_success_flow.md`](payments/payment_success_flow.md) - Flujo de pago exitoso
- [`stripe_webhooks_configuration.md`](payments/stripe_webhooks_configuration.md) - Configuración de webhooks
- [`admin_payment_links_guide.md`](payments/admin_payment_links_guide.md) - Guía de links de pago para admin

## 🔒 Security
*Seguridad y mejores prácticas*

- [`SECURITY_FIXES.md`](security/SECURITY_FIXES.md) - Correcciones de seguridad implementadas
- [`RESUMEN_CAMBIOS_SEGURIDAD.md`](security/RESUMEN_CAMBIOS_SEGURIDAD.md) - Resumen de cambios de seguridad
- [`auth/auth0_highest_role_action.md`](auth/auth0_highest_role_action.md) - Acción de rol más alto en Auth0
- [`auth/new_simplified_scopes.md`](auth/new_simplified_scopes.md) - Nuevos scopes simplificados

## 📋 Surveys
*Sistema de encuestas y feedback*

- [`SURVEY_SYSTEM_DOCUMENTATION.md`](surveys/SURVEY_SYSTEM_DOCUMENTATION.md) - **📌 NUEVO** - Documentación completa del sistema de encuestas

---

## 📖 Guías Rápidas

### Para Desarrolladores Backend
1. Comenzar con [`architecture/api_permissions.md`](architecture/api_permissions.md)
2. Revisar [`configuration/environment_variables.md`](configuration/environment_variables.md)
3. Estudiar [`security/SECURITY_FIXES.md`](security/SECURITY_FIXES.md)

### Para Desarrolladores Frontend
1. Leer [`frontend/FRONTEND_INDEX.md`](frontend/FRONTEND_INDEX.md)
2. Revisar integraciones específicas (chat, nutrition, payments)
3. Consultar [`frontend/frontend_timezone_migration.md`](frontend/frontend_timezone_migration.md)

### Para DevOps
1. [`configuration/environment_variables.md`](configuration/environment_variables.md)
2. [`payments/stripe_webhooks_configuration.md`](payments/stripe_webhooks_configuration.md)
3. [`chat/STREAM_WEBHOOK_DIAGNOSTIC.md`](chat/STREAM_WEBHOOK_DIAGNOSTIC.md)

### Para Product Managers
1. [`dashboard/DASHBOARD_IMPLEMENTATION_SUMMARY.md`](dashboard/DASHBOARD_IMPLEMENTATION_SUMMARY.md)
2. [`surveys/SURVEY_SYSTEM_DOCUMENTATION.md`](surveys/SURVEY_SYSTEM_DOCUMENTATION.md)
3. [`nutrition/PUNTOS_CLAVE_SISTEMA.md`](nutrition/PUNTOS_CLAVE_SISTEMA.md)

---

## 🚀 Nuevas Características

### Sistema de Entrenadores Personales (Enero 2024) ⭐
**NUEVO** - Sistema completo para entrenadores personales individuales:
- Workspaces dedicados tipo `personal_trainer`
- UI adaptativa según tipo de workspace
- 5 endpoints nuevos de API
- Registro de trainers con validación en tiempo real
- Terminología dinámica ("clientes" vs "miembros")
- Features condicionales según tipo
- Branding personalizado
- Ejemplos de código completos (React, Vue, Flutter)
- Documentación completa de integración

**Documentación**:
- 📄 [Resumen Completo](../TRAINER_IMPLEMENTATION_COMPLETE.md) - Estado de implementación
- 🆚 [Trainers vs Gyms](trainers/TRAINERS_VS_GYMS.md) - **⭐ NUEVO** - Diferencias y guía completa (~500 líneas)
- 📖 [API Documentation](TRAINER_API_DOCUMENTATION.md) - Referencia de endpoints (~1150 líneas)
- 🎨 [Integration Guide](TRAINER_INTEGRATION_GUIDE.md) - Guía para frontend (~800 líneas)
- 💻 [Ejemplos de Código](../examples/) - Código reutilizable (TypeScript/React)
- 📋 [Implementation Summary](../IMPLEMENTATION_SUMMARY.md) - Resumen técnico

**Scripts**:
- `scripts/setup_trainer.py` - Registrar trainer desde CLI
- `scripts/apply_trainer_migration.py` - Aplicar/revertir migración

**Endpoints**:
```
POST   /api/v1/auth/register-trainer
GET    /api/v1/auth/trainer/check-email/{email}
GET    /api/v1/auth/trainer/validate-subdomain/{subdomain}
GET    /api/v1/context/workspace
GET    /api/v1/context/workspace/stats
```

---

### Sistema de Encuestas (Agosto 2025)
El nuevo sistema de encuestas permite:
- 13 tipos diferentes de preguntas
- Encuestas anónimas o identificadas
- Estadísticas automáticas y exportación
- Sistema de plantillas reutilizables
- Multi-tenant con aislamiento total

Ver documentación completa en [`surveys/SURVEY_SYSTEM_DOCUMENTATION.md`](surveys/SURVEY_SYSTEM_DOCUMENTATION.md)

---

## 📝 Archivos en Raíz

Estos archivos permanecen en la raíz del proyecto por su importancia:

- [`README.md`](/README.md) - README principal del proyecto
- [`CLAUDE.md`](/CLAUDE.md) - Instrucciones para Claude AI
- [`scripts/README.md`](/scripts/README.md) - Documentación de scripts
- [`tests/README.md`](/tests/README.md) - Documentación de tests
- [`TRAINER_IMPLEMENTATION_COMPLETE.md`](/TRAINER_IMPLEMENTATION_COMPLETE.md) - ⭐ **NUEVO** - Implementación de trainers
- [`IMPLEMENTATION_SUMMARY.md`](/IMPLEMENTATION_SUMMARY.md) - Resumen de implementación de trainers
- [`examples/`](/examples/) - Ejemplos de código reutilizable

---

## 🔄 Mantenimiento

### Última Actualización
- **Fecha**: Agosto 24, 2025
- **Versión**: 2.0.0
- **Cambios**: 
  - Reorganización completa de documentación
  - Añadido sistema de encuestas
  - Categorización por temas

### Contribuir
Para añadir nueva documentación:
1. Identificar la categoría apropiada
2. Crear el archivo MD en la carpeta correspondiente
3. Actualizar este índice
4. Seguir el formato establecido

---

*GymAPI - Sistema de Gestión de Gimnasios Multi-tenant*