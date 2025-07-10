"""
Páginas de éxito y cancelación para pagos de Stripe.

Estos endpoints proporcionan páginas básicas de HTML que se muestran
después de completar o cancelar un pago en Stripe.
"""

from fastapi import APIRouter, Request, Query, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.stripe_service import stripe_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/membership/success", response_class=HTMLResponse)
async def payment_success_page(
    request: Request,
    session_id: str = Query(None, description="ID de sesión de Stripe"),
    db: Session = Depends(get_db)
):
    """
    Página de éxito después de completar un pago.
    
    Esta página procesa automáticamente el session_id para activar la membresía
    y muestra el resultado al usuario.
    
    Args:
        session_id: ID de la sesión de checkout de Stripe
        db: Sesión de base de datos
        
    Returns:
        HTMLResponse: Página HTML de confirmación
    """
    
    # Variables para el contenido de la página
    payment_processed = False
    membership_info = None
    error_message = None
    
    # Procesar el pago automáticamente si hay session_id
    if session_id:
        try:
            logger.info(f"🔄 Procesando pago automáticamente para session_id: {session_id}")
            result = await stripe_service.handle_successful_payment(db, session_id)
            
            if result.success:
                payment_processed = True
                membership_info = {
                    'expires_at': result.membership_expires_at,
                    'message': result.message
                }
                logger.info(f"✅ Pago procesado exitosamente: {session_id}")
            else:
                error_message = result.message or "Error procesando el pago"
                logger.error(f"❌ Error procesando pago: {session_id} - {error_message}")
                
        except Exception as e:
            error_message = f"Error procesando el pago: {str(e)}"
            logger.error(f"❌ Excepción procesando pago {session_id}: {str(e)}")
    
    # Generar contenido HTML dinámico
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{'¡Pago Exitoso!' if payment_processed else 'Procesando Pago...' if session_id else 'Confirmación de Pago'} - GymAPI</title>
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
            .error-icon {{
                font-size: 4rem;
                color: #EF4444;
                margin-bottom: 1rem;
            }}
            .processing-icon {{
                font-size: 4rem;
                color: #F59E0B;
                margin-bottom: 1rem;
                animation: spin 2s linear infinite;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
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
            .membership-info {{
                background: #ECFDF5;
                border: 1px solid #10B981;
                padding: 1rem;
                border-radius: 8px;
                margin: 1rem 0;
                color: #065F46;
            }}
            .error-info {{
                background: #FEF2F2;
                border: 1px solid #EF4444;
                padding: 1rem;
                border-radius: 8px;
                margin: 1rem 0;
                color: #991B1B;
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
                margin: 0 10px;
            }}
            .btn:hover {{
                background: #2563EB;
            }}
            .btn-success {{
                background: #10B981;
            }}
            .btn-success:hover {{
                background: #059669;
            }}
            .btn-retry {{
                background: #F59E0B;
            }}
            .btn-retry:hover {{
                background: #D97706;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            {_generate_page_content(payment_processed, membership_info, error_message, session_id)}
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content, status_code=200)


def _generate_page_content(payment_processed: bool, membership_info: dict, error_message: str, session_id: str) -> str:
    """Genera el contenido dinámico de la página según el estado del pago"""
    
    if payment_processed and membership_info:
        # Pago procesado exitosamente
        expires_text = ""
        if membership_info.get('expires_at'):
            from datetime import datetime
            try:
                expires_date = datetime.fromisoformat(membership_info['expires_at'].replace('Z', '+00:00'))
                expires_text = f"<p><strong>Tu membresía expira el:</strong> {expires_date.strftime('%d/%m/%Y a las %H:%M')}</p>"
            except:
                expires_text = f"<p><strong>Fecha de expiración:</strong> {membership_info['expires_at']}</p>"
        
        return f"""
            <div class="success-icon">✅</div>
            <h1>¡Pago Completado!</h1>
            <div class="membership-info">
                <p><strong>✅ Tu membresía ha sido activada exitosamente</strong></p>
                {expires_text}
                <p>Ya puedes disfrutar de todos los beneficios de tu plan.</p>
            </div>
            <p>Recibirás una notificación de confirmación en tu dispositivo.</p>
            {'<div class="session-info">ID de Sesión: ' + session_id + '</div>' if session_id else ''}
            <a href="/" class="btn btn-success">Ir a la App</a>
            <a href="/membership/my-status" class="btn">Ver Mi Membresía</a>
        """
    
    elif error_message:
        # Error procesando el pago
        return f"""
            <div class="error-icon">❌</div>
            <h1>Error Procesando Pago</h1>
            <div class="error-info">
                <p><strong>❌ Hubo un problema procesando tu pago:</strong></p>
                <p>{error_message}</p>
            </div>
            <p>Por favor, contacta con el soporte técnico si el problema persiste.</p>
            {'<div class="session-info">ID de Sesión: ' + session_id + '</div>' if session_id else ''}
            <a href="/" class="btn">Volver a la App</a>
            <a href="/membership/plans" class="btn btn-retry">Ver Planes</a>
        """
    
    elif session_id:
        # Session ID presente pero no procesado (no debería ocurrir)
        return f"""
            <div class="processing-icon">⏳</div>
            <h1>Procesando Pago...</h1>
            <p>Estamos procesando tu pago. Por favor, espera un momento.</p>
            <div class="session-info">ID de Sesión: {session_id}</div>
            <p>Si esta página no se actualiza automáticamente, por favor contacta con soporte.</p>
            <a href="/" class="btn">Volver a la App</a>
            <script>
                // Recargar la página después de 3 segundos para reintentar el procesamiento
                setTimeout(function() {{
                    window.location.reload();
                }}, 3000);
            </script>
        """
    
    else:
        # No hay session_id - página genérica
        return f"""
            <div class="success-icon">✅</div>
            <h1>¡Pago Completado!</h1>
            <p>Tu pago ha sido procesado exitosamente.</p>
            <p>Si has comprado una membresía, debería estar activa en unos minutos.</p>
            <a href="/" class="btn">Volver a la App</a>
            <a href="/membership/my-status" class="btn">Ver Mi Membresía</a>
        """


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