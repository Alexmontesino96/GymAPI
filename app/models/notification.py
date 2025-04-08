from sqlalchemy import Column, String, DateTime, Boolean, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.base_class import Base

class DeviceToken(Base):
    """Modelo para almacenar tokens de dispositivos para notificaciones push"""
    
    __tablename__ = "device_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    device_token = Column(String(255), nullable=False) 
    platform = Column(String(20), nullable=False)  # 'ios', 'android', 'web'
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('user_id', 'device_token', name='uq_user_device_token'),
        Index('idx_device_token', 'device_token'),
    ) 