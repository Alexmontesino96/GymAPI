# 🐛 FIX: Compatibilidad de Tags con Frontend

## 🔴 Problema Identificado

El frontend enviaba `session_id` pero el backend esperaba `tagged_session_id`, causando que los tags no se guardaran.

### Logs del Frontend:
```
📌 [PostService] Etiquetando sesión ID: 926
✅ [PostService] session_id agregado al body del request
...
🏷️ [CreatePostViewModel] - Tags count: 0
⚠️ [CreatePostViewModel] Se envió session_id=926 pero el post no tiene tags!
```

### Resultado:
- Post creado exitosamente (ID: 18)
- **PERO sin tags guardados** (0 tags)

## ✅ Solución Implementada

### 1. **Endpoint Actualizado** (`/api/v1/endpoints/posts.py`)

#### Antes:
```python
@router.post("")
async def create_post(
    tagged_event_id: Optional[int] = Form(None),
    tagged_session_id: Optional[int] = Form(None),
    # ...
)
```

#### Después:
```python
@router.post("")
async def create_post(
    tagged_event_id: Optional[int] = Form(None),
    tagged_session_id: Optional[int] = Form(None),
    session_id: Optional[int] = Form(None),  # Compatibilidad con frontend
    event_id: Optional[int] = Form(None),    # Compatibilidad con frontend
    # ...
)
```

### 2. **Lógica de Compatibilidad**

```python
# Si el frontend envía 'session_id' en lugar de 'tagged_session_id'
if not tagged_session_id and session_id:
    tagged_session_id = session_id
    logger.info(f"Usando session_id={session_id} como tagged_session_id")

# Si el frontend envía 'event_id' en lugar de 'tagged_event_id'
if not tagged_event_id and event_id:
    tagged_event_id = event_id
    logger.info(f"Usando event_id={event_id} como tagged_event_id")
```

## 📝 Campos Aceptados Ahora

El endpoint acepta AMBOS nombres para mantener compatibilidad:

| Campo Original | Campo Alternativo | Descripción |
|---|---|---|
| `tagged_session_id` | `session_id` | ID de la sesión/clase a etiquetar |
| `tagged_event_id` | `event_id` | ID del evento a etiquetar |
| `mentioned_user_ids_json` | - | Array de IDs de usuarios mencionados |

## 🔧 Cómo Usar

### Opción 1: Frontend Actual (sin cambios)
```javascript
formData.append('session_id', 926);  // ✅ Funcionará
formData.append('event_id', 5);      // ✅ Funcionará
```

### Opción 2: Nombres Originales
```javascript
formData.append('tagged_session_id', 926);  // ✅ También funciona
formData.append('tagged_event_id', 5);      // ✅ También funciona
```

### Opción 3: Mixto
```javascript
formData.append('session_id', 926);         // ✅ OK
formData.append('tagged_event_id', 5);      // ✅ OK
```

## 🧪 Verificación

Para verificar que los tags se están creando:

```sql
-- Verificar tags del último post
SELECT p.id, p.caption, pt.*
FROM posts p
LEFT JOIN post_tags pt ON p.id = pt.post_id
WHERE p.id = (SELECT MAX(id) FROM posts);
```

O usar el script:
```bash
python scripts/verify_post_tags.py
```

## 🎯 Resultado Esperado

Después del fix, al crear un post con `session_id=926`:

```json
{
  "success": true,
  "post": {
    "id": 19,
    "tags": [
      {
        "id": 1,
        "tag_type": "session",
        "tag_value": "926",
        "created_at": "2026-02-01T20:15:00Z"
      }
    ],
    // ... resto del post
  }
}
```

## 📌 Notas

- **No Breaking Change**: Los clientes que usan `tagged_session_id` seguirán funcionando
- **Prioridad**: Si se envían ambos campos, `tagged_*` tiene prioridad
- **Logs**: Se registra cuando se usa el campo alternativo para debugging
- **Migración Futura**: Considerar estandarizar a un solo nombre en v2 del API