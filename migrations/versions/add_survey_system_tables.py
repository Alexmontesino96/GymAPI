"""Add survey system tables

Revision ID: add_survey_system
Revises: c26b3d4e5f60
Create Date: 2025-08-24 13:24:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_survey_system'
down_revision = 'c26b3d4e5f60'
branch_labels = None
depends_on = None


def upgrade():
    # Create survey status enum if not exists
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE surveystatus AS ENUM ('DRAFT', 'PUBLISHED', 'CLOSED', 'ARCHIVED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create question type enum if not exists
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE questiontype AS ENUM (
                'TEXT', 'TEXTAREA', 'RADIO', 'CHECKBOX', 'SELECT', 
                'SCALE', 'DATE', 'TIME', 'NUMBER', 'EMAIL', 
                'PHONE', 'YES_NO', 'NPS'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create surveys table
    op.create_table('surveys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gym_id', sa.Integer(), nullable=False),
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('status', postgresql.ENUM('DRAFT', 'PUBLISHED', 'CLOSED', 'ARCHIVED', name='surveystatus'), nullable=False),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_anonymous', sa.Boolean(), nullable=True),
        sa.Column('allow_multiple', sa.Boolean(), nullable=True),
        sa.Column('randomize_questions', sa.Boolean(), nullable=True),
        sa.Column('show_progress', sa.Boolean(), nullable=True),
        sa.Column('thank_you_message', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('target_audience', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['creator_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['gym_id'], ['gyms.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_surveys_gym_id'), 'surveys', ['gym_id'], unique=False)
    op.create_index(op.f('ix_surveys_id'), 'surveys', ['id'], unique=False)
    op.create_index(op.f('ix_surveys_status'), 'surveys', ['status'], unique=False)
    
    # Create survey_questions table
    op.create_table('survey_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('survey_id', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_type', postgresql.ENUM('TEXT', 'TEXTAREA', 'RADIO', 'CHECKBOX', 'SELECT', 'SCALE', 'DATE', 'TIME', 'NUMBER', 'EMAIL', 'PHONE', 'YES_NO', 'NPS', name='questiontype'), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=True),
        sa.Column('order', sa.Integer(), nullable=True),
        sa.Column('help_text', sa.Text(), nullable=True),
        sa.Column('placeholder', sa.String(length=200), nullable=True),
        sa.Column('min_value', sa.Float(), nullable=True),
        sa.Column('max_value', sa.Float(), nullable=True),
        sa.Column('min_length', sa.Integer(), nullable=True),
        sa.Column('max_length', sa.Integer(), nullable=True),
        sa.Column('regex_validation', sa.String(length=500), nullable=True),
        sa.Column('allow_other', sa.Boolean(), nullable=True),
        sa.Column('depends_on_question_id', sa.Integer(), nullable=True),
        sa.Column('depends_on_answer', sa.JSON(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['depends_on_question_id'], ['survey_questions.id'], ),
        sa.ForeignKeyConstraint(['survey_id'], ['surveys.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_survey_questions_id'), 'survey_questions', ['id'], unique=False)
    op.create_index(op.f('ix_survey_questions_survey_id'), 'survey_questions', ['survey_id'], unique=False)
    
    # Create question_choices table
    op.create_table('question_choices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('choice_text', sa.String(length=500), nullable=False),
        sa.Column('choice_value', sa.String(length=100), nullable=True),
        sa.Column('order', sa.Integer(), nullable=True),
        sa.Column('next_question_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['next_question_id'], ['survey_questions.id'], ),
        sa.ForeignKeyConstraint(['question_id'], ['survey_questions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_question_choices_id'), 'question_choices', ['id'], unique=False)
    op.create_index(op.f('ix_question_choices_question_id'), 'question_choices', ['question_id'], unique=False)
    
    # Create survey_responses table
    op.create_table('survey_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('survey_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('gym_id', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_complete', sa.Boolean(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('event_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
        sa.ForeignKeyConstraint(['gym_id'], ['gyms.id'], ),
        sa.ForeignKeyConstraint(['survey_id'], ['surveys.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_survey_responses_gym_id'), 'survey_responses', ['gym_id'], unique=False)
    op.create_index(op.f('ix_survey_responses_id'), 'survey_responses', ['id'], unique=False)
    op.create_index(op.f('ix_survey_responses_survey_id'), 'survey_responses', ['survey_id'], unique=False)
    op.create_index(op.f('ix_survey_responses_user_id'), 'survey_responses', ['user_id'], unique=False)
    
    # Create survey_answers table
    op.create_table('survey_answers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('response_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('text_answer', sa.Text(), nullable=True),
        sa.Column('choice_id', sa.Integer(), nullable=True),
        sa.Column('choice_ids', sa.JSON(), nullable=True),
        sa.Column('number_answer', sa.Float(), nullable=True),
        sa.Column('date_answer', sa.DateTime(timezone=True), nullable=True),
        sa.Column('boolean_answer', sa.Boolean(), nullable=True),
        sa.Column('other_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['choice_id'], ['question_choices.id'], ),
        sa.ForeignKeyConstraint(['question_id'], ['survey_questions.id'], ),
        sa.ForeignKeyConstraint(['response_id'], ['survey_responses.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_survey_answers_id'), 'survey_answers', ['id'], unique=False)
    op.create_index(op.f('ix_survey_answers_question_id'), 'survey_answers', ['question_id'], unique=False)
    op.create_index(op.f('ix_survey_answers_response_id'), 'survey_answers', ['response_id'], unique=False)
    
    # Create survey_templates table
    op.create_table('survey_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gym_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('template_data', sa.JSON(), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['gym_id'], ['gyms.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_survey_templates_gym_id'), 'survey_templates', ['gym_id'], unique=False)
    op.create_index(op.f('ix_survey_templates_id'), 'survey_templates', ['id'], unique=False)


def downgrade():
    # Drop tables
    op.drop_index(op.f('ix_survey_templates_id'), table_name='survey_templates')
    op.drop_index(op.f('ix_survey_templates_gym_id'), table_name='survey_templates')
    op.drop_table('survey_templates')
    
    op.drop_index(op.f('ix_survey_answers_response_id'), table_name='survey_answers')
    op.drop_index(op.f('ix_survey_answers_question_id'), table_name='survey_answers')
    op.drop_index(op.f('ix_survey_answers_id'), table_name='survey_answers')
    op.drop_table('survey_answers')
    
    op.drop_index(op.f('ix_survey_responses_user_id'), table_name='survey_responses')
    op.drop_index(op.f('ix_survey_responses_survey_id'), table_name='survey_responses')
    op.drop_index(op.f('ix_survey_responses_id'), table_name='survey_responses')
    op.drop_index(op.f('ix_survey_responses_gym_id'), table_name='survey_responses')
    op.drop_table('survey_responses')
    
    op.drop_index(op.f('ix_question_choices_question_id'), table_name='question_choices')
    op.drop_index(op.f('ix_question_choices_id'), table_name='question_choices')
    op.drop_table('question_choices')
    
    op.drop_index(op.f('ix_survey_questions_survey_id'), table_name='survey_questions')
    op.drop_index(op.f('ix_survey_questions_id'), table_name='survey_questions')
    op.drop_table('survey_questions')
    
    op.drop_index(op.f('ix_surveys_status'), table_name='surveys')
    op.drop_index(op.f('ix_surveys_id'), table_name='surveys')
    op.drop_index(op.f('ix_surveys_gym_id'), table_name='surveys')
    op.drop_table('surveys')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS questiontype')
    op.execute('DROP TYPE IF EXISTS surveystatus')