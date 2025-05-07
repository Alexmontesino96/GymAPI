from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any
import hmac
import hashlib
import logging

from app.db.session import get_db
from app.core.config import settings
from app.services.notification_service import notification_service
from app.services.chat import chat_service

router = APIRouter()
logger = logging.getLogger(__name__)

async def verify_stream_webhook_signature(request: Request):
    """
    Verify the webhook signature from GetStream.
    """
    if not settings.STREAM_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stream webhook secret not configured"
        )
    
    signature = request.headers.get("X-Signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature"
        )
    
    # Get raw body
    body = await request.body()
    
    # Calculate expected signature
    expected_signature = hmac.new(
        settings.STREAM_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )

@router.post("/stream/new-message", status_code=status.HTTP_200_OK)
async def handle_new_message(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(verify_stream_webhook_signature)
):
    """
    Webhook endpoint for handling new messages from GetStream.
    When a new message is created, this endpoint will be called to send notifications.
    """
    try:
        # Get webhook payload
        payload = await request.json()
        
        # Extract message data
        message = payload.get("message", {})
        channel = payload.get("channel", {})
        
        if not message or not channel:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook payload"
            )
        
        # Get channel type and id
        channel_type = channel.get("type")
        channel_id = channel.get("id")
        
        # Get message sender
        user_id = message.get("user", {}).get("id")
        
        if not all([channel_type, channel_id, user_id]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields"
            )
            
        # Get channel members to notify (excluding sender)
        channel_members = await chat_service.get_channel_members(channel_type, channel_id)
        recipients = [member for member in channel_members if member != user_id]
        
        if not recipients:
            logger.info(f"No recipients to notify for message in channel {channel_id}")
            return {"status": "success", "message": "No recipients to notify"}
        
        # Prepare notification data
        notification_data = {
            "title": f"New message in {channel.get('name', 'chat')}",
            "message": message.get("text", "You have a new message"),
            "data": {
                "channel_id": channel_id,
                "channel_type": channel_type,
                "message_id": message.get("id"),
                "sender_id": user_id
            }
        }
        
        # Send notifications in background
        background_tasks.add_task(
            notification_service.send_notification_to_users,
            db,
            recipients,
            notification_data
        )
        
        return {
            "status": "success",
            "message": f"Notifications queued for {len(recipients)} recipients"
        }
        
    except Exception as e:
        logger.error(f"Error processing stream webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}"
        ) 