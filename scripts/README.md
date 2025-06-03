# Scripts de Mantenimiento - GymAPI

Este directorio contiene scripts de mantenimiento y migración para la aplicación GymAPI.

## Scripts Disponibles

### `generate_qr_for_existing_users.py`

Script para generar códigos QR para usuarios existentes que fueron creados antes de implementar el sistema de QR.

**Propósito:**
- Genera códigos QR únicos para usuarios existentes sin QR
- Verifica la unicidad de todos los códigos QR
- Proporciona estadísticas del proceso

**Uso:**
```bash
# Ejecutar desde el directorio raíz del proyecto
python scripts/generate_qr_for_existing_users.py
```

**Características:**
- ✅ Genera QRs únicos con formato `U{user_id}_{hash}`
- ✅ Verifica duplicados y regenera si es necesario
- ✅ Manejo de errores robusto
- ✅ Logging detallado del proceso
- ✅ Estadísticas antes y después del proceso
- ✅ Rollback automático en caso de errores críticos

**Ejemplo de salida:**
```
2024-01-15 10:30:00 - INFO - === Script de generación de códigos QR para usuarios existentes ===
2024-01-15 10:30:00 - INFO - 📊 Estadísticas de códigos QR:
2024-01-15 10:30:00 - INFO -   Total de usuarios: 150
2024-01-15 10:30:00 - INFO -   Usuarios con QR: 0
2024-01-15 10:30:00 - INFO -   Usuarios sin QR: 150
2024-01-15 10:30:01 - INFO - Encontrados 150 usuarios sin código QR
2024-01-15 10:30:05 - INFO - ✅ Códigos QR generados exitosamente para 150 usuarios
2024-01-15 10:30:05 - INFO - ✅ Todos los códigos QR son únicos
2024-01-15 10:30:05 - INFO - 🎉 Todos los usuarios tienen ahora código QR asignado
```

**Cuándo ejecutar:**
- **Una sola vez** después de implementar el sistema de QR
- Solo si tienes usuarios existentes en la base de datos
- Antes de que los usuarios empiecen a usar el sistema de check-in por QR

**Nota importante:**
Este script debe ejecutarse **solo una vez** por base de datos. Los nuevos usuarios que se registren después de implementar el sistema de QR ya tendrán su código generado automáticamente.

## Requisitos

- Python 3.8+
- Dependencias del proyecto instaladas
- Acceso a la base de datos configurada
- Variables de entorno configuradas correctamente

## Consideraciones

- **Backup:** Se recomienda hacer backup de la base de datos antes de ejecutar scripts de migración
- **Entorno:** Ejecutar primero en entorno de desarrollo/staging antes de producción
- **Monitoreo:** Revisar los logs para asegurar que el proceso se completó correctamente 