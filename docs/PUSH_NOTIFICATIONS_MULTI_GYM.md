# Push Notifications - Soporte Multi-Gimnasio

## Descripción General

El sistema de notificaciones ahora incluye contexto del gimnasio que envía la notificación. Esto permite que usuarios que pertenecen a múltiples gimnasios puedan identificar fácilmente de qué gimnasio proviene cada notificación.

## Cambios Implementados

### Backend

Las notificaciones ahora incluyen automáticamente:

1. **`gym_id`** - ID del gimnasio en el campo `data`
2. **`gym_name`** - Nombre del gimnasio en el campo `data` y como prefijo en el título

### Formato de Notificación

```json
{
  "headings": {
    "en": "Fitness Pro: Nueva clase de yoga",
    "es": "Fitness Pro: Nueva clase de yoga"
  },
  "contents": {
    "en": "La clase comienza en 30 minutos",
    "es": "La clase comienza en 30 minutos"
  },
  "data": {
    "gym_id": 1,
    "gym_name": "Fitness Pro",
    "type": "class_reminder",
    ...
  }
}
```

## Implementación en App Móvil

### 1. Configuración Inicial (UNA SOLA VEZ)

#### iOS (Swift)

```swift
import OneSignal

class NotificationManager {

    func initialize(userId: Int) {
        // Inicializar OneSignal
        OneSignal.setAppId("YOUR_ONESIGNAL_APP_ID")

        // ✅ IMPORTANTE: Usar solo el user_id como external_user_id
        // NO usar formato "gym_{id}_user_{id}"
        OneSignal.setExternalUserId("\(userId)")

        // Configurar handler de notificaciones
        OneSignal.setNotificationOpenedHandler { result in
            self.handleNotificationOpened(result)
        }

        OneSignal.setNotificationWillShowInForegroundHandler { notification, completion in
            self.handleNotificationReceived(notification)
            completion(notification)
        }

        print("📱 OneSignal inicializado con external_user_id: \(userId)")
    }
}
```

#### Android (Kotlin)

```kotlin
import com.onesignal.OneSignal

class NotificationManager {

    fun initialize(context: Context, userId: Int) {
        // Inicializar OneSignal
        OneSignal.setAppId("YOUR_ONESIGNAL_APP_ID")
        OneSignal.initWithContext(context)

        // ✅ IMPORTANTE: Usar solo el user_id como external_user_id
        OneSignal.setExternalUserId(userId.toString())

        // Configurar handlers
        OneSignal.setNotificationOpenedHandler { result ->
            handleNotificationOpened(result)
        }

        OneSignal.setNotificationWillShowInForegroundHandler { notificationReceivedEvent ->
            handleNotificationReceived(notificationReceivedEvent)
        }

        Log.d("Notifications", "OneSignal inicializado con user_id: $userId")
    }
}
```

#### React Native

```javascript
import OneSignal from 'react-native-onesignal';

export const initializeNotifications = (userId) => {
  // Inicializar OneSignal
  OneSignal.setAppId('YOUR_ONESIGNAL_APP_ID');

  // ✅ IMPORTANTE: Usar solo el user_id
  OneSignal.setExternalUserId(userId.toString());

  // Handlers
  OneSignal.setNotificationOpenedHandler((notification) => {
    handleNotificationOpened(notification);
  });

  OneSignal.setNotificationWillShowInForegroundHandler((notificationReceivedEvent) => {
    handleNotificationReceived(notificationReceivedEvent);
  });

  console.log('📱 OneSignal initialized with user_id:', userId);
};
```

### 2. Manejo de Notificaciones Recibidas

#### iOS (Swift)

