"""
Modelos de interacciones con posts: likes, comentarios y reportes.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLAlchemyEnum, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.db.base_class import Base


class ReportReason(str, enum.Enum):
    """Razones para reportar un post o comentario"""
    SPAM = "spam"
    INAPPROPRIATE = "inappropriate"  # Contenido inapropiado
    HARASSMENT = "harassment"  # Acoso o bullying
    FALSE_INFO = "false_information"  # Información falsa
    HATE_SPEECH = "hate_speech"  # Discurso de odio
    VIOLENCE = "violence"  # Contenido violento
    OTHER = "other"


class PostLike(Base):
    """
    Likes en posts.
    Un usuario solo puede dar un like por post.
    """
    __tablename__ = "post_likes"
    __table_args__ = (
        UniqueConstraint('post_id', 'user_id', name='unique_post_like_user'),
        Index('ix_post_likes_gym_user', 'gym_id', 'user_id'),  # Para obtener likes del usuario
    )

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)  # Para multi-tenant

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relaciones
    post = relationship("Post", back_populates="likes")
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<PostLike(id={self.id}, post_id={self.post_id}, user_id={self.user_id})>"


class PostComment(Base):
    """
    Comentarios en posts.
    Soporta comentarios simples (sin anidamiento en v1).
    """
    __tablename__ = "post_comments"
    __table_args__ = (
        Index('ix_post_comments_post_created', 'post_id', 'created_at'),
        Index('ix_post_comments_user', 'user_id'),
    )

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)  # Para multi-tenant

    # Contenido
    comment_text = Column(Text, nullable=False)  # Texto del comentario

    # Edición
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime, nullable=True)

    # Control de estado
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    # Estadísticas
    like_count = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relaciones
    post = relationship("Post", back_populates="comments")
    user = relationship("User", foreign_keys=[user_id])
    likes = relationship("PostCommentLike", back_populates="comment", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PostComment(id={self.id}, post_id={self.post_id}, user_id={self.user_id})>"


class PostCommentLike(Base):
    """
    Likes en comentarios de posts.
    Un usuario solo puede dar un like por comentario.
    """
    __tablename__ = "post_comment_likes"
    __table_args__ = (
        UniqueConstraint('comment_id', 'user_id', name='unique_comment_like_user'),
    )

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("post_comments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relaciones
    comment = relationship("PostComment", back_populates="likes")
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<PostCommentLike(id={self.id}, comment_id={self.comment_id}, user_id={self.user_id})>"


class PostReport(Base):
    """
    Reportes de posts inapropiados.
    Sistema de moderación para contenido reportado por usuarios.
    """
    __tablename__ = "post_reports"
    __table_args__ = (
        Index('ix_post_reports_reviewed', 'is_reviewed'),
    )

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    reporter_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)

    # Razón del reporte
    reason = Column(SQLAlchemyEnum(ReportReason), nullable=False)
    description = Column(Text, nullable=True)  # Detalles adicionales opcionales

    # Revisión del reporte
    is_reviewed = Column(Boolean, default=False, index=True)
    reviewed_by = Column(Integer, ForeignKey("user.id"), nullable=True)  # Admin que revisó
    reviewed_at = Column(DateTime, nullable=True)
    action_taken = Column(String(100), nullable=True)  # "deleted", "warning", "no_action"

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relaciones
    post = relationship("Post", back_populates="reports")
    reporter = relationship("User", foreign_keys=[reporter_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])

    def __repr__(self):
        return f"<PostReport(id={self.id}, post_id={self.post_id}, reason={self.reason})>"


class PostView(Base):
    """
    Tracking de vistas de posts para deduplicación en el feed.

    Registra cuando un usuario visualiza un post para:
    - Evitar mostrar posts ya vistos en el feed rankeado
    - Medir engagement real (view-through rate)
    - Calcular métricas de popularidad
    """
    __tablename__ = "post_views"
    __table_args__ = (
        Index('ix_post_views_user_post', 'user_id', 'post_id'),
        Index('ix_post_views_gym_user', 'gym_id', 'user_id'),
        Index('ix_post_views_post_date', 'post_id', 'viewed_at'),
    )

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)

    # Tracking de vista
    viewed_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    view_duration_seconds = Column(Integer, nullable=True)  # Tiempo en vista (futuro)
    device_type = Column(String(50), nullable=True)  # iOS, Android, Web

    # Relaciones
    post = relationship("Post", back_populates="views")
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<PostView(id={self.id}, post_id={self.post_id}, user_id={self.user_id})>"
