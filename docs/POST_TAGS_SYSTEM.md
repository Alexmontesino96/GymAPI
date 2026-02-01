# 📌 Sistema de Tags en Posts - Documentación

## 🎯 Resumen

El sistema de tags en posts **NO usa hashtags (#)** como Instagram. En su lugar, utiliza un sistema de **referencias** a entidades del gimnasio:

- **Usuarios mencionados** (@username)
- **Eventos etiquetados** (evento del gimnasio)
- **Sesiones/Clases etiquetadas** (clase de entrenamiento)

## 📊 Tipos de Tags

### 1. **MENTION** - Menciones de Usuarios
- **Tipo**: `TagType.MENTION`
- **Valor**: ID del usuario mencionado (string)
- **Cómo enviar**: Campo `mentioned_user_ids_json` con array de IDs
- **Ejemplo**: `[123, 456]` para mencionar a usuarios con ID 123 y 456

### 2. **EVENT** - Etiqueta de Evento
- **Tipo**: `TagType.EVENT`
- **Valor**: ID del evento (string)
- **Cómo enviar**: Campo `tagged_event_id` con el ID del evento
- **Ejemplo**: `5` para etiquetar el evento con ID 5

### 3. **SESSION** - Etiqueta de Sesión/Clase
- **Tipo**: `TagType.SESSION`
- **Valor**: ID de la sesión (string)
- **Cómo enviar**: Campo `tagged_session_id` con el ID de la sesión
- **Ejemplo**: `42` para etiquetar la sesión con ID 42

## 🔧 Estructura de la Base de Datos

### Tabla: `post_tags`
```sql
CREATE TABLE post_tags (
    id INTEGER PRIMARY KEY,
    post_id INTEGER NOT NULL,        -- FK a posts.id
    tag_type ENUM('mention', 'event', 'session'),
    tag_value VARCHAR(100),           -- ID de la entidad referenciada
    created_at DATETIME
);
```

### Restricciones:
- **Unique constraint**: `(post_id, tag_type, tag_value)` - No duplicar tags
- **Índices**: Por `tag_type` y `tag_value` para búsquedas eficientes

## 📤 Cómo Crear un Post con Tags

### Request al Endpoint `POST /api/v1/posts`

```javascript
// Datos del formulario (multipart/form-data)
const formData = new FormData();

// Campos básicos del post
formData.append('caption', 'Gran entrenamiento con @juan en el evento anual!');
formData.append('post_type', 'single_image');
formData.append('privacy', 'public');
formData.append('location', 'Gym Central');

// TAGS - Así se envían:
// 1. Mencionar usuarios (array de IDs)
formData.append('mentioned_user_ids_json', JSON.stringify([123, 456]));

// 2. Etiquetar un evento
formData.append('tagged_event_id', 5);

// 3. Etiquetar una sesión/clase
formData.append('tagged_session_id', 42);

// Archivos de media (opcional)
if (imageFile) {
    formData.append('files', imageFile);
}

// Enviar request
const response = await fetch('/api/v1/posts', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${token}`,
        'X-Gym-ID': gymId
    },
    body: formData
});
```

## 🔍 Procesamiento de Tags

### 1. **Tags Explícitos**
Se procesan los campos enviados en el request:
- `mentioned_user_ids_json` → Crea tags tipo MENTION
- `tagged_event_id` → Crea tag tipo EVENT
- `tagged_session_id` → Crea tag tipo SESSION

### 2. **Menciones en Caption**
El sistema también extrae menciones del caption usando regex:
```python
mention_pattern = r'@(\w+)'  # Busca @username en el texto
```

### 3. **Validaciones**
- ✅ Verifica que usuarios mencionados pertenezcan al gimnasio
- ✅ Verifica que evento pertenezca al gimnasio
- ✅ Verifica que sesión pertenezca al gimnasio
- ❌ Ignora tags inválidos sin lanzar error

## 📝 Ejemplo de Post Creado

```json
{
    "success": true,
    "post": {
        "id": 15,
        "caption": "Gran entrenamiento con @juan en el evento anual!",
        "post_type": "single_image",
        "privacy": "public",
        "location": "Gym Central",
        "tags": [
            {
                "id": 1,
                "tag_type": "mention",
                "tag_value": "123",
                "created_at": "2026-02-01T19:52:45Z"
            },
            {
                "id": 2,
                "tag_type": "mention",
                "tag_value": "456",
                "created_at": "2026-02-01T19:52:45Z"
            },
            {
                "id": 3,
                "tag_type": "event",
                "tag_value": "5",
                "created_at": "2026-02-01T19:52:45Z"
            },
            {
                "id": 4,
                "tag_type": "session",
                "tag_value": "42",
                "created_at": "2026-02-01T19:52:45Z"
            }
        ],
        "media": [...],
        "like_count": 0,
        "comment_count": 0,
        "created_at": "2026-02-01T19:52:45Z"
    }
}
```

## ⚠️ Notas Importantes

### NO son Hashtags
- ❌ **NO** se usan hashtags como `#fitness` o `#workout`
- ✅ **SÍ** se usan referencias a entidades reales del gym

### Límites
- No hay límite definido para cantidad de menciones
- Solo 1 evento por post
- Solo 1 sesión por post

### Permisos
- Solo se pueden mencionar usuarios del mismo gimnasio
- Solo se pueden etiquetar eventos/sesiones del mismo gimnasio
- Los usuarios mencionados NO reciben notificaciones (TODO pendiente)

## 🔍 Búsqueda por Tags

Para buscar posts por tags:

```sql
-- Posts que mencionan al usuario 123
SELECT * FROM posts p
JOIN post_tags pt ON p.id = pt.post_id
WHERE pt.tag_type = 'mention'
  AND pt.tag_value = '123';

-- Posts etiquetados en evento 5
SELECT * FROM posts p
JOIN post_tags pt ON p.id = pt.post_id
WHERE pt.tag_type = 'event'
  AND pt.tag_value = '5';

-- Posts de una sesión específica
SELECT * FROM posts p
JOIN post_tags pt ON p.id = pt.post_id
WHERE pt.tag_type = 'session'
  AND pt.tag_value = '42';
```

## 🐛 Verificación de Tags Creados

Para verificar si los tags se crearon correctamente:

1. **Revisar logs del servidor**: Buscar línea ~137 del servicio
2. **Query directo a BD**:
```sql
SELECT * FROM post_tags WHERE post_id = [ID_DEL_POST];
```

3. **Endpoint GET del post**: Los tags aparecen en la respuesta

## 📱 Recomendaciones para Frontend

### UI/UX Sugerencias:
1. **Menciones**: Autocompletado al escribir @ en caption
2. **Eventos**: Dropdown/selector de eventos activos
3. **Sesiones**: Selector de clases próximas o pasadas
4. **Visual**: Mostrar tags como chips/badges en el post

### Validaciones Frontend:
- Verificar que usuarios existen antes de enviar
- No permitir duplicados en menciones
- Limitar cantidad de menciones (ej: máx 10)
- Mostrar eventos/sesiones relevantes (próximos o recientes)