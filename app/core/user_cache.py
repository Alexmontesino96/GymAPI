"""
Cache de usuario para solicitudes HTTP.

Este módulo proporciona una implementación simplificada de cache para
almacenar el usuario autenticado durante el ciclo de vida de una solicitud HTTP.
"""

from typing import Optional, Dict, Any, List
from fastapi import Request, Depends, Security, HTTPException
from fastapi.security import SecurityScopes
from app.core.auth0_fastapi import Auth0User, auth, Auth0HTTPBearer


class RequestUserCache:
    """Gestor simplificado de cache de usuario para solicitudes."""
    
    @staticmethod
    async def get_cached_user(
        request: Request,
        security_scopes: SecurityScopes
    ) -> Auth0User:
        """
        Obtiene el usuario autenticado desde el cache o Auth0.
        
        Args:
            request: La solicitud HTTP actual
            security_scopes: Scopes requeridos para el usuario
            
        Returns:
            Auth0User: Usuario autenticado
        """
        # Verificar si el usuario ya fue cacheado en esta petición
        if not hasattr(request.state, "current_user"):
            # Si no está en cache, obtener desde Auth0
            token = await Auth0HTTPBearer()(request)
            user = await auth.get_user(security_scopes=security_scopes, creds=token)
            # Almacenar en cache para esta petición
            request.state.current_user = user
            return user
            
        # Para usuarios ya cacheados, verificar los scopes
        user = request.state.current_user
        
        # Verificar que el usuario tenga los scopes necesarios
        if security_scopes.scopes:
            user_permissions = getattr(user, "permissions", []) or []
            for scope in security_scopes.scopes:
                if scope not in user_permissions:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Permiso insuficiente: {scope}",
                        headers={"WWW-Authenticate": f'Bearer scope="{security_scopes.scope_str}"'}
                    )
        
        # Devolver usuario cacheado
        return user


# Dependencia simplificada para obtener usuario cacheado
async def get_current_user_cached(
    request: Request,
    security_scopes: SecurityScopes = SecurityScopes([])
) -> Auth0User:
    """
    Dependencia de FastAPI para obtener usuario cacheado.
    
    Args:
        request: La solicitud HTTP actual
        security_scopes: Scopes requeridos
        
    Returns:
        Auth0User: Usuario autenticado (cacheado)
    """
    return await RequestUserCache.get_cached_user(request, security_scopes) 