import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.v1.api import api_router
from app.core.config import settings
from app.middleware.timing import TimingMiddleware
from app.core.scheduler import init_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Código que se ejecuta al inicio
    # Iniciar el scheduler para tareas programadas (notificaciones)
    scheduler = init_scheduler()
    app.state.scheduler = scheduler
    
    yield
    
    # Código que se ejecuta al cierre
    # Apagar el scheduler al cerrar la aplicación
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION, 
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
    swagger_ui_oauth2_redirect_url=f"{settings.API_V1_STR}/docs/oauth2-redirect",
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
        "clientId": settings.AUTH0_CLIENT_ID,
        "appName": settings.PROJECT_NAME,
        "scopes": "openid profile email read:users write:users delete:users read:trainer-members write:trainer-members delete:trainer-members",
    }
)

# Añadir middleware para medir el tiempo de respuesta
app.add_middleware(TimingMiddleware)

# Lista de orígenes permitidos para CORS
origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS]
if "*" in origins:
    # Si se permite cualquier origen, usar una lista más amplia de dominios comunes
    origins = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3005",
        "http://127.0.0.1:8080",
        # Puedes agregar más dominios según sea necesario
    ]
else:
    # Asegurarse de que http://localhost:3001 esté siempre incluido
    if "http://localhost:3001" not in origins:
        origins.append("http://localhost:3001")

# Configurar CORS para toda la aplicación
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,  # 24 horas en segundos
)

# Incluir routers
app.include_router(api_router, prefix=settings.API_V1_STR)

# Ruta raíz
@app.get("/")
def root():
    return {
        "message": "Bienvenido a la API",
        "docs": f"{settings.API_V1_STR}/docs",
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 