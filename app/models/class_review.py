"""
Class Review Model

Sistema de reviews con estrellas para sesiones de clase.
"""

from sqlalchemy import Column, Integer, Text, ForeignKey, DateTime, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class ClassReview(Base):
    """Review de una sesión de clase por un miembro"""
    __tablename__ = "class_reviews"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("class_session.id"), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    session = relationship("ClassSession", backref="reviews")
    member = relationship("User")
    gym = relationship("Gym")

    __table_args__ = (
        UniqueConstraint('session_id', 'member_id', name='uq_class_review_session_member'),
        CheckConstraint('rating >= 1 AND rating <= 5', name='check_rating_range'),
        Index('ix_class_reviews_gym_session', 'gym_id', 'session_id'),
    )
