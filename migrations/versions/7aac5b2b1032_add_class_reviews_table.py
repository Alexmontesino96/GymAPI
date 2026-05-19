"""add_class_reviews_table

Revision ID: 7aac5b2b1032
Revises: f8d4b9a3c2e1
Create Date: 2026-05-18 21:08:05.176070

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '7aac5b2b1032'
down_revision = 'f8d4b9a3c2e1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('class_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('gym_id', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('rating >= 1 AND rating <= 5', name='check_rating_range'),
        sa.ForeignKeyConstraint(['gym_id'], ['gyms.id'], ),
        sa.ForeignKeyConstraint(['member_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['session_id'], ['class_session.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'member_id', name='uq_class_review_session_member')
    )
    op.create_index(op.f('ix_class_reviews_gym_id'), 'class_reviews', ['gym_id'], unique=False)
    op.create_index('ix_class_reviews_gym_session', 'class_reviews', ['gym_id', 'session_id'], unique=False)
    op.create_index(op.f('ix_class_reviews_id'), 'class_reviews', ['id'], unique=False)
    op.create_index(op.f('ix_class_reviews_member_id'), 'class_reviews', ['member_id'], unique=False)
    op.create_index(op.f('ix_class_reviews_session_id'), 'class_reviews', ['session_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_class_reviews_session_id'), table_name='class_reviews')
    op.drop_index(op.f('ix_class_reviews_member_id'), table_name='class_reviews')
    op.drop_index(op.f('ix_class_reviews_id'), table_name='class_reviews')
    op.drop_index('ix_class_reviews_gym_session', table_name='class_reviews')
    op.drop_index(op.f('ix_class_reviews_gym_id'), table_name='class_reviews')
    op.drop_table('class_reviews')
