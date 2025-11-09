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

**⚠️ IMPORTANTE:** Esta API usa **Auth0** para autenticación, NO Supabase Auth.

Por lo tanto, las políticas con `TO authenticated` **NO funcionarán** porque:
- Los requests usan `SUPABASE_ANON_KEY` (anónima)
- No hay usuarios autenticados en Supabase Auth
- `auth.uid()` será `null`

---

### 🎯 Políticas Correctas para Auth0 + Supabase Storage

#### Opción A: Políticas Públicas con Anon Key (RECOMENDADO)

Estas políticas permiten operaciones con la `anon key`:

**1. Permitir INSERT y UPDATE con anon key**

En SQL Editor:
```sql
CREATE POLICY "Allow anon insert stories"
ON storage.objects FOR INSERT
TO anon, authenticated
WITH CHECK (bucket_id = 'stories');

CREATE POLICY "Allow anon update stories"
ON storage.objects FOR UPDATE
TO anon, authenticated
USING (bucket_id = 'stories')
WITH CHECK (bucket_id = 'stories');
```

**2. Lectura pública**
```sql
CREATE POLICY "Allow public read stories"
ON storage.objects FOR SELECT
TO public
USING (bucket_id = 'stories');
```

**3. Eliminar con anon key**
```sql
CREATE POLICY "Allow anon delete stories"
ON storage.objects FOR DELETE
TO anon, authenticated
USING (bucket_id = 'stories');
```

---

#### Opción B: Bucket Público Sin RLS (MÁS SIMPLE)

Si prefieres no usar RLS (más simple pero menos seguro):

1. En Supabase Dashboard > Storage > "stories" bucket
2. Click en **Settings** (del bucket)
3. ✅ Activar **Public bucket**
4. **NO crear políticas RLS**

**Ventajas:**
- ✅ Más simple
- ✅ No requiere políticas
- ✅ Funciona inmediatamente

**Desventajas:**
- ❌ Cualquiera con la URL puede borrar archivos
- ❌ Menos seguro (pero la seguridad real está en tu API con Auth0)

---

#### Opción C: Service Role Key (Bypass RLS)

Usar `SUPABASE_SERVICE_ROLE_KEY` en lugar de `SUPABASE_ANON_KEY`:

**En `.env` y Render:**
```bash
# Cambiar de:
SUPABASE_ANON_KEY=eyJhbGc...  # Anon key - respeta RLS

# A:
SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...  # Service role - bypass RLS
```

**En `app/core/config.py`:**
```python
SUPABASE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
# En lugar de SUPABASE_ANON_KEY
```

**Ventajas:**
- ✅ Bypass completo de RLS
- ✅ Control total desde tu API (con Auth0)

**Desventajas:**
- ⚠️ Service role key es muy poderosa (guardar como secreto)

---

### ✅ Configuración Recomendada: Validación en API

**Enfoque adoptado:** Seguridad a nivel de API con Auth0, storage permisivo

**Razón:**
- ✅ La API ya valida con Auth0 (tokens JWT)
- ✅ Los endpoints `/api/v1/stories/` requieren autenticación
- ✅ Supabase Storage es solo almacenamiento pasivo
- ✅ Más simple y mantenible

---

### 🎯 Configuración Final (Opción B - Bucket Público)

**Pasos:**

1. **Crear bucket "stories" como PÚBLICO**
   - En Supabase Dashboard > Storage
   - New Bucket > Name: `stories`
   - ✅ **Public bucket** activado
   - File size limit: 50 MB

2. **NO crear políticas RLS**
   - Dejar las policies vacías
   - El acceso es público desde Supabase
   - La seguridad la maneja Auth0 en la API

---

### 🔒 Cómo Funciona la Seguridad

**Flujo de upload de story:**

```
Cliente (App móvil)
    ↓
    | POST /api/v1/stories/
    | Authorization: Bearer {AUTH0_TOKEN}
    | X-Gym-ID: 5
    | media=@imagen.jpg
    ↓
FastAPI Endpoint (stories.py)
    ↓
    | 1. Auth0 valida token JWT ✅
    | 2. get_current_db_user() obtiene usuario ✅
    | 3. Verifica permisos y gym_id ✅
    ↓
MediaService.upload_story_media()
    ↓
    | 4. Construye path: gym_5/user_123/stories/abc.jpg
    | 5. Sube a Supabase (con ANON_KEY)
    ↓
Supabase Storage (bucket público)
    ↓
    | 6. Acepta el upload (bucket público)
    | 7. Retorna URL pública
    ↓
API retorna 201 Created
```

**Seguridad:**
- ✅ Solo usuarios autenticados (Auth0) pueden llamar `/api/v1/stories/`
- ✅ La API valida que el usuario pertenece al gym
- ✅ La API construye la ruta con el user_id correcto
- ⚠️ Las URLs son públicas (cualquiera con la URL puede ver la imagen)
- ⚠️ Para borrar, se debe llamar al endpoint de API (también validado)

**Limitaciones aceptables:**
- Una vez subida, la URL es pública (normal para stories estilo Instagram)
- No se puede borrar directamente desde Supabase (solo vía API)
- Esto es **correcto** para el caso de uso de stories

---

### ❌ Lo que NO se usa

- ❌ Políticas RLS con `TO authenticated` (requieren Supabase Auth)
- ❌ Políticas con `auth.uid()` (Auth0 no es Supabase Auth)
- ❌ Service Role Key (innecesario para bucket público)

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
