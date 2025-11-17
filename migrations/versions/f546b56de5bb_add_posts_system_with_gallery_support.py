"""add posts system with gallery support

Revision ID: f546b56de5bb
Revises: add_survey_system
Create Date: 2025-11-09 21:24:20.449618

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f546b56de5bb'
down_revision = 'add_survey_system'
branch_labels = None
depends_on = None


def upgrade():
    # Crear tabla posts
    op.create_table(
        'posts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gym_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('stream_activity_id', sa.String(), nullable=True),
        sa.Column('post_type', sa.Enum('SINGLE_IMAGE', 'GALLERY', 'VIDEO', 'WORKOUT', name='posttype'), nullable=False),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('location', sa.String(length=100), nullable=True),
        sa.Column('workout_data', sa.JSON(), nullable=True),
        sa.Column('privacy', sa.Enum('PUBLIC', 'PRIVATE', name='postprivacy'), nullable=False),
        sa.Column('is_edited', sa.Boolean(), nullable=True),
        sa.Column('edited_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('like_count', sa.Integer(), nullable=False),
        sa.Column('comment_count', sa.Integer(), nullable=False),
        sa.Column('view_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['gym_id'], ['gyms.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_posts_created_at'), 'posts', ['created_at'], unique=False)
    op.create_index(op.f('ix_posts_gym_id'), 'posts', ['gym_id'], unique=False)
    op.create_index(op.f('ix_posts_id'), 'posts', ['id'], unique=False)
    op.create_index(op.f('ix_posts_stream_activity_id'), 'posts', ['stream_activity_id'], unique=True)
    op.create_index(op.f('ix_posts_user_id'), 'posts', ['user_id'], unique=False)
    op.create_index('ix_posts_gym_created', 'posts', ['gym_id', 'created_at'], unique=False)
    op.create_index('ix_posts_gym_engagement', 'posts', ['gym_id', 'like_count', 'comment_count'], unique=False)
    op.create_index('ix_posts_location', 'posts', ['gym_id', 'location'], unique=False)

    # Crear tabla post_media
    op.create_table(
        'post_media',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('media_url', sa.String(), nullable=False),
        sa.Column('thumbnail_url', sa.String(), nullable=True),
        sa.Column('media_type', sa.String(length=20), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_post_media_id'), 'post_media', ['id'], unique=False)
    op.create_index(op.f('ix_post_media_post_id'), 'post_media', ['post_id'], unique=False)
    op.create_index('ix_post_media_post_order', 'post_media', ['post_id', 'display_order'], unique=False)

    # Crear tabla post_tags
    op.create_table(
        'post_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('tag_type', sa.Enum('MENTION', 'EVENT', 'SESSION', name='tagtype'), nullable=False),
        sa.Column('tag_value', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('post_id', 'tag_type', 'tag_value', name='unique_post_tag')
    )
    op.create_index(op.f('ix_post_tags_id'), 'post_tags', ['id'], unique=False)
    op.create_index(op.f('ix_post_tags_post_id'), 'post_tags', ['post_id'], unique=False)
    op.create_index('ix_post_tags_type_value', 'post_tags', ['tag_type', 'tag_value'], unique=False)

    # Crear tabla post_likes
    op.create_table(
        'post_likes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('gym_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['gym_id'], ['gyms.id'], ),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('post_id', 'user_id', name='unique_post_like_user')
    )
    op.create_index(op.f('ix_post_likes_id'), 'post_likes', ['id'], unique=False)
    op.create_index(op.f('ix_post_likes_post_id'), 'post_likes', ['post_id'], unique=False)
    op.create_index(op.f('ix_post_likes_user_id'), 'post_likes', ['user_id'], unique=False)
    op.create_index(op.f('ix_post_likes_gym_id'), 'post_likes', ['gym_id'], unique=False)
    op.create_index('ix_post_likes_gym_user', 'post_likes', ['gym_id', 'user_id'], unique=False)

    # Crear tabla post_comments
    op.create_table(
        'post_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('gym_id', sa.Integer(), nullable=False),
        sa.Column('comment_text', sa.Text(), nullable=False),
        sa.Column('is_edited', sa.Boolean(), nullable=True),
        sa.Column('edited_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('like_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['gym_id'], ['gyms.id'], ),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_post_comments_id'), 'post_comments', ['id'], unique=False)
    op.create_index(op.f('ix_post_comments_post_id'), 'post_comments', ['post_id'], unique=False)
    op.create_index(op.f('ix_post_comments_gym_id'), 'post_comments', ['gym_id'], unique=False)
    op.create_index('ix_post_comments_post_created', 'post_comments', ['post_id', 'created_at'], unique=False)
    op.create_index('ix_post_comments_user', 'post_comments', ['user_id'], unique=False)

    # Crear tabla post_comment_likes
    op.create_table(
        'post_comment_likes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('comment_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['comment_id'], ['post_comments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('comment_id', 'user_id', name='unique_comment_like_user')
    )
    op.create_index(op.f('ix_post_comment_likes_id'), 'post_comment_likes', ['id'], unique=False)
    op.create_index(op.f('ix_post_comment_likes_comment_id'), 'post_comment_likes', ['comment_id'], unique=False)
    op.create_index(op.f('ix_post_comment_likes_user_id'), 'post_comment_likes', ['user_id'], unique=False)

    # Crear tabla post_reports
    op.create_table(
        'post_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('reporter_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Enum('SPAM', 'INAPPROPRIATE', 'HARASSMENT', 'FALSE_INFO', 'HATE_SPEECH', 'VIOLENCE', 'OTHER', name='reportreason'), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_reviewed', sa.Boolean(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('action_taken', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reporter_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_post_reports_id'), 'post_reports', ['id'], unique=False)
    op.create_index(op.f('ix_post_reports_post_id'), 'post_reports', ['post_id'], unique=False)
    op.create_index(op.f('ix_post_reports_reporter_id'), 'post_reports', ['reporter_id'], unique=False)
    op.create_index('ix_post_reports_reviewed', 'post_reports', ['is_reviewed'], unique=False)


def downgrade():
    # Eliminar tablas en orden inverso
    op.drop_index('ix_post_reports_reviewed', table_name='post_reports')
    op.drop_index(op.f('ix_post_reports_reporter_id'), table_name='post_reports')
    op.drop_index(op.f('ix_post_reports_post_id'), table_name='post_reports')
    op.drop_index(op.f('ix_post_reports_id'), table_name='post_reports')
    op.drop_table('post_reports')

    op.drop_index(op.f('ix_post_comment_likes_user_id'), table_name='post_comment_likes')
    op.drop_index(op.f('ix_post_comment_likes_comment_id'), table_name='post_comment_likes')
    op.drop_index(op.f('ix_post_comment_likes_id'), table_name='post_comment_likes')
    op.drop_table('post_comment_likes')

    op.drop_index('ix_post_comments_user', table_name='post_comments')
    op.drop_index('ix_post_comments_post_created', table_name='post_comments')
    op.drop_index(op.f('ix_post_comments_gym_id'), table_name='post_comments')
    op.drop_index(op.f('ix_post_comments_post_id'), table_name='post_comments')
    op.drop_index(op.f('ix_post_comments_id'), table_name='post_comments')
    op.drop_table('post_comments')

    op.drop_index('ix_post_likes_gym_user', table_name='post_likes')
    op.drop_index(op.f('ix_post_likes_gym_id'), table_name='post_likes')
    op.drop_index(op.f('ix_post_likes_user_id'), table_name='post_likes')
    op.drop_index(op.f('ix_post_likes_post_id'), table_name='post_likes')
    op.drop_index(op.f('ix_post_likes_id'), table_name='post_likes')
    op.drop_table('post_likes')

    op.drop_index('ix_post_tags_type_value', table_name='post_tags')
    op.drop_index(op.f('ix_post_tags_post_id'), table_name='post_tags')
    op.drop_index(op.f('ix_post_tags_id'), table_name='post_tags')
    op.drop_table('post_tags')

    op.drop_index('ix_post_media_post_order', table_name='post_media')
    op.drop_index(op.f('ix_post_media_post_id'), table_name='post_media')
    op.drop_index(op.f('ix_post_media_id'), table_name='post_media')
    op.drop_table('post_media')

    op.drop_index('ix_posts_location', table_name='posts')
    op.drop_index('ix_posts_gym_engagement', table_name='posts')
    op.drop_index('ix_posts_gym_created', table_name='posts')
    op.drop_index(op.f('ix_posts_user_id'), table_name='posts')
    op.drop_index(op.f('ix_posts_stream_activity_id'), table_name='posts')
    op.drop_index(op.f('ix_posts_id'), table_name='posts')
    op.drop_index(op.f('ix_posts_gym_id'), table_name='posts')
    op.drop_index(op.f('ix_posts_created_at'), table_name='posts')
    op.drop_table('posts')

    # Eliminar enums
    sa.Enum(name='reportreason').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='tagtype').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='postprivacy').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='posttype').drop(op.get_bind(), checkfirst=False) 