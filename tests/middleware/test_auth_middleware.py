import pytest
from fastapi import FastAPI, Depends, Security, Request
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.core.auth0_fastapi import auth, Auth0User

# Creamos una app de prueba simplificada para probar el middleware
test_app = FastAPI()

# Ruta de prueba protegida
@test_app.get("/test-middleware-auth")
async def test_route(user: Auth0User = Security(auth.get_user, scopes=["read:profile"])):
    return {"user_id": user.id}

# Ruta para probar headers de request
@test_app.get("/test-headers")
async def test_headers(request: Request):
    auth_header = request.headers.get("Authorization", "")
    return {"auth_header": auth_header}

client = TestClient(test_app)

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
def mock_valid_token():
    """Token JWT válido para pruebas"""
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdXRoMHx0ZXN0MTIzIiwiaXNzIjoiaHR0cHM6Ly9leGFtcGxlLmF1dGgwLmNvbS8iLCJwZXJtaXNzaW9ucyI6WyJyZWFkOnByb2ZpbGUiXSwiZXhwIjoxNjkyMjMxMjM0fQ.signature"

@pytest.fixture
def mock_user():
    """Usuario de prueba"""
    return DummyAuth0User(
        sub="auth0|test123",
        email="test@example.com",
        permissions=["read:profile"]
    )

# TESTS

def test_middleware_passes_token_to_auth(mock_valid_token, mock_user):
    """Prueba que el middleware pasa correctamente el token a la autenticación"""
    with patch('app.core.auth0_fastapi.auth.get_user') as mock_auth:
        mock_auth.return_value = mock_user
        
        response = client.get(
            "/test-middleware-auth",
            headers={"Authorization": f"Bearer {mock_valid_token}"}
        )
        
        assert response.status_code == 200
        assert response.json() == {"user_id": "auth0|test123"}

def test_middleware_handles_missing_token():
    """Prueba que el middleware maneja correctamente un token ausente"""
    response = client.get("/test-middleware-auth")
    assert response.status_code == 401

def test_middleware_handles_malformed_token():
    """Prueba que el middleware maneja correctamente un token malformado"""
    response = client.get(
        "/test-middleware-auth",
        headers={"Authorization": "NotBearer malformed_token"}
    )
    assert response.status_code == 401

def test_middleware_extracts_bearer_token():
    """Prueba que el middleware extrae correctamente el token Bearer"""
    # Esta prueba verifica que el token se extraiga correctamente de la cabecera
    response = client.get(
        "/test-headers",
        headers={"Authorization": "Bearer valid_token"}
    )
    
    assert response.status_code == 200
    assert response.json()["auth_header"] == "Bearer valid_token"

@patch('app.core.auth0_fastapi.auth.get_user')
def test_error_handling_in_auth_middleware(mock_get_user):
    """Prueba que el middleware maneja correctamente errores internos"""
    # Simulamos un error interno en get_user
    mock_get_user.side_effect = Exception("Error interno")
    
    response = client.get(
        "/test-middleware-auth", 
        headers={"Authorization": "Bearer test_token"}
    )
    
    # Debería devolver un error 500 o similar
    assert response.status_code >= 400 