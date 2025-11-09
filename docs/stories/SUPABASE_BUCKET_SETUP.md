# Configuración del Bucket de Stories en Supabase

## Problema Resuelto

**Error anterior:** `InvalidKey: Invalid key: gym_4/user_auth0|67f71e304b8a05024c163e04/stories/...jpg`

**Causa:** Se usaba el Auth0 ID (con carácter `|`) en la ruta del archivo, lo cual Supabase Storage no permite.

**Solución:**
- Usar ID numérico de base de datos en lugar de Auth0 ID
- Bucket dedicado "stories" separado de perfiles

## Pasos para Configurar el Bucket en Supabase

### 1. Crear el Bucket "stories"

1. Ir a Supabase Dashboard
2. Navegar a **Storage** > **Buckets**
3. Click en **New bucket**
4. Configuración:
   - **Name:** `stories`
   - **Public bucket:** ✅ Sí (para URLs públicas)
   - **Allowed MIME types:**
     - `image/jpeg`
     - `image/png`
     - `image/gif`
     - `image/webp`
     - `video/mp4`
     - `video/quicktime` (mov)
     - `video/x-msvideo` (avi)
   - **File size limit:** 50 MB

5. Click **Create bucket**

### 2. Configurar Políticas de Acceso (RLS)

**IMPORTANTE:** En Supabase Dashboard, las políticas se crean desde la interfaz web, NO ejecutando SQL directamente.

#### Pasos para crear políticas:

1. Ir a **Storage** > **Policies** en el bucket "stories"
2. Click en **New Policy**
3. Seleccionar la operación (INSERT, SELECT, DELETE, UPDATE)
4. Completar los campos según las políticas abajo

---

#### Política 1: Permitir upload autenticado

**En Supabase Dashboard:**
- **Policy name:** `Users can upload their own stories`
- **Allowed operation:** `INSERT`
- **Target roles:** `authenticated`
- **USING expression:** (dejar vacío para INSERT)
- **WITH CHECK expression:**
```sql
bucket_id = 'stories' AND
(storage.foldername(name))[1] LIKE 'gym_%' AND
(storage.foldername(name))[2] LIKE 'user_%'
```

**O usando SQL Editor:**
```sql
CREATE POLICY "Users can upload their own stories"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (
  bucket_id = 'stories' AND
  (storage.foldername(name))[1] LIKE 'gym_%' AND
  (storage.foldername(name))[2] LIKE 'user_%'
);
```

---

#### Política 2: Lectura pública

**En Supabase Dashboard:**
- **Policy name:** `Public read access for stories`
- **Allowed operation:** `SELECT`
- **Target roles:** `public`
- **USING expression:**
```sql
bucket_id = 'stories'
```
- **WITH CHECK expression:** (dejar vacío para SELECT)

**O usando SQL Editor:**
```sql
CREATE POLICY "Public read access for stories"
ON storage.objects FOR SELECT
TO public
USING (bucket_id = 'stories');
```

---

#### Política 3: Eliminar propias stories

**En Supabase Dashboard:**
- **Policy name:** `Users can delete their own stories`
- **Allowed operation:** `DELETE`
- **Target roles:** `authenticated`
- **USING expression:**
```sql
bucket_id = 'stories'
```
- **WITH CHECK expression:** (dejar vacío para DELETE)

**O usando SQL Editor:**
```sql
CREATE POLICY "Users can delete their own stories"
ON storage.objects FOR DELETE
TO authenticated
USING (bucket_id = 'stories');
```

---

**ALTERNATIVA SIMPLE:** Si las políticas anteriores causan problemas, puedes usar estas políticas más permisivas:

```sql
-- Permitir todo a usuarios autenticados (SOLO PARA DESARROLLO)
CREATE POLICY "Allow authenticated users all operations"
ON storage.objects
TO authenticated
USING (bucket_id = 'stories')
WITH CHECK (bucket_id = 'stories');

-- Lectura pública
CREATE POLICY "Allow public read"
ON storage.objects FOR SELECT
TO public
USING (bucket_id = 'stories');
```

### 3. Estructura de Carpetas

Las rutas de archivos siguen este patrón:
```
stories/
  ├── gym_1/
  │   ├── user_123/
  │   │   └── stories/
  │   │       ├── abc123def.jpg
  │   │       ├── xyz789abc.mp4
  │   │       └── ...
  │   └── user_456/
  │       └── stories/
  ├── gym_2/
  │   └── user_789/
  │       └── stories/
  └── ...
```

**Formato:** `gym_{gym_id}/user_{db_user_id}/stories/{uuid}.{ext}`

**Nota:** `db_user_id` es el ID numérico de la tabla `users`, NO el Auth0 ID.

### 4. Variables de Entorno

En `.env` y Render, configurar:
```bash
# Opcional - default es "stories"
STORIES_BUCKET=stories
```

### 5. Verificación

Para verificar que el bucket funciona:

```bash
# Test local
python -c "
from app.core.config import get_settings
settings = get_settings()
print(f'Bucket configurado: {settings.STORIES_BUCKET}')
"
```

```bash
# Test de upload (requiere token válido)
curl -X POST https://gymapi-eh6m.onrender.com/api/v1/stories/ \
  -H 'Authorization: Bearer TU_TOKEN' \
  -H 'X-Gym-ID: 4' \
  -F 'story_type=image' \
  -F 'privacy=public' \
  -F 'media=@test_image.jpg'
```

## Diferencias vs Bucket Anterior

| Aspecto | Bucket Anterior | Bucket "stories" |
|---------|----------------|------------------|
| Nombre | `userphotoprofile` | `stories` |
| User ID en path | Auth0 ID (`auth0\|123`) | DB ID numérico (`123`) |
| Propósito | Fotos de perfil | Stories temporales |
| Tamaño máximo | Variable | 50 MB videos, 10 MB imágenes |

## Troubleshooting

### Error: "Bucket does not exist"
- Verificar que el bucket "stories" está creado en Supabase
- Verificar variable `STORIES_BUCKET` en Render

### Error: "Invalid key"
- Verificar que se está usando `db_user.id` (numérico)
- NO usar `current_user.id` (Auth0 ID con `|`)

### Error: "Policy violation"
- Verificar que las políticas RLS están configuradas
- Verificar que el token Auth0 es válido

## Código Relevante

**Dependencia para obtener user_id correcto:**
```python
from app.core.auth0_fastapi import get_current_db_user

@router.post("/")
async def create_story(
    db_user: User = Depends(get_current_db_user)  # ✅ User de BD
):
    # db_user.id es numérico (ej: 123)
    media_service.upload_story_media(user_id=db_user.id)
```

**NO usar:**
```python
from app.core.auth0_fastapi import get_current_user

@router.post("/")
async def create_story(
    current_user: Auth0User = Depends(get_current_user)  # ❌
):
    # current_user.id es "auth0|67f..." (con |)
    media_service.upload_story_media(user_id=current_user.id)  # ❌ Falla
```
