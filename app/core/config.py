import secrets
from typing import Any, Dict, List, Optional, Union

from pydantic import AnyHttpUrl, EmailStr, PostgresDsn, validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)
    
    # Configuración básica
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    # 60 minutos * 24 horas * 8 días = 8 días
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    
    # Información del proyecto
    PROJECT_NAME: str = "GymAPI"
    PROJECT_DESCRIPTION: str = "API con FastAPI para gestión de gimnasios"
    VERSION: str = "0.1.0"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Base de datos
    DATABASE_URL: str
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None
    
    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    def assemble_db_connection(cls, v: Optional[str], info) -> Any:
        if isinstance(v, str):
            return v
        
        values = info.data
        db_url = values.get("DATABASE_URL")
        if db_url:
            return db_url
        
        return PostgresDsn.build(
            scheme="postgresql",
            username=values.get("POSTGRES_USER", "postgres"),
            password=values.get("POSTGRES_PASSWORD", "postgres"),
            host=values.get("POSTGRES_SERVER", "localhost"),
            port=values.get("POSTGRES_PORT", "5432"),
            path=f"/{values.get('POSTGRES_DB', 'app_db') or ''}",
        )

    # Email
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[EmailStr] = None
    EMAILS_FROM_NAME: Optional[str] = None

    # Superadmin
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    # Auth0 Configuration
    AUTH0_DOMAIN: str
    AUTH0_API_AUDIENCE: str
    AUTH0_ALGORITHMS: List[str] = ["RS256"]
    AUTH0_ISSUER: str
    AUTH0_CLIENT_ID: str
    AUTH0_CLIENT_SECRET: str
    AUTH0_CALLBACK_URL: str
    # Clave secreta para verificar los webhooks de Auth0 (debe coincidir con el secreto en Auth0 Actions)
    AUTH0_WEBHOOK_SECRET: str = ""
    # Clave secreta para crear administradores
    ADMIN_SECRET_KEY: str

    @field_validator("AUTH0_ISSUER", mode="before")
    def assemble_auth0_issuer(cls, v: str, info) -> str:
        if v:
            return v
        domain = info.data.get("AUTH0_DOMAIN")
        if domain:
            return f"https://{domain}/"
        return ""
    
    # Configuración de Stream.io para el chat
    STREAM_API_KEY: str
    STREAM_API_SECRET: str


settings = Settings() 