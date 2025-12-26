"""
Endpoints públicos de Stripe para callbacks de onboarding.

Este módulo maneja las redirecciones desde Stripe después del onboarding.
No requieren autenticación ya que son llamados directamente por Stripe.
"""

from typing import Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.stripe_connect_service import stripe_connect_service
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/return", response_class=HTMLResponse, include_in_schema=False)
async def stripe_onboarding_return(
    gym_id: int = Query(..., description="ID del gimnasio"),
    status_param: str = Query(None, alias="status", description="Estado del onboarding"),
    db: Session = Depends(get_db)
):
    """
    Endpoint de retorno después de completar el onboarding de Stripe.

    Este endpoint es llamado por Stripe después de que el admin completa
    el proceso de onboarding. Actualiza el estado de la cuenta y muestra
    una página de éxito.

    Args:
        gym_id: ID del gimnasio que completó el onboarding
        status_param: Estado del proceso (completed, etc.)
        db: Sesión de base de datos

    Returns:
        HTMLResponse: Página HTML con el resultado
    """
    try:
        # Actualizar estado de la cuenta desde Stripe
        updated_account = await stripe_connect_service.update_gym_account_status(db, gym_id)

        settings = get_settings()
        frontend_url = settings.FRONTEND_URL or settings.BASE_URL

        # Si hay un FRONTEND_URL configurado, redirigir allá
        if settings.FRONTEND_URL:
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/admin/stripe/success?gym_id={gym_id}",
                status_code=303
            )

        # Si no hay frontend, mostrar página HTML simple
        html_content = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Configuración de Stripe Completada</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    padding: 20px;
                }}
                .container {{
                    background: white;
                    border-radius: 16px;
                    padding: 48px 40px;
                    max-width: 500px;
                    width: 100%;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    text-align: center;
                }}
                .success-icon {{
                    width: 80px;
                    height: 80px;
                    background: #10b981;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0 auto 24px;
                    animation: scaleIn 0.5s ease-out;
                }}
                .success-icon svg {{
                    width: 48px;
                    height: 48px;
                    stroke: white;
                    stroke-width: 3;
                    stroke-linecap: round;
                    stroke-linejoin: round;
                    fill: none;
                }}
                @keyframes scaleIn {{
                    from {{ transform: scale(0); }}
                    to {{ transform: scale(1); }}
                }}
                h1 {{
                    color: #1f2937;
                    font-size: 28px;
                    font-weight: 700;
                    margin-bottom: 16px;
                }}
                .status-info {{
                    background: #f3f4f6;
                    padding: 20px;
                    border-radius: 12px;
                    margin: 24px 0;
                }}
                .status-row {{
                    display: flex;
                    justify-content: space-between;
                    padding: 8px 0;
                    border-bottom: 1px solid #e5e7eb;
                }}
                .status-row:last-child {{
                    border-bottom: none;
                }}
                .status-label {{
                    color: #6b7280;
                    font-size: 14px;
                }}
                .status-value {{
                    color: #1f2937;
                    font-weight: 600;
                    font-size: 14px;
                }}
                .status-value.success {{
                    color: #10b981;
                }}
                p {{
                    color: #6b7280;
                    line-height: 1.6;
                    margin-bottom: 24px;
                }}
                .btn {{
                    display: inline-block;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 14px 32px;
                    border-radius: 8px;
                    text-decoration: none;
                    font-weight: 600;
                    transition: transform 0.2s, box-shadow 0.2s;
                    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
                }}
                .btn:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 6px 16px rgba(102, 126, 234, 0.6);
                }}
                .info-box {{
                    background: #eff6ff;
                    border-left: 4px solid #3b82f6;
                    padding: 16px;
                    border-radius: 8px;
                    text-align: left;
                    margin-top: 24px;
                }}
                .info-box p {{
                    margin: 0;
                    color: #1e40af;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">
                    <svg viewBox="0 0 24 24">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                </div>

                <h1>¡Configuración Completada!</h1>

                <p>
                    Tu cuenta de Stripe ha sido configurada exitosamente.
                    Ahora puedes procesar pagos para eventos y membresías.
                </p>

                <div class="status-info">
                    <div class="status-row">
                        <span class="status-label">Estado de cargos:</span>
                        <span class="status-value {"success" if updated_account.charges_enabled else ""}">
                            {"Habilitado ✓" if updated_account.charges_enabled else "Pendiente"}
                        </span>
                    </div>
                    <div class="status-row">
                        <span class="status-label">Estado de retiros:</span>
                        <span class="status-value {"success" if updated_account.payouts_enabled else ""}">
                            {"Habilitado ✓" if updated_account.payouts_enabled else "Pendiente"}
                        </span>
                    </div>
                    <div class="status-row">
                        <span class="status-label">Onboarding:</span>
                        <span class="status-value {"success" if updated_account.onboarding_completed else ""}">
                            {"Completado ✓" if updated_account.onboarding_completed else "En proceso"}
                        </span>
                    </div>
                </div>

                <a href="{frontend_url}/api/v1/docs" class="btn">
                    Ir al Dashboard de API
                </a>

                <div class="info-box">
                    <p>
                        <strong>Próximos pasos:</strong><br>
                        Puedes cerrar esta ventana y volver a tu aplicación.
                        Los cambios ya están activos.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        logger.info(
            f"Onboarding completado para gym {gym_id}. "
            f"Onboarding completado: {updated_account.onboarding_completed}, "
            f"Charges enabled: {updated_account.charges_enabled}, "
            f"Payouts enabled: {updated_account.payouts_enabled}"
        )

        return HTMLResponse(content=html_content)

    except ValueError as e:
        logger.error(f"Error actualizando estado de gym {gym_id}: {str(e)}")

        html_error = """
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Error de Configuración</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    padding: 20px;
                }
                .container {
                    background: white;
                    border-radius: 16px;
                    padding: 48px 40px;
                    max-width: 500px;
                    width: 100%;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    text-align: center;
                }
                .error-icon {
                    width: 80px;
                    height: 80px;
                    background: #ef4444;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0 auto 24px;
                }
                .error-icon svg {
                    width: 48px;
                    height: 48px;
                    stroke: white;
                    stroke-width: 3;
                }
                h1 { color: #1f2937; font-size: 28px; margin-bottom: 16px; }
                p { color: #6b7280; line-height: 1.6; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="error-icon">
                    <svg viewBox="0 0 24 24" fill="none">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </div>
                <h1>Error de Configuración</h1>
                <p>No se pudo actualizar el estado de la cuenta. Por favor, contacta a soporte.</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_error, status_code=500)

    except Exception as e:
        logger.error(f"Error inesperado en stripe return para gym {gym_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/reauth", response_class=HTMLResponse, include_in_schema=False)
async def stripe_onboarding_reauth(
    gym_id: int = Query(..., description="ID del gimnasio")
):
    """
    Endpoint de refresh cuando el link de onboarding expira.

    Redirige al usuario para generar un nuevo link de onboarding.
    """
    settings = get_settings()
    frontend_url = settings.FRONTEND_URL or settings.BASE_URL

    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sesión Expirada</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }}
            .container {{
                background: white;
                border-radius: 16px;
                padding: 48px 40px;
                max-width: 500px;
                width: 100%;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
            }}
            .warning-icon {{
                width: 80px;
                height: 80px;
                background: #f59e0b;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 24px;
            }}
            .warning-icon svg {{
                width: 48px;
                height: 48px;
                stroke: white;
                stroke-width: 3;
                fill: none;
            }}
            h1 {{ color: #1f2937; font-size: 28px; margin-bottom: 16px; }}
            p {{ color: #6b7280; line-height: 1.6; margin-bottom: 24px; }}
            .btn {{
                display: inline-block;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 14px 32px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: 600;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="warning-icon">
                <svg viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
            </div>
            <h1>Sesión Expirada</h1>
            <p>
                Tu sesión de configuración ha expirado.
                Por favor, solicita un nuevo link de configuración desde el panel de administración.
            </p>
            <a href="{frontend_url}/api/v1/docs" class="btn">
                Volver al Dashboard
            </a>
        </div>
    </body>
    </html>
    """

    logger.info(f"Sesión de onboarding expirada para gym {gym_id}")
    return HTMLResponse(content=html_content)
