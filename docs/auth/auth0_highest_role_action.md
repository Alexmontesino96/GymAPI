# Configuración de Auth0 para Asignar Permisos Basados en Roles

Este documento explica cómo configurar Auth0 para asignar permisos automáticamente basados en el rol más alto de un usuario.

## Resumen de la Solución

1. **En la API**: Se determina y almacena el rol más alto de cada usuario en Auth0 mediante `app_metadata`.
2. **En Auth0**: Una Action asigna automáticamente los permisos correspondientes durante la emisión del token.

## Configuración de la Action en Auth0

### Paso 1: Crear Nueva Action

1. Inicia sesión en tu [Dashboard de Auth0](https://manage.auth0.com/)
2. Ve a **Actions** → **Flows** → **Login**
3. Haz clic en **+ Create** y selecciona **Build Custom**

### Paso 2: Configurar Action

1. **Nombre**: "Asignar Permisos por Rol"
2. **Trigger**: Login / Post Login
3. **Runtime**: Node.js 18
4. Reemplaza el código con el siguiente:

```javascript
/**
 * Action que asigna permisos según el rol más alto del usuario
 * @param {Event} event - Información de la solicitud de autenticación
 * @param {API} api - API de Auth0 para modificar flujo de autenticación
 */
exports.onExecutePostLogin = async (event, api) => {
  // Definir los permisos para cada rol
  const rolePermissions = {
    "SUPER_ADMIN": [
      "tenant:admin", "tenant:read", 
      "user:admin", "user:write", "user:read", 
      "resource:admin", "resource:write", "resource:read"
    ],
    "ADMIN": [
      "tenant:read", 
      "user:write", "user:read", 
      "resource:admin", "resource:write", "resource:read"
    ],
    "OWNER": [
      "tenant:admin", "tenant:read", 
      "user:write", "user:read", 
      "resource:admin", "resource:write", "resource:read"
    ],
    "TRAINER": [
      "tenant:read", 
      "user:read", 
      "resource:write", "resource:read"
    ],
    "MEMBER": [
      "user:read", 
      "resource:write", "resource:read"
    ]
  };

  // Obtener el rol más alto del usuario desde app_metadata
  const highestRole = event.user.app_metadata?.highest_role || "MEMBER";
  
  // Log para depuración
  console.log(`Usuario ${event.user.email}: Rol más alto = ${highestRole}`);
  
  // Asignar permisos al token basados en el rol
  if (rolePermissions[highestRole]) {
    api.accessToken.setCustomClaim('permissions', rolePermissions[highestRole]);
    console.log(`Permisos asignados para rol ${highestRole}: ${rolePermissions[highestRole].join(', ')}`);
  } else {
    console.log(`ADVERTENCIA: Rol ${highestRole} no reconocido, utilizando permisos de MEMBER`);
    api.accessToken.setCustomClaim('permissions', rolePermissions["MEMBER"]);
  }
};
```

### Paso 3: Activar la Action

1. Despliega la Action haciendo clic en **Deploy**
2. Vuelve a **Flows** → **Login**
3. Arrastra la Action "Asignar Permisos por Rol" a la ubicación deseada dentro del flujo
4. Haz clic en **Apply**

## Migración Inicial de Usuarios

Una vez desplegada la solución en la API, debes realizar una migración inicial para asignar el rol más alto a todos los usuarios existentes:

1. Accede al endpoint `/api/v1/auth/admin/sync-roles-to-auth0` como usuario SUPER_ADMIN.
2. Este endpoint iniciará una tarea en segundo plano que:
   - Determinará el rol más alto de cada usuario
   - Actualizará esta información en Auth0

## Comportamiento Esperado

Con esta configuración:

1. Cada vez que un usuario inicie sesión, Auth0 verificará su `highest_role` en `app_metadata`
2. Asignará automáticamente los permisos correspondientes en el token
3. Los endpoints de la API verificarán estos permisos para autorizar acciones

## Solución de Problemas

Si los permisos no se asignan correctamente:

1. Verifica los logs de Auth0 para la Action "Asignar Permisos por Rol"
2. Asegúrate de que la API está actualizando correctamente `app_metadata` cuando cambian los roles
3. Confirma que el endpoint de migración inicial se ejecutó correctamente
4. Revisa manualmente los datos de usuario en Auth0 para verificar que `highest_role` está establecido

## Modificar Asignación de Permisos

Si necesitas cambiar los permisos asignados a cada rol, simplemente modifica el objeto `rolePermissions` en la Action de Auth0. 