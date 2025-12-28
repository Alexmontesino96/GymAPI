# 🚨 FIX RÁPIDO - Error 404 Activity Feed

## ❌ PROBLEMA
```
GET /api/v1/activity-feed/realtime → 404 Not Found
```

## 🔴 CAUSA
El módulo `activity_feed` NO está habilitado para gym_id=4

## ✅ SOLUCIÓN INMEDIATA PARA FRONTEND

### Opción 1: Usar `/api/v1/events` (RECOMENDADO)
```javascript
// CAMBIAR ESTO:
const response = await fetch('/api/v1/activity-feed/realtime', {
    headers: { 'Authorization': `Bearer ${token}`, 'X-Gym-Id': '4' }
});

// POR ESTO:
const response = await fetch('/api/v1/events?limit=10&status=active', {
    headers: { 'Authorization': `Bearer ${token}`, 'X-Gym-Id': '4' }
});

// Transformar la respuesta
const activityData = {
    status: 'success',
    data: {
        active_users: response.events?.length || 0,
        recent_activities: response.events?.map(e => ({
            type: 'event',
            message: `${e.participants_count} en ${e.name}`,
            time: e.start_date
        })) || []
    }
};
```

### Opción 2: Usar Dashboard del Usuario
```javascript
const response = await fetch('/api/v1/users/dashboard', {
    headers: { 'Authorization': `Bearer ${token}`, 'X-Gym-Id': '4' }
});
```

### Opción 3: Desactivar Temporalmente
```javascript
// En tu componente
const useActivityFeed = () => {
    const [data, setData] = useState(null);

    useEffect(() => {
        // TEMPORAL: Mientras se habilita el módulo
        setData({
            status: 'success',
            data: {
                active_users: 0,
                recent_activities: [],
                message: 'Feed temporalmente no disponible'
            }
        });

        // TODO: Reactivar cuando el módulo esté habilitado
        // fetchActivityFeed().then(setData);
    }, []);

    return data;
};
```

## 📝 PARA EL BACKEND TEAM
El módulo `activity_feed` necesita ser habilitado en la BD para gym_id=4

```sql
-- Ejecutar en producción
UPDATE gym_module
SET is_active = true
WHERE gym_id = 4
AND module_id = (SELECT id FROM module WHERE code = 'activity_feed');
```

## 🎯 RESUMEN
1. **AHORA**: Usar `/api/v1/events` en lugar de `/api/v1/activity-feed/realtime`
2. **DESPUÉS**: Backend habilitará el módulo
3. **FUTURO**: Volver al endpoint original cuando esté habilitado

---
*Fix temporal mientras se habilita el módulo activity_feed*