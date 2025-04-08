import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app
import urllib.request
from app.core.config import settings
from app.core.auth0_fastapi import Auth0User

client = TestClient(app)

class MockResponse:
    """Clase para simular una respuesta de urllib.request"""
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code
    
    def read(self):
        return json.dumps(self.data).encode()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass

@pytest.fixture
def mock_auth0_response():
    """Mock para las respuestas de Auth0"""
    return {
        "access_token": "test_access_token",
        "id_token": "test_id_token",
        "refresh_token": "test_refresh_token",
        "token_type": "Bearer",
        "expires_in": 86400
    }

@pytest.fixture
def mock_auth0_userinfo():
    """Mock para la información de usuario de Auth0"""
    return {
        "sub": "auth0|test123",
        "name": "Test User",
        "email": "test@example.com",
        "email_verified": True,
        "picture": "https://example.com/avatar.jpg"
    }

# TESTS

def test_login_endpoint_generates_correct_auth_url():
    """El endpoint de login debe generar la URL de Auth0 correcta"""
    response = client.get("/api/v1/auth/login")
    
    assert response.status_code == 200
    assert "auth_url" in response.json()
    auth_url = response.json()["auth_url"]
    
    # Verificar componentes de la URL
    assert f"https://{settings.AUTH0_DOMAIN}/authorize" in auth_url
    assert f"client_id={settings.AUTH0_CLIENT_ID}" in auth_url
    assert "response_type=code" in auth_url
    assert "scope=openid%20profile%20email" in auth_url

@patch('urllib.request.urlopen')
def test_token_exchange_endpoint(mock_urlopen, mock_auth0_response):
    """El endpoint de intercambio de token debe funcionar correctamente"""
    # Configurar mock para urllib.request.urlopen
    mock_urlopen.return_value = MockResponse(mock_auth0_response)
    
    response = client.post(
        "/api/v1/auth/token",
        data={
            "code": "test_code",
            "redirect_uri": "http://localhost:3001",
            "grant_type": "authorization_code"
        }
    )
    
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["access_token"] == mock_auth0_response["access_token"]

@patch('app.core.auth0_fastapi.auth.get_user')
def test_user_info_endpoint(mock_get_user, mock_auth0_userinfo):
    """El endpoint de información de usuario debe devolver los datos del usuario"""
    # Crear un usuario Auth0 para el mock
    mock_user = Auth0User(
        sub=mock_auth0_userinfo["sub"],
        email=mock_auth0_userinfo["email"],
        name=mock_auth0_userinfo["name"],
        picture=mock_auth0_userinfo["picture"],
        permissions=["read:profile"]
    )
    
    # Configurar mock para auth.get_user
    mock_get_user.return_value = mock_user
    
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer test_token"}
    )
    
    assert response.status_code == 200
    assert response.json()["id"] == mock_auth0_userinfo["sub"]
    assert response.json()["email"] == mock_auth0_userinfo["email"]

@patch('urllib.request.urlopen')
def test_token_exchange_handles_errors(mock_urlopen):
    """El endpoint de intercambio de token debe manejar errores de Auth0"""
    # Configurar mock para simular error de Auth0
    error_response = {
        "error": "invalid_grant",
        "error_description": "Invalid authorization code"
    }
    mock_urlopen.return_value = MockResponse(error_response, 400)
    
    response = client.post(
        "/api/v1/auth/token",
        data={
            "code": "invalid_code",
            "redirect_uri": "http://localhost:3001",
            "grant_type": "authorization_code"
        }
    )
    
    # Debería devolver un error, pero aún así ser un JSON válido
    assert response.status_code >= 400
    assert "error" in response.json() or "detail" in response.json()

@patch('app.api.v1.endpoints.auth.login.generate_state_param')
def test_login_redirect_validates_redirect_uri(mock_generate_state):
    """El endpoint de login debe validar las URLs de redirección"""
    mock_generate_state.return_value = "test_state"
    
    # Probamos con una URL no permitida
    response = client.get(
        "/api/v1/auth/login",
        params={"redirect_uri": "https://malicious-site.com"}
    )
    
    # Debería devolver un error 400
    assert response.status_code == 400
    assert "no permitida" in response.json()["detail"].lower() 