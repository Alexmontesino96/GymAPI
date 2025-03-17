import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.core.config import settings


class TestAuthEndpoints:
    """Tests para endpoints de autenticación."""
    
    def test_login_redirect_returns_auth_url(self, client):
        """Test que verifica que login_redirect devuelve una URL de Auth0."""
        response = client.get("/api/v1/auth/login")
        assert response.status_code == 200
        assert "auth_url" in response.json()
        auth_url = response.json()["auth_url"]
        assert settings.AUTH0_DOMAIN in auth_url
        assert "authorize" in auth_url
        assert "client_id" in auth_url
    
    def test_login_redirect_automatic(self, client):
        """Test que verifica que login_redirect_automatic redirecciona a Auth0."""
        response = client.get("/api/v1/auth/login-redirect", allow_redirects=False)
        assert response.status_code == 307  # Redirección temporal
        location = response.headers.get("location")
        assert settings.AUTH0_DOMAIN in location
        assert "authorize" in location
    
    @patch("httpx.AsyncClient.post")
    def test_auth0_callback_success(self, mock_post, client):
        """Test que verifica el procesamiento exitoso del callback de Auth0."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "mock_access_token",
            "id_token": "mock_id_token",
            "refresh_token": "mock_refresh_token",
            "token_type": "Bearer",
            "expires_in": 86400
        }
        mock_post.return_value = mock_response
        
        response = client.get("/api/v1/auth/callback?code=test_code")
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["access_token"] == "mock_access_token"
    
    @patch("httpx.AsyncClient.post")
    def test_auth0_callback_error(self, mock_post, client):
        """Test que verifica el manejo de errores en el callback de Auth0."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Invalid authorization code"
        }
        mock_post.return_value = mock_response
        
        response = client.get("/api/v1/auth/callback?code=invalid_code")
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
    
    @patch("app.core.auth.get_current_user")
    @patch("app.core.auth.auth0.verify_token")
    def test_me_endpoint(self, mock_verify_token, mock_get_current_user, client, mock_auth0_user):
        """Test que verifica el endpoint /me."""
        mock_verify_token.return_value = mock_auth0_user
        mock_get_current_user.return_value = mock_auth0_user
        
        headers = {"Authorization": "Bearer fake_token"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == mock_auth0_user["email"]
        assert data["name"] == mock_auth0_user["name"]
    
    def test_logout_endpoint(self, client):
        """Test que verifica que logout devuelve una URL de cierre de sesión."""
        response = client.get("/api/v1/auth/logout")
        assert response.status_code == 200
        assert "logout_url" in response.json()
        logout_url = response.json()["logout_url"]
        assert settings.AUTH0_DOMAIN in logout_url
        assert "v2/logout" in logout_url
        assert "returnTo" in logout_url 