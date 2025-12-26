import secrets
import os
from typing import Any, Dict, List, Optional, Union
from functools import lru_cache
import logging

from pydantic import AnyHttpUrl, EmailStr, PostgresDsn, validator, field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configurar el logger
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        case_sensitive=True,
        extra="ignore"  # Permitir campos extra en .env
    )
    
    # Configuración básica
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    # 60 minutos * 24 horas * 8 días = 8 días
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8

    # URLs de la aplicación
    BASE_URL: str = os.getenv("BASE_URL", "https://gymapi-eh6m.onrender.com")
    FRONTEND_URL: Optional[str] = os.getenv("FRONTEND_URL", None)
    
    # Información del proyecto
    PROJECT_NAME: str = "GymAPI"
    PROJECT_DESCRIPTION: str = "API con FastAPI para gestión de gimnasios"
    VERSION: str = "0.2.0"
    
    # Debug mode
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "True").lower() in ("true", "1", "t")
    # Trust proxy headers for client IP derivation (rate limiting, logs)
    TRUST_PROXY_HEADERS: bool = os.getenv("TRUST_PROXY_HEADERS", "False").lower() in ("true", "1", "t")
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode='before')
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

   
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    SQLALCHEMY_DATABASE_URI: Optional[str] = None  # Definir explícitamente este campo
    
    @field_validator("DATABASE_URL", mode="before")
    def ensure_proper_url_format(cls, v: Optional[str], info) -> str:
        """Asegura que DATABASE_URL esté en el formato correcto y use Heroku si está disponible."""
        # No loguear el valor completo por seguridad
        logger.info("DATABASE_URL detectado en configuración")
        
        # Si hay una URL explícita, usarla
        if v:
            # Comprobar si es la URL antigua
            if 'db.ueijlkythlkqadxymzqd.supabase.co:5432' in v:
                logger.warning("Detectada URL antigua de Supabase. Se recomienda usar el Transaction Pooler.")
            
            # Asegurar formato postgresql://
            if v.startswith('postgres://'):
                corrected = 'postgresql://' + v[len('postgres://'):]
                logger.info("Corrigiendo formato de postgres:// a postgresql://")
                return corrected
            return v
        
        # Si no hay URL, usar la URL de Heroku
        return
    
    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before", check_fields=False)
    def assemble_db_connection(cls, v: Optional[str], info) -> Any:
        """Configura la URI de SQLAlchemy basada en DATABASE_URL.
        Siempre prioriza DATABASE_URL si está presente y tiene el formato correcto.
        """
        values = info.data
        db_url = values.get("DATABASE_URL")
        
        # Registro explícito
        logger.info("Configurando SQLALCHEMY_DATABASE_URI basado en DATABASE_URL")
        
        # SIEMPRE usar DATABASE_URL si está definido
        if db_url:
            # Asegurar formato postgresql://
            if db_url.startswith('postgres://'):
                corrected_url = 'postgresql://' + db_url[len('postgres://'):]
                logger.info(f"Corrigiendo DATABASE_URL de postgres:// a postgresql://")
                return corrected_url
            elif not db_url.startswith('postgresql://'):
                # Si no empieza con postgresql://, podría ser un formato inválido
                logger.warning("DATABASE_URL tiene un formato inesperado")
                # Intentar forzar el prefijo si parece una URL válida
                if '@' in db_url and ':' in db_url and '/' in db_url:
                    corrected = f"postgresql://{db_url}"
                    logger.info("Forzando prefijo postgresql://")
                    return corrected
                else:
                    # Si no se puede corregir, usar la URL de Heroku como fallback seguro
                    logger.error("Formato de DATABASE_URL inválido. Usando Heroku DB URL de fallback.")
                    return values.get("HEROKU_DB_URL") # Usar la URL explícita de Heroku
            # Registro final de la URL que se usará
            logger.info("SQLAlchemy URI configurada desde DATABASE_URL")
            return db_url # Ya está en formato postgresql://
        
        # Si DATABASE_URL no está definida en .env, usar HEROKU_DB_URL
        logger.warning("DATABASE_URL no encontrada, usando HEROKU_DB_URL por defecto.")
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

    # Public API Key (SHA256) para endpoints sin autenticación
    PUBLIC_API_KEY: str = os.getenv("PUBLIC_API_KEY", "")

    @field_validator("AUTH0_ISSUER", mode="before")
    def assemble_auth0_issuer(cls, v: str, info) -> str:
        if v:
            return v
        domain = info.data.get("AUTH0_DOMAIN")
        if domain:
            return f"https://{domain}/"
        return ""
    
    # Configuración de Stream.io para el chat y activity feeds
    STREAM_API_KEY: str = os.getenv("STREAM_API_KEY", "")
    STREAM_API_SECRET: str = os.getenv("STREAM_API_SECRET", "")
    STREAM_WEBHOOK_SECRET: str = os.getenv("STREAM_WEBHOOK_SECRET", "")
    STREAM_APP_ID: str = os.getenv("STREAM_APP_ID", "")
    STREAM_LOCATION: str = os.getenv("STREAM_LOCATION", "us-east")

    # Configuración de OneSignal para notificaciones push
    ONESIGNAL_APP_ID: Optional[str] = None
    ONESIGNAL_REST_API_KEY: Optional[str] = None

    # Configuración de OpenAI para IA nutricional
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "1500"))
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))

    @field_validator("OPENAI_API_KEY")
    def validate_openai_key(cls, v: str) -> str:
        if v and not v.startswith('sk-'):
            raise ValueError('OPENAI_API_KEY debe empezar con sk-')
        return v

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
    
    # Configuración del pool de conexiones Redis
    REDIS_POOL_MAX_CONNECTIONS: int = int(os.getenv("REDIS_POOL_MAX_CONNECTIONS", "50"))  # Aumentado de 20 a 50
    REDIS_POOL_SOCKET_TIMEOUT: int = int(os.getenv("REDIS_POOL_SOCKET_TIMEOUT", "5"))  # Aumentado de 2 a 5 segundos
    REDIS_POOL_HEALTH_CHECK_INTERVAL: int = int(os.getenv("REDIS_POOL_HEALTH_CHECK_INTERVAL", "30"))
    REDIS_POOL_RETRY_ON_TIMEOUT: bool = os.getenv("REDIS_POOL_RETRY_ON_TIMEOUT", "True").lower() in ("true", "1", "t")
    REDIS_POOL_SOCKET_KEEPALIVE: bool = os.getenv("REDIS_POOL_SOCKET_KEEPALIVE", "True").lower() in ("true", "1", "t")

    @field_validator("REDIS_URL", mode="before")
    def assemble_redis_connection(cls, v: Optional[str], info) -> Any:
        if isinstance(v, str):
            # No loguear valores exactos
            logger.info("REDIS_URL detectada en configuración")
            
            # Eliminar comentarios (todo lo que sigue a #)
            if '#' in v:
                v = v.split('#')[0]
                logger.info("REDIS_URL: eliminados comentarios en configuración")
            
            # Eliminar espacios en blanco al principio y final
            v = v.strip()
            logger.info("REDIS_URL normalizada (strip aplicado)")
            
            # Verificar que REDIS_PORT y REDIS_HOST no tengan valores extraños
            values = info.data
            if 'REDIS_PORT' in values:
                port_value = values.get('REDIS_PORT')
                if isinstance(port_value, str):
                    # Limpiar el puerto si es una cadena
                    values["REDIS_PORT"] = port_value.strip()
            
            # Si la URL es de un proveedor en la nube (rediss://) no usar componentes individuales
            if v.startswith('rediss://'):
                logger.info("Usando URL segura de Redis directamente (rediss://)")
                return v
            else:
                logger.info("Usando REDIS_URL directamente")
                return v
        
        values = info.data
        password_part = f":{values.get('REDIS_PASSWORD')}@" if values.get('REDIS_PASSWORD') else ""
        host = values.get('REDIS_HOST', 'localhost')
        port = values.get('REDIS_PORT', 6379)
        db = values.get('REDIS_DB', 0)
        
        # Asegurarse de que el puerto sea un entero
        if isinstance(port, str):
            port = int(port.strip())
            
        url = f"redis://{password_part}{host}:{port}/{db}"
        logger.info("URL de Redis construida a partir de componentes")
        return url

    # Auth0 Management API
    AUTH0_MGMT_CLIENT_ID: str = os.getenv("AUTH0_MGMT_CLIENT_ID", "")
    AUTH0_MGMT_CLIENT_SECRET: str = os.getenv("AUTH0_MGMT_CLIENT_SECRET", "")
    AUTH0_MGMT_AUDIENCE: str = os.getenv("AUTH0_MGMT_AUDIENCE", f"https://{AUTH0_DOMAIN}/api/v2/")

    # Storage configuration
    PROFILE_IMAGE_BUCKET: str = "profile-images"
    STORIES_BUCKET: str = os.getenv("STORIES_BUCKET", "stories")
    GYM_LOGO_BUCKET: str = os.getenv("GYM_LOGO_BUCKET", "gym_logo")
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
    
    # AWS Configuration
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    SQS_QUEUE_URL: Optional[str] = None  # Cola FIFO para eventos

    # SQS Nutrition Notifications (cola Standard, separada de eventos)
    SQS_NUTRITION_QUEUE_URL: Optional[str] = None
    SQS_NUTRITION_DLQ_URL: Optional[str] = None

    # Configuración para el Worker
    WORKER_API_KEY: str = os.getenv("WORKER_API_KEY", "")

    # Stripe Configuration
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_CONNECT_WEBHOOK_SECRET: str = os.getenv("STRIPE_CONNECT_WEBHOOK_SECRET", "")
    STRIPE_SUCCESS_URL: str = "http://localhost:8080/membership/success"
    STRIPE_CANCEL_URL: str = "http://localhost:8080/membership/cancel"

# Usar una función con caché para obtener la configuración
@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    # Logging final de la URL de la base de datos
    logger.info("Configuración cargada correctamente")
    return settings 
