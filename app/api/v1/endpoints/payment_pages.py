"""
Páginas de éxito y cancelación para pagos de Stripe.

Estos endpoints proporcionan páginas básicas de HTML que se muestran
después de completar o cancelar un pago en Stripe.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from fastapi import Depends
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/membership/success", response_class=HTMLResponse)
async def payment_success_page(
    request: Request,
    session_id: str = Query(None, description="ID de sesión de Stripe")
):
    """
    Página de éxito después de completar un pago.
    
    Args:
        session_id: ID de la sesión de checkout de Stripe
        
    Returns:
        HTMLResponse: Página HTML de confirmación
    """
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>¡Pago Exitoso! - GymAPI</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0;
                padding: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }}
            .container {{
                background: white;
                padding: 2rem;
                border-radius: 12px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.1);
                text-align: center;
                max-width: 500px;
                margin: 20px;
            }}
            .success-icon {{
                font-size: 4rem;
                color: #10B981;
                margin-bottom: 1rem;
            }}
            h1 {{
                color: #1F2937;
                margin-bottom: 1rem;
                font-size: 2rem;
            }}
            p {{
                color: #6B7280;
                margin-bottom: 1.5rem;
                line-height: 1.6;
            }}
            .session-info {{
                background: #F3F4F6;
                padding: 1rem;
                border-radius: 8px;
                margin: 1rem 0;
                font-family: monospace;
                font-size: 0.9rem;
                color: #374151;
            }}
            .btn {{
                background: #3B82F6;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                text-decoration: none;
                display: inline-block;
                font-weight: 500;
                transition: background 0.2s;
            }}
            .btn:hover {{
                background: #2563EB;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✅</div>
            <h1>¡Pago Completado!</h1>
            <p>Tu membresía ha sido activada exitosamente. Ya puedes disfrutar de todos los beneficios de tu plan.</p>
            
            {'<div class="session-info">ID de Sesión: ' + session_id + '</div>' if session_id else ''}
            
            <p>Recibirás un email de confirmación en los próximos minutos.</p>
            
            <a href="/" class="btn">Volver a la App</a>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content, status_code=200)


@router.get("/membership/cancel", response_class=HTMLResponse)
async def payment_cancel_page(request: Request):
    """
    Página mostrada cuando el usuario cancela el pago.
    
    Returns:
        HTMLResponse: Página HTML de cancelación
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pago Cancelado - GymAPI</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0;
                padding: 0;
                background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            .container {
                background: white;
                padding: 2rem;
                border-radius: 12px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.1);
                text-align: center;
                max-width: 500px;
                margin: 20px;
            }
            .cancel-icon {
                font-size: 4rem;
                color: #F59E0B;
                margin-bottom: 1rem;
            }
            h1 {
                color: #1F2937;
                margin-bottom: 1rem;
                font-size: 2rem;
            }
            p {
                color: #6B7280;
                margin-bottom: 1.5rem;
                line-height: 1.6;
            }
            .btn {
                background: #3B82F6;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                text-decoration: none;
                display: inline-block;
                font-weight: 500;
                transition: background 0.2s;
                margin: 0 10px;
            }
            .btn:hover {
                background: #2563EB;
            }
            .btn-secondary {
                background: #6B7280;
            }
            .btn-secondary:hover {
                background: #4B5563;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="cancel-icon">⚠️</div>
            <h1>Pago Cancelado</h1>
            <p>Has cancelado el proceso de pago. Tu membresía no ha sido procesada.</p>
            <p>Si necesitas ayuda o tienes alguna pregunta, no dudes en contactarnos.</p>
            
            <a href="/membership/plans" class="btn">Ver Planes</a>
            <a href="/" class="btn btn-secondary">Volver a la App</a>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content, status_code=200) 