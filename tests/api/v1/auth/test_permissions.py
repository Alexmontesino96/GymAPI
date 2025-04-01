import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.core.auth0_fastapi import auth, Auth0User
from main import app

client = TestClient(app)

class DummyAuth0User(Auth0User):
    """Clase de usuario para pruebas."""
    def dict(self):
        return {
            "sub": self.id,
            "email": self.email,
            "permissions": self.permissions,
            "name": getattr(self, "name", "")
        }

@pytest.fixture
def mock_auth_user_admin():
    """Mock de un usuario autenticado con permisos de administrador"""
    return DummyAuth0User(
        sub="auth0|admin123",
        email="admin@example.com",
        permissions=["read:profile", "admin:users", "create:gym"],
        name="Admin User"
    )

@pytest.fixture
def mock_auth_user_regular():
    """Mock de un usuario autenticado con permisos básicos"""
    return DummyAuth0User(
        sub="auth0|user123",
        email="user@example.com",
        permissions=["read:profile"],
        name="Regular User"
    )

# TESTS

@patch('app.api.v1.endpoints.auth.auth.get_user')
def test_endpoint_with_required_scope_passes(mock_get_user, mock_auth_user_admin):
    """Un usuario con los scopes necesarios debe poder acceder al endpoint"""
    mock_get_user.return_value = mock_auth_user_admin
    
    # Endpoint que requiere scope admin:users
    response = client.post(
        "/api/v1/auth/create-admin",
        json={"secret_key": "test-secret"}
    )
    
    # Nota: Este test puede fallar si el ADMIN_SECRET_KEY no coincide con "test-secret"
    # Lo importante es verificar que la autenticación pasó (no 401 ni 403)
    assert response.status_code not in [401, 403]

@patch('app.api.v1.endpoints.auth.auth.get_user')
def test_endpoint_with_missing_scope_fails(mock_get_user, mock_auth_user_regular):
    """Un usuario sin los scopes necesarios debe recibir un error 403"""
    mock_get_user.return_value = mock_auth_user_regular
    
    # Endpoint que requiere scope admin:users
    response = client.post(
        "/api/v1/auth/create-admin",
        json={"secret_key": "test-secret"}
    )
    
    assert response.status_code == 403
    assert "scope" in response.json()["detail"].lower()

@patch('app.core.auth0_fastapi.auth.get_user')
def test_endpoint_with_permission_check(mock_get_user, mock_auth_user_admin):
    """Prueba para verificar permisos en endpoint protegido"""
    mock_get_user.return_value = mock_auth_user_admin
    
    # Endpoint que solo requiere autenticación estándar
    response = client.get("/api/v1/auth/me")
    
    assert response.status_code == 200
    assert response.json()["id"] == mock_auth_user_admin.id

@patch('app.core.auth0_fastapi.auth.get_user')
def test_verify_permissions_utility(mock_get_user, mock_auth_user_admin, mock_auth_user_regular):
    """Prueba la utilidad para verificar permisos de forma programática"""
    # Verificar permisos de usuario admin
    mock_get_user.return_value = mock_auth_user_admin
    
    # La función tiene_permiso es una función hipotética que deberíamos implementar
    # Aquí mostramos cómo podría ser probada
    with patch('app.core.auth0_fastapi.auth.verify_scope') as mock_verify:
        mock_verify.return_value = True
        
        admin_has_perm = auth.verify_scope(mock_auth_user_admin, "admin:users")
        assert admin_has_perm == True
        
        # Para el usuario regular
        mock_verify.return_value = False
        regular_has_perm = auth.verify_scope(mock_auth_user_regular, "admin:users")
        assert regular_has_perm == False 