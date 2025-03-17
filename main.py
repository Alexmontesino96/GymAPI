import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.v1.api import api_router
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Código que se ejecuta al inicio
    # Aquí puedes agregar tareas que se ejecutan al iniciar la aplicación
    yield
    # Código que se ejecuta al cierre
    # Aquí puedes agregar tareas que se ejecutan al apagar la aplicación

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

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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