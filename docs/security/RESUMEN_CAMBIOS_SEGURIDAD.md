# Resumen de Cambios de Seguridad (Agosto 2025)

Este documento resume las mejoras de seguridad aplicadas recientemente a la API.

## 1) Sanitización de Logs
- Se enmascaran encabezados sensibles (Authorization, cookies, secretos de webhooks) en `app/main.py`.
- En `app/core/auth0_fastapi.py` los tokens solo se registran en DEBUG y de forma enmascarada (últimos 6 caracteres).
- Se eliminaron/maskearon logs que contenían valores de `DATABASE_URL` y `REDIS_URL` en `app/core/config.py`.
- El objetivo es evitar la exposición de tokens, credenciales o PII en archivos de log.

## 2) CORS Restringido
- Se reemplazó el comodín `*` por una lista explícita de orígenes permitidos: `settings.BACKEND_CORS_ORIGINS`.
- Nota: si `allow_credentials=True`, los navegadores no aceptan `*`; ahora solo se aceptan orígenes whitelisted.

## 3) Niveles de Log por Entorno
- El nivel de log ahora depende de `DEBUG_MODE` (INFO en producción, DEBUG en desarrollo) vía `app/core/logging_config.py`.
- El logging verboso de cabeceras y tokens queda restringido a entornos de desarrollo.

## 4) Rate Limiting más Robusto
- Se endureció el cálculo de IP cliente en `app/middleware/rate_limit.py`:
  - Por defecto se usa la IP del socket (ASGI `request.client.host`).
  - Solo si `TRUST_PROXY_HEADERS=True` se usan cabeceras `X-Forwarded-For`/`X-Real-IP` (escenario detrás de proxy confiable).
- Nueva variable de entorno: `TRUST_PROXY_HEADERS` (por defecto False).

## 5) Encabezados de Seguridad
- Nuevo middleware `SecurityHeadersMiddleware` añade por defecto:
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Content-Security-Policy: default-src 'none'; img-src https: data:; connect-src https:; frame-ancestors 'none'`
- Estos encabezados fortalecen la protección frente a clickjacking, MIME sniffing, y controlan el contexto de carga.

## 6) Refresh de JWKS (Auth0)
- `app/core/auth0_fastapi.py` ahora:
  - Refresca las JWKS con TTL (~10 minutos).
  - Fuerza un refresh cuando no encuentra la `kid` (posible rotación de clave en Auth0) y reintenta la validación una vez.
- Beneficio: evita fallas de autenticación ante rotación de claves sin reiniciar el servicio.

## 7) Swagger/Docs en Producción
- En producción (`DEBUG_MODE=False`) se deshabilitan `docs_url` y `redoc_url` para no exponer documentación pública.
- En desarrollo, las docs permanecen disponibles.

## 8) Invalicación de Caché Extendida
- `app/services/cache_service.py` ahora invalida también claves `user_gym_membership_obj:*`.
- Evita inconsistencias tras cambios de membresía/rol.

---

## Variables de Entorno Relevantes
- `DEBUG_MODE`: `true/false`. Controla nivel de logs y exposición de docs.
- `BACKEND_CORS_ORIGINS`: Lista de orígenes permitidos (JSON o separado por comas).
- `TRUST_PROXY_HEADERS`: `true/false`. Confía en cabeceras de proxy para determinar IP cliente.

## Recomendaciones de Despliegue
- Asegurar HTTPS a nivel de proxy/CDN; HSTS se aplica desde la app.
- Si hay proxy inverso, habilitar `--proxy-headers` en Uvicorn y establecer `TRUST_PROXY_HEADERS=true` solo si el proxy es de confianza.
- Mantener `BACKEND_CORS_ORIGINS` actualizado con las URLs reales del frontend (prod/staging/dev).

## Checklist de Verificación Rápida
- [ ] Solicitud a cualquier endpoint muestra encabezados de seguridad en la respuesta.
- [ ] En producción, `/api/v1/docs` y `/api/v1/redoc` no están disponibles.
- [ ] Logs en producción no contienen tokens/credenciales ni cabeceras sensibles completas.
- [ ] Los orígenes no permitidos fallan CORS correctamente.
- [ ] Validación de JWT sigue funcionando tras una rotación de claves en Auth0 sin reinicios.

## Commits Relacionados
- `security: sanitize sensitive logs, tighten CORS, set prod log levels, harden rate-limit IP source, extend cache invalidation`
- `security: add security headers middleware, disable docs in prod, implement JWKS refresh with TTL and KID-miss reload`

