"""
Modelo de seguimiento entre usuarios (follow/following).

Sistema tipo Instagram donde usuarios pueden seguirse entre sí.
Usado para calcular social affinity en el algoritmo de feed ranking.
"""

from sqlalchemy import Column, Integer, ForeignKey, DateTime, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

from app.db.base_class import Base


class UserFollow(Base):
    """
    Relación de seguimiento entre usuarios.

    Un usuario (follower) sigue a otro usuario (following).
    Usado para personalización de feed y social affinity scoring.
    """
    __tablename__ = "user_follows"
    __table_args__ = (
        UniqueConstraint('follower_id', 'following_id', 'gym_id', name='unique_user_follow'),
        Index('ix_user_follows_follower_gym', 'follower_id', 'gym_id'),
        Index('ix_user_follows_following_gym', 'following_id', 'gym_id'),
        Index('ix_user_follows_active', 'is_active'),
    )

    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    following_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)

    # Estado
    is_active = Column(Boolean, default=True, nullable=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relaciones
    follower = relationship("User", foreign_keys=[follower_id], back_populates="following")
    following_user = relationship("User", foreign_keys=[following_id], back_populates="followers")

    def __repr__(self):
        return f"<UserFollow(id={self.id}, follower={self.follower_id}, following={self.following_id})>"
