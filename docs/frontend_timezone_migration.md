# Migración Frontend: Sistema de Zonas Horarias

## 📋 Resumen de Cambios

Hemos implementado un sistema de zonas horarias que permite que cada gimnasio tenga su propia zona horaria. Esto afecta principalmente cómo se manejan los horarios de las sesiones.

## 🆕 Nuevos Endpoints Disponibles

### 1. Sesiones con Timezone (Básico)
```http
GET /api/v1/schedule/sessions-with-timezone
```

### 2. Sesiones por Rango de Fechas con Timezone  
```http
GET /api/v1/schedule/date-range-with-timezone?start_date=2025-07-27&end_date=2025-08-03
```

## 📊 Cambios en los Datos

### ✅ Datos que NO cambiaron
- Los endpoints existentes siguen funcionando igual
- `start_time` y `end_time` siguen siendo datetime strings
- Estructura básica de las sesiones se mantiene

### 🆕 Nuevos Campos Disponibles

#### En Gimnasios:
```json
{
  "id": 4,
  "name": "Mi Gimnasio",
  "timezone": "America/Mexico_City",  // 🆕 NUEVO
  // ... otros campos existentes
}
```

#### En Sesiones (nuevos endpoints):
```json
{
  "id": 123,
  "start_time": "2025-07-27T14:00:00",      // Hora local del gym (SIN timezone)
  "end_time": "2025-07-27T15:00:00",
  "gym_timezone": "America/Mexico_City",     // 🆕 NUEVO
  "time_info": {                             // 🆕 NUEVO
    "local_time": "2025-07-27T14:00:00",
    "gym_timezone": "America/Mexico_City",
    "iso_with_timezone": "2025-07-27T14:00:00-06:00",
    "utc_time": "2025-07-27T20:00:00+00:00"
  },
  // ... todos los campos existentes de sesión
}
```

## 🔄 Migración del Frontend

### Opción 1: Sin Cambios (Recomendado inicialmente)
```javascript
// Continuar usando endpoints existentes
const sessions = await fetch('/api/v1/schedule/sessions');
const dateRangeSessions = await fetch('/api/v1/schedule/date-range?start_date=2025-07-27&end_date=2025-08-03');

// Todo funciona igual que antes
```

### Opción 2: Migración Gradual (Recomendado para futuro)
```javascript
// Nuevos endpoints con información de timezone
const sessionsWithTz = await fetch('/api/v1/schedule/sessions-with-timezone');
const dateRangeWithTz = await fetch('/api/v1/schedule/date-range-with-timezone?start_date=2025-07-27&end_date=2025-08-03');
```

## 🌍 Manejo de Timezone en Frontend

### Conversión Automática a Hora Local del Usuario

```javascript
// Ejemplo de conversión usando la nueva información
function convertSessionToUserTime(session) {
  // Usar el campo iso_with_timezone que ya incluye la zona horaria
  const sessionDate = new Date(session.time_info.iso_with_timezone);
  
  // Esto automáticamente se convierte a la zona horaria del usuario
  return sessionDate.toLocaleString();
}

// Ejemplo de uso
const session = {
  start_time: "2025-07-27T14:00:00",
  gym_timezone: "America/Mexico_City",
  time_info: {
    iso_with_timezone: "2025-07-27T14:00:00-06:00"
  }
};

console.log(convertSessionToUserTime(session)); 
// Si el usuario está en España: "27/7/2025, 22:00:00"
// Si el usuario está en México: "27/7/2025, 14:00:00"
```

### Mostrar Zona Horaria del Gimnasio

```javascript
function formatSessionTime(session) {
  const userTime = new Date(session.time_info.iso_with_timezone);
  
  return {
    userLocalTime: userTime.toLocaleString(),
    gymLocalTime: session.start_time,
    gymTimezone: session.gym_timezone,
    isUserInSameTimezone: session.gym_timezone === Intl.DateTimeFormat().resolvedOptions().timeZone
  };
}

// Ejemplo de UI
function SessionCard({ session }) {
  const timeInfo = formatSessionTime(session);
  
  return (
    <div>
      <h3>{session.class_name}</h3>
      <p>Tu hora local: {timeInfo.userLocalTime}</p>
      {!timeInfo.isUserInSameTimezone && (
        <p>Hora del gym: {timeInfo.gymLocalTime} ({timeInfo.gymTimezone})</p>
      )}
    </div>
  );
}
```

## 📝 Ejemplos de Integración

### React/TypeScript
```typescript
interface SessionWithTimezone {
  id: number;
  start_time: string;
  end_time: string;
  gym_timezone: string;
  time_info: {
    local_time: string;
    gym_timezone: string;
    iso_with_timezone: string;
    utc_time: string;
  };
  // ... otros campos
}

function useSessionsWithTimezone(startDate: string, endDate: string) {
  return useQuery({
    queryKey: ['sessions', 'timezone', startDate, endDate],
    queryFn: () => 
      fetch(`/api/v1/schedule/date-range-with-timezone?start_date=${startDate}&end_date=${endDate}`)
        .then(res => res.json()) as Promise<SessionWithTimezone[]>
  });
}
```

### Vue/Nuxt
```javascript
// composables/useTimezone.js
export function useTimezone() {
  const convertToUserTime = (session) => {
    return new Date(session.time_info.iso_with_timezone);
  };
  
  const formatTimeForDisplay = (session) => {
    const userTime = convertToUserTime(session);
    const gymTime = session.start_time;
    
    return {
      user: userTime.toLocaleString(),
      gym: `${gymTime} (${session.gym_timezone})`
    };
  };
  
  return {
    convertToUserTime,
    formatTimeForDisplay
  };
}
```

## ⚠️ Consideraciones Importantes

### 1. Horario de Verano
- El sistema maneja automáticamente los cambios de horario de verano
- Las conversiones son siempre precisas

### 2. Performance
- Los nuevos endpoints tienen overhead mínimo
- La información de timezone se calcula una vez por sesión

### 3. Retrocompatibilidad
- **Todos los endpoints existentes siguen funcionando igual**
- No hay breaking changes en la API actual
- Migración puede ser gradual

## 🚀 Plan de Migración Recomendado

### Fase 1 (Inmediata): Sin Cambios
- Continuar usando endpoints existentes
- No requiere cambios en frontend

### Fase 2 (Opcional): Experimentar
- Probar nuevos endpoints en desarrollo
- Implementar conversión de timezone en componentes específicos

### Fase 3 (Futuro): Migración Completa
- Migrar gradualmente a endpoints con timezone
- Mejorar UX mostrando horarios precisos

## ❓ Preguntas Frecuentes

**Q: ¿Tengo que cambiar mi código existente?**
A: No, todos los endpoints existentes siguen funcionando igual.

**Q: ¿Cómo sé qué zona horaria usar?**
A: El gimnasio actual incluye el campo `timezone` en su respuesta.

**Q: ¿Qué pasa si el usuario está en diferente zona horaria?**
A: Los nuevos endpoints proporcionan toda la información necesaria para conversión automática.

**Q: ¿Es más lento?**
A: El overhead es mínimo, las conversiones son muy rápidas.

## 🆘 Soporte

Si tienes dudas durante la migración:
1. Los endpoints antiguos siguen funcionando
2. Los nuevos endpoints son opcionales
3. Puedes migrar gradualmente
4. Contacta al equipo backend para cualquier duda