```swift
func handleNotificationReceived(_ notification: OSNotification) {
    // Extraer datos del gimnasio
    guard let additionalData = notification.additionalData else { return }

    let gymId = additionalData["gym_id"] as? Int
    let gymName = additionalData["gym_name"] as? String
    let notificationType = additionalData["type"] as? String

    // El título ya incluye el nombre del gym
    let title = notification.title ?? "Notificación"
    let body = notification.body ?? ""

    // Logging para debugging
    print("📬 Notificación recibida:")
    print("   Gym: \(gymName ?? "Desconocido") (ID: \(gymId ?? 0))")
    print("   Tipo: \(notificationType ?? "unknown")")
    print("   Título: \(title)")

    // Opcional: Verificar si es del gym actual
    let currentGymId = UserDefaults.standard.integer(forKey: "current_gym_id")
    if let gymId = gymId, gymId != currentGymId {
        print("⚠️  Notificación de otro gimnasio (\(gymId) vs \(currentGymId))")
        // Opción 1: Guardar para mostrar después
        saveNotificationForLater(notification, gymId: gymId)
        // Opción 2: Mostrar con badge pero sin sonido
        // Opción 3: Mostrar igual (recomendado para mejor UX)
    }

    // Mostrar notificación local
    showLocalNotification(title: title, body: body, userInfo: additionalData)
}

func handleNotificationOpened(_ result: OSNotificationOpenedResult) {
    let notification = result.notification
    guard let additionalData = notification.additionalData else { return }

    let gymId = additionalData["gym_id"] as? Int
    let gymName = additionalData["gym_name"] as? String
    let notificationType = additionalData["type"] as? String

    print("👆 Usuario abrió notificación de \(gymName ?? "gym")")

    // Navegar según el tipo
    switch notificationType {
    case "class_reminder":
        navigateToClass(additionalData)
    case "event_created":
        navigateToEvent(additionalData)
    case "chat_message":
        navigateToChat(additionalData)
    case "event_cancelled":
        navigateToEventDetails(additionalData)
    default:
        navigateToHome(gymId: gymId)
    }
}
```

#### Android (Kotlin)

```kotlin
fun handleNotificationReceived(notificationReceivedEvent: OSNotificationReceivedEvent) {
    val notification = notificationReceivedEvent.notification
    val additionalData = notification.additionalData

    val gymId = additionalData?.optInt("gym_id")
    val gymName = additionalData?.optString("gym_name")
    val notificationType = additionalData?.optString("type")

    val title = notification.title ?: "Notificación"
    val body = notification.body ?: ""

    Log.d("Notifications", "📬 Notificación recibida:")
    Log.d("Notifications", "   Gym: $gymName (ID: $gymId)")
    Log.d("Notifications", "   Tipo: $notificationType")
    Log.d("Notifications", "   Título: $title")

    // Verificar si es del gym actual (opcional)
    val currentGymId = sharedPreferences.getInt("current_gym_id", 0)
    if (gymId != null && gymId != currentGymId) {
        Log.w("Notifications", "⚠️  Notificación de otro gimnasio ($gymId vs $currentGymId)")
        // Manejar según preferencias del usuario
    }

    // Mostrar notificación
    notificationReceivedEvent.complete(notification)
}

fun handleNotificationOpened(result: OSNotificationOpenedResult) {
    val notification = result.notification
    val additionalData = notification.additionalData

    val gymId = additionalData?.optInt("gym_id")
    val gymName = additionalData?.optString("gym_name")
    val notificationType = additionalData?.optString("type")

    Log.d("Notifications", "👆 Usuario abrió notificación de $gymName")

    // Navegar según tipo
    when (notificationType) {
        "class_reminder" -> navigateToClass(additionalData)
        "event_created" -> navigateToEvent(additionalData)
        "chat_message" -> navigateToChat(additionalData)
        "event_cancelled" -> navigateToEventDetails(additionalData)
        else -> navigateToHome(gymId)
    }
}
```

### 3. Preferencias de Usuario (Opcional)

Puedes permitir que los usuarios configuren qué notificaciones quieren recibir de cada gimnasio:

```swift
class NotificationPreferences {

    func shouldShowNotification(for gymId: Int) -> Bool {
        // Obtener preferencias del usuario
        let preferences = getUserNotificationPreferences()

        // Verificar si el usuario quiere notificaciones de este gym
        return preferences.allowedGyms.contains(gymId)
    }

    func enableNotifications(for gymId: Int) {
        var preferences = getUserNotificationPreferences()
        preferences.allowedGyms.insert(gymId)
        saveUserNotificationPreferences(preferences)
    }

    func disableNotifications(for gymId: Int) {
        var preferences = getUserNotificationPreferences()
        preferences.allowedGyms.remove(gymId)
        saveUserNotificationPreferences(preferences)
    }
}
```

