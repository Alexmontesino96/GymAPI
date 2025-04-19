import secrets
import os
from typing import Any, Dict, List, Optional, Union
from functools import lru_cache

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
    VERSION: str = "0.2.0"
    
    # Debug mode
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "False").lower() in ("true", "1", "t")
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode='before')
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Base de datos - URL explícita y de respaldo para Heroku
    HEROKU_DB_URL: str = "postgresql://u6chpjmhvbacn5:pcc8066ee2c146523c96e94ea9c289bdfb35af0a929c1c0243adbe5dd4ea85546@c6sfjnr30ch74e.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/d8mrfqhqd7jn4k"
    DATABASE_URL: str = os.getenv("DATABASE_URL", HEROKU_DB_URL)
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None
    
    @field_validator("DATABASE_URL", mode="before")
    def ensure_proper_url_format(cls, v: Optional[str], info) -> str:
        """Asegura que DATABASE_URL esté en el formato correcto y use Heroku si está disponible."""
        # Si hay una URL explícita, usarla
        if v:
            # Ya no detectamos ni sustituimos la URL de Supabase
            # Asegurar formato postgresql://
            if v.startswith('postgres://'):
                return 'postgresql://' + v[len('postgres://'):]
            return v
        
        # Si no hay URL, usar la URL de Heroku
        return "postgresql://u6chpjmhvbacn5:pcc8066ee2c146523c96e94ea9c289bdfb35af0a929c1c0243adbe5dd4ea85546@c6sfjnr30ch74e.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/d8mrfqhqd7jn4k"
    
    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    def assemble_db_connection(cls, v: Optional[str], info) -> Any:
        """Configura la URI de SQLAlchemy basada en DATABASE_URL.
        Siempre prioriza DATABASE_URL si está presente y tiene el formato correcto.
        """
        values = info.data
        db_url = values.get("DATABASE_URL")
        
        # SIEMPRE usar DATABASE_URL si está definido
        if db_url:
            # Asegurar formato postgresql://
            if db_url.startswith('postgres://'):
                corrected_url = 'postgresql://' + db_url[len('postgres://'):]
                print(f"INFO: Corrigiendo DATABASE_URL de postgres:// a {corrected_url.split('@')[0]}@...")
                return corrected_url
            elif not db_url.startswith('postgresql://'):
                # Si no empieza con postgresql://, podría ser un formato inválido
                print(f"WARNING: DATABASE_URL tiene un formato inesperado: {db_url}")
                # Intentar forzar el prefijo si parece una URL válida
                if '@' in db_url and ':' in db_url and '/' in db_url:
                    return f"postgresql://{db_url}"
                else:
                    # Si no se puede corregir, usar la URL de Heroku como fallback seguro
                    print(f"ERROR: Formato de DATABASE_URL inválido: {db_url}. Usando Heroku DB URL de fallback.")
                    return values.get("HEROKU_DB_URL") # Usar la URL explícita de Heroku
            return db_url # Ya está en formato postgresql://
        
        # Si DATABASE_URL no está definida en .env, usar HEROKU_DB_URL
        print("INFO: DATABASE_URL no encontrada en .env, usando HEROKU_DB_URL por defecto.")
        return values.get("HEROKU_DB_URL")

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
    AUTH0_DOMAIN: str = os.getenv("AUTH0_DOMAIN", "dev-gd5crfe6qbqlu23p.us.auth0.com")
    AUTH0_API_AUDIENCE: str = os.getenv("AUTH0_API_AUDIENCE", "https://gymapi")
    AUTH0_ALGORITHMS: List[str] = ["RS256"]
    AUTH0_ISSUER: str = os.getenv("AUTH0_ISSUER", f"https://{AUTH0_DOMAIN}/")
    AUTH0_CLIENT_ID: str
    AUTH0_CLIENT_SECRET: str
    AUTH0_CALLBACK_URL: str
    AUTH0_WEBHOOK_SECRET: str = os.getenv("AUTH0_WEBHOOK_SECRET", "")
    ADMIN_SECRET_KEY: str = os.getenv("ADMIN_SECRET_KEY", "admin-secret-key")

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

    # Configuración de OneSignal para notificaciones push
    ONESIGNAL_APP_ID: Optional[str] = None
    ONESIGNAL_REST_API_KEY: Optional[str] = None

    # Lista de URLs de redirección permitidas
    AUTH0_ALLOWED_REDIRECT_URIS: List[str]

    @field_validator("AUTH0_ALLOWED_REDIRECT_URIS", mode="before")
    def assemble_redirect_uris(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, list):
            # Asegurar que http://localhost:3001 siempre esté en la lista
            result = v.copy()
            if "http://localhost:3001" not in result:
                result.append("http://localhost:3001")
            return result
        elif isinstance(v, str):
            try:
                # Intentar analizar como JSON (formato ["url1", "url2", ...])
                import json
                result = json.loads(v)
                if "http://localhost:3001" not in result:
                    result.append("http://localhost:3001")
                return result
            except json.JSONDecodeError:
                # Si no es JSON válido, verificar si es una cadena separada por comas
                if ',' in v:
                    # Si es una cadena separada por comas, dividirla
                    result = [uri.strip() for uri in v.split(',')]
                    if "http://localhost:3001" not in result:
                        result.append("http://localhost:3001")
                    return result
                else:
                    # Si es una sola URL, asegurar que http://localhost:3001 esté incluido
                    result = [v]
                    if "http://localhost:3001" not in result:
                        result.append("http://localhost:3001")
                    return result

    # Configuración de Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_USERNAME: Optional[str] = os.getenv("REDIS_USERNAME", None)
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)
    REDIS_URL: str = "redis://localhost:6379/0"

    @field_validator("REDIS_URL", mode="before")
    def assemble_redis_connection(cls, v: Optional[str], info) -> Any:
        if isinstance(v, str):
            return v
        
        values = info.data
        password_part = f":{values.get('REDIS_PASSWORD')}@" if values.get('REDIS_PASSWORD') else ""
        return f"redis://{password_part}{values.get('REDIS_HOST', 'localhost')}:{values.get('REDIS_PORT', 6379)}/{values.get('REDIS_DB', 0)}"

    # Auth0 Management API
    AUTH0_MGMT_CLIENT_ID: str = os.getenv("AUTH0_MGMT_CLIENT_ID", "")
    AUTH0_MGMT_CLIENT_SECRET: str = os.getenv("AUTH0_MGMT_CLIENT_SECRET", "")
    AUTH0_MGMT_AUDIENCE: str = os.getenv("AUTH0_MGMT_AUDIENCE", f"https://{AUTH0_DOMAIN}/api/v2/")

    # Storage configuration
    PROFILE_IMAGE_BUCKET: str = "profile-images"
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    S3_ACCESS_KEY_ID: str = os.getenv("S3_ACCESS_KEY_ID", "")
    S3_SECRET_ACCESS_KEY: str = os.getenv("S3_SECRET_ACCESS_KEY", "")  # ¡Reemplazar con la clave real en producción!

    # Notification config
    FCM_PROJECT_ID: str = os.getenv("FCM_PROJECT_ID", "")
    FCM_PRIVATE_KEY_ID: str = os.getenv("FCM_PRIVATE_KEY_ID", "")
    FCM_PRIVATE_KEY: str = os.getenv("FCM_PRIVATE_KEY", "").replace("\\n", "\n")
    FCM_CLIENT_EMAIL: str = os.getenv("FCM_CLIENT_EMAIL", "")
    FCM_CLIENT_ID: str = os.getenv("FCM_CLIENT_ID", "")
    FCM_CLIENT_CERT_URL: str = os.getenv("FCM_CLIENT_CERT_URL", "")

    # Configuración Redis
    CACHE_TTL_USER_MEMBERSHIP: int = 3600
    CACHE_TTL_NEGATIVE: int = 60 # 1 minuto
    CACHE_TTL_GYM_DETAILS: int = 3600 # 1 hora para detalles del gym
    CACHE_TTL_USER_PROFILE: int = 300 # <<< NUEVO: 5 minutos para perfil de usuario >>>

# Usar una función con caché para obtener la configuración
@lru_cache()
def get_settings() -> Settings:
    return Settings() 