import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
# Quitar import sys si ya no se usa aquí

# Importar la función de configuración de logging
from app.core.logging_config import setup_logging

# Llamar a la configuración de logging ANTES de importar/crear otros elementos
setup_logging()

# --- Configuración de Logging Explícita Eliminada --- 
# (Código anterior eliminado)
# ----------------------------------------

# Ahora importar el resto
from app.api.v1.api import api_router
from app.core.config import get_settings
from app.middleware.timing import TimingMiddleware
from app.core.scheduler import init_scheduler
from app.db.redis_client import initialize_redis_pool, close_redis_client

logger = logging.getLogger(__name__) # Mantener o ajustar según necesidad

# Obtener la instancia de configuración al inicio del módulo
settings_instance = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Lifespan: Startup iniciado...")
    
    # Iniciar el scheduler
    try:
        scheduler = init_scheduler()
        app.state.scheduler = scheduler
        logger.info("Lifespan: Scheduler inicializado.")
    except Exception as e:
        logger.error(f"Lifespan: Error al inicializar scheduler: {e}", exc_info=True)

    # Inicializar el pool de conexiones Redis
    print("Lifespan: Inicializando Redis connection pool...")
    redis_connected = False
    try:
        await initialize_redis_pool()
        logger.info("Lifespan: Redis connection pool inicializado correctamente.")
        redis_connected = True
    except Exception as e:
        logger.error(f"Lifespan: Error al inicializar Redis connection pool: {e}", exc_info=True)
    print(f"Lifespan: Conexión Redis {'EXITOSA' if redis_connected else 'FALLIDA'}.")
    
    yield # Aplicación en ejecución
    
    logger.info("Lifespan: Shutdown iniciado...")
    
    # Apagar el scheduler
    if hasattr(app.state, "scheduler") and app.state.scheduler:
        try:
            app.state.scheduler.shutdown()
            logger.info("Scheduler shut down.")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}", exc_info=True)
    
    # Cerrar conexión Redis
    print("Lifespan: Intentando cerrar connection pool de Redis...")
    try:
        await close_redis_client()
        logger.info("Lifespan: Connection pool de Redis cerrado.")
        print("Lifespan: Connection pool de Redis CERRADO exitosamente.")
    except Exception as e:
        logger.error(f"Lifespan: Error cerrando Redis connection pool: {e}", exc_info=True)
        print(f"Lifespan: Error al cerrar Redis connection pool: {e}")

app = FastAPI(
    title=settings_instance.PROJECT_NAME,
    description=settings_instance.PROJECT_DESCRIPTION, 
    version=settings_instance.VERSION,
    openapi_url=f"{settings_instance.API_V1_STR}/openapi.json",
    docs_url=f"{settings_instance.API_V1_STR}/docs",
    redoc_url=f"{settings_instance.API_V1_STR}/redoc",
    lifespan=lifespan,
    swagger_ui_oauth2_redirect_url=f"{settings_instance.API_V1_STR}/docs/oauth2-redirect",
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
        "clientId": settings_instance.AUTH0_CLIENT_ID,
        "appName": settings_instance.PROJECT_NAME,
        "scopes": "openid profile email read:users write:users delete:users read:trainer-members write:trainer-members delete:trainer-members",
    }
)

# <<< AÑADIR MIDDLEWARE DE LOGGING AQUÍ >>>
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Añadir un print para diagnóstico inmediato
    print(f"DEBUG: log_requests middleware ejecutado para: {request.method} {request.url}") 
    # Cambiar a logger.info para mayor visibilidad estándar
    logger.info(f"Middleware: Recibida petición: {request.method} {request.url}")
    logger.info(f"Middleware: Headers: {dict(request.headers)}")
    # El logger ya captura la IP, no es necesario extraerla aquí.
    
    response = await call_next(request)
    
    # Cambiar a logger.info
    logger.info(f"Middleware: Enviando respuesta: {response.status_code}")
    return response
# <<< FIN MIDDLEWARE DE LOGGING >>>

# Añadir middleware para medir el tiempo de respuesta
# Asegurarse que este middleware esté DESPUÉS del de logging si quieres loguear antes de medir
app.add_middleware(TimingMiddleware)

# Añadir el nuevo middleware de autenticación y tenant
from app.middleware.tenant_auth import setup_tenant_auth_middleware
setup_tenant_auth_middleware(app)

# Desactivar middleware de profiling en producción
if settings_instance.DEBUG_MODE:  # Usar la instancia
    from app.core.profiling import ProfilingMiddleware
    app.add_middleware(
        ProfilingMiddleware, 
        target_paths=[
            "/api/v1/users/p/gym-participants",
            "/api/v1/users/p/public-profile/"
        ]
    )

# Lista de orígenes permitidos para CORS
origins = ["*"]

# Configurar CORS para toda la aplicación
# Asegurarse que este middleware esté DESPUÉS del de logging si quieres loguear la petición antes de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Usar la lista simplificada
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,  # 24 horas en segundos
)

# Incluir routers
app.include_router(api_router, prefix=settings_instance.API_V1_STR)

# Ruta raíz
@app.get("/")
def root():
    return {
        "message": "Bienvenido a la API",
        "docs": f"{settings_instance.API_V1_STR}/docs",
    }

if __name__ == "__main__":
    # Usar la instancia para el reload, aunque no es ideal para producción
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings_instance.DEBUG_MODE) 