### 4. Badge Counter por Gimnasio (Opcional)

Para mostrar notificaciones pendientes por gimnasio:

```swift
class BadgeManager {

    func incrementBadge(for gymId: Int) {
        var badges = getBadgesForAllGyms()
        badges[gymId, default: 0] += 1
        saveBadges(badges)
        updateUIBadges()
    }

    func clearBadge(for gymId: Int) {
        var badges = getBadgesForAllGyms()
        badges[gymId] = 0
        saveBadges(badges)
        updateUIBadges()
    }

    func getTotalBadgeCount() -> Int {
        let badges = getBadgesForAllGyms()
        return badges.values.reduce(0, +)
    }

    func getBadgeCount(for gymId: Int) -> Int {
        let badges = getBadgesForAllGyms()
        return badges[gymId, default: 0]
    }
}
```

## Tipos de Notificaciones Disponibles

| Tipo | Descripción | Data Adicional |
|------|-------------|----------------|
| `class_reminder` | Recordatorio de clase próxima | `class_id`, `class_name`, `start_time` |
| `event_created` | Nuevo evento creado | `event_id`, `event_title` |
| `event_cancelled` | Evento cancelado | `event_id`, `refund_cents`, `currency` |
| `chat_message` | Nuevo mensaje en chat | `chat_room_id`, `sender_id`, `stream_channel_id` |
| `chat_mention` | Mención en chat | `chat_room_id`, `sender_id`, `mentioned_user_id` |
| `payment_failed` | Pago fallido | `invoice_id`, `amount_due` |
| `subscription_renewed` | Suscripción renovada | `subscription_id`, `next_billing_date` |

## Testing

### 1. Verificar External User ID

```swift
// iOS
if let externalUserId = OneSignal.getDeviceState()?.userId {
    print("✅ External User ID configurado: \(externalUserId)")
} else {
    print("❌ External User ID NO configurado")
}
```

```kotlin
// Android
val externalUserId = OneSignal.getDeviceState()?.userId
if (externalUserId != null) {
    Log.d("Test", "✅ External User ID: $externalUserId")
} else {
    Log.e("Test", "❌ External User ID NO configurado")
}
```

### 2. Enviar Notificación de Prueba

Usa el endpoint del backend:

```bash
POST /api/v1/notifications/send
Authorization: Bearer {token}
X-Gym-ID: 1

{
  "user_ids": ["25"],
  "title": "Test",
  "message": "Probando notificaciones multi-gym",
  "data": {
    "test": true
  }
}
```

Deberías recibir una notificación con título: `"Fitness Pro: Test"`

## Troubleshooting

### Problema: No recibo notificaciones

1. ✅ Verifica que OneSignal esté inicializado
2. ✅ Verifica que `external_user_id` esté configurado
3. ✅ Verifica permisos de notificaciones en el dispositivo
4. ✅ Verifica que el usuario exista en OneSignal Dashboard
5. ✅ Revisa los logs del backend

### Problema: Recibo duplicados

- ❌ **NO** cambies el `external_user_id` cuando el usuario cambia de gym
- ✅ Usa siempre el mismo `user_id` para todo
- ✅ El backend ya filtra las notificaciones correctamente

### Problema: No veo el nombre del gym

1. ✅ Actualiza el backend a la última versión
2. ✅ Verifica que la notificación incluya `gym_name` en `additionalData`
3. ✅ Revisa los logs de la app móvil

## Mejores Prácticas

1. **✅ UN SOLO External User ID**: Nunca cambies el `external_user_id` del usuario
2. **✅ Usar gym_name del payload**: El título ya incluye el nombre del gym
3. **✅ Deep Linking**: Navega al contenido correcto cuando el usuario toca la notificación
4. **✅ Badge Management**: Actualiza badges cuando el usuario lee notificaciones
5. **✅ Logging**: Registra todas las notificaciones recibidas para debugging

## Ejemplo Completo

Ver archivo de ejemplo: `examples/NotificationManagerExample.swift` (próximamente)

## Soporte

Para problemas o preguntas, contacta al equipo de desarrollo backend.
