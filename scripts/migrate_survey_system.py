#!/usr/bin/env python
"""
Script to create survey system tables in the database.

Usage:
    python scripts/migrate_survey_system.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.session import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_survey_tables():
    """Create all survey system tables"""
    
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # Check if tables already exist
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('surveys', 'survey_questions', 'question_choices', 
                                   'survey_responses', 'survey_answers', 'survey_templates')
            """))
            existing_tables = [row[0] for row in result]
            
            if existing_tables:
                logger.warning(f"Some tables already exist: {existing_tables}")
                response = input("Do you want to continue? This will skip existing tables (y/n): ")
                if response.lower() != 'y':
                    logger.info("Migration cancelled")
                    return
            
            # Create ENUMs if they don't exist
            logger.info("Creating ENUM types...")
            conn.execute(text("""
                DO $$ BEGIN
                    CREATE TYPE surveystatus AS ENUM ('DRAFT', 'PUBLISHED', 'CLOSED', 'ARCHIVED');
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """))
            
            conn.execute(text("""
                DO $$ BEGIN
                    CREATE TYPE questiontype AS ENUM (
                        'TEXT', 'TEXTAREA', 'RADIO', 'CHECKBOX', 'SELECT', 
                        'SCALE', 'DATE', 'TIME', 'NUMBER', 'EMAIL', 
                        'PHONE', 'YES_NO', 'NPS'
                    );
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """))
            logger.info("✓ ENUM types created")
            
            # Create surveys table
            if 'surveys' not in existing_tables:
                logger.info("Creating surveys table...")
                conn.execute(text("""
                    CREATE TABLE surveys (
                        id SERIAL PRIMARY KEY,
                        gym_id INTEGER NOT NULL REFERENCES gyms(id),
                        creator_id INTEGER NOT NULL REFERENCES "user"(id),
                        title VARCHAR(200) NOT NULL,
                        description TEXT,
                        instructions TEXT,
                        status surveystatus NOT NULL DEFAULT 'DRAFT',
                        start_date TIMESTAMP WITH TIME ZONE,
                        end_date TIMESTAMP WITH TIME ZONE,
                        is_anonymous BOOLEAN DEFAULT FALSE,
                        allow_multiple BOOLEAN DEFAULT FALSE,
                        randomize_questions BOOLEAN DEFAULT FALSE,
                        show_progress BOOLEAN DEFAULT TRUE,
                        thank_you_message TEXT DEFAULT 'Gracias por completar la encuesta',
                        tags JSON,
                        target_audience VARCHAR(100),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE,
                        published_at TIMESTAMP WITH TIME ZONE
                    );
                    
                    CREATE INDEX idx_surveys_gym_id ON surveys(gym_id);
                    CREATE INDEX idx_surveys_status ON surveys(status);
                    CREATE INDEX idx_surveys_creator_id ON surveys(creator_id);
                """))
                logger.info("✓ surveys table created")
            
            # Create survey_questions table
            if 'survey_questions' not in existing_tables:
                logger.info("Creating survey_questions table...")
                conn.execute(text("""
                    CREATE TABLE survey_questions (
                        id SERIAL PRIMARY KEY,
                        survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
                        question_text TEXT NOT NULL,
                        question_type questiontype NOT NULL,
                        is_required BOOLEAN DEFAULT FALSE,
                        "order" INTEGER DEFAULT 0,
                        help_text TEXT,
                        placeholder VARCHAR(200),
                        min_value FLOAT,
                        max_value FLOAT,
                        min_length INTEGER,
                        max_length INTEGER,
                        regex_validation VARCHAR(500),
                        allow_other BOOLEAN DEFAULT FALSE,
                        depends_on_question_id INTEGER REFERENCES survey_questions(id),
                        depends_on_answer JSON,
                        category VARCHAR(100),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE
                    );
                    
                    CREATE INDEX idx_survey_questions_survey_id ON survey_questions(survey_id);
                """))
                logger.info("✓ survey_questions table created")
            
            # Create question_choices table
            if 'question_choices' not in existing_tables:
                logger.info("Creating question_choices table...")
                conn.execute(text("""
                    CREATE TABLE question_choices (
                        id SERIAL PRIMARY KEY,
                        question_id INTEGER NOT NULL REFERENCES survey_questions(id) ON DELETE CASCADE,
                        choice_text VARCHAR(500) NOT NULL,
                        choice_value VARCHAR(100),
                        "order" INTEGER DEFAULT 0,
                        next_question_id INTEGER REFERENCES survey_questions(id),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE INDEX idx_question_choices_question_id ON question_choices(question_id);
                """))
                logger.info("✓ question_choices table created")
            
            # Create survey_responses table
            if 'survey_responses' not in existing_tables:
                logger.info("Creating survey_responses table...")
                conn.execute(text("""
                    CREATE TABLE survey_responses (
                        id SERIAL PRIMARY KEY,
                        survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
                        user_id INTEGER REFERENCES "user"(id),
                        gym_id INTEGER NOT NULL REFERENCES gyms(id),
                        started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP WITH TIME ZONE,
                        is_complete BOOLEAN DEFAULT FALSE,
                        ip_address VARCHAR(45),
                        user_agent VARCHAR(500),
                        event_id INTEGER REFERENCES events(id),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE
                    );
                    
                    CREATE INDEX idx_survey_responses_survey_id ON survey_responses(survey_id);
                    CREATE INDEX idx_survey_responses_user_id ON survey_responses(user_id);
                    CREATE INDEX idx_survey_responses_gym_id ON survey_responses(gym_id);
                    CREATE INDEX idx_survey_responses_event_id ON survey_responses(event_id);
                """))
                logger.info("✓ survey_responses table created")
            
            # Create survey_answers table
            if 'survey_answers' not in existing_tables:
                logger.info("Creating survey_answers table...")
                conn.execute(text("""
                    CREATE TABLE survey_answers (
                        id SERIAL PRIMARY KEY,
                        response_id INTEGER NOT NULL REFERENCES survey_responses(id) ON DELETE CASCADE,
                        question_id INTEGER NOT NULL REFERENCES survey_questions(id),
                        text_answer TEXT,
                        choice_id INTEGER REFERENCES question_choices(id),
                        choice_ids JSON,
                        number_answer FLOAT,
                        date_answer TIMESTAMP WITH TIME ZONE,
                        boolean_answer BOOLEAN,
                        other_text TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE
                    );
                    
                    CREATE INDEX idx_survey_answers_response_id ON survey_answers(response_id);
                    CREATE INDEX idx_survey_answers_question_id ON survey_answers(question_id);
                """))
                logger.info("✓ survey_answers table created")
            
            # Create survey_templates table
            if 'survey_templates' not in existing_tables:
                logger.info("Creating survey_templates table...")
                conn.execute(text("""
                    CREATE TABLE survey_templates (
                        id SERIAL PRIMARY KEY,
                        gym_id INTEGER REFERENCES gyms(id),
                        name VARCHAR(200) NOT NULL,
                        description TEXT,
                        category VARCHAR(100),
                        template_data JSON NOT NULL,
                        is_public BOOLEAN DEFAULT FALSE,
                        usage_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE
                    );
                    
                    CREATE INDEX idx_survey_templates_gym_id ON survey_templates(gym_id);
                    CREATE INDEX idx_survey_templates_category ON survey_templates(category);
                """))
                logger.info("✓ survey_templates table created")
            
            # Update alembic version table
            logger.info("Updating alembic version...")
            conn.execute(text("""
                INSERT INTO alembic_version (version_num) 
                VALUES ('add_survey_system')
                ON CONFLICT (version_num) DO NOTHING
            """))
            
            trans.commit()
            logger.info("\n✅ Survey system tables created successfully!")
            
            # Create sample templates
            create_sample_templates(conn)
            
        except Exception as e:
            trans.rollback()
            logger.error(f"Error creating tables: {e}")
            raise


def create_sample_templates(conn):
    """Create sample survey templates"""
    try:
        logger.info("\nCreating sample templates...")
        
        # Check if templates already exist
        result = conn.execute(text("SELECT COUNT(*) FROM survey_templates"))
        count = result.scalar()
        
        if count > 0:
            logger.info(f"Templates already exist ({count} found), skipping...")
            return
        
        # Customer Satisfaction Template
        conn.execute(text("""
            INSERT INTO survey_templates (name, description, category, is_public, template_data)
            VALUES (
                'Encuesta de Satisfacción del Cliente',
                'Plantilla estándar para medir la satisfacción del cliente con el gimnasio',
                'satisfaction',
                true,
                '{
                    "description": "Ayúdanos a mejorar tu experiencia en el gimnasio",
                    "instructions": "Por favor, tómate unos minutos para responder estas preguntas",
                    "is_anonymous": false,
                    "allow_multiple": false,
                    "questions": [
                        {
                            "question_text": "¿Qué tan satisfecho estás con nuestras instalaciones?",
                            "question_type": "SCALE",
                            "is_required": true,
                            "min_value": 1,
                            "max_value": 5,
                            "order": 0
                        },
                        {
                            "question_text": "¿Cómo calificarías la limpieza del gimnasio?",
                            "question_type": "RADIO",
                            "is_required": true,
                            "order": 1,
                            "choices": [
                                {"choice_text": "Excelente", "order": 0},
                                {"choice_text": "Buena", "order": 1},
                                {"choice_text": "Regular", "order": 2},
                                {"choice_text": "Mala", "order": 3}
                            ]
                        },
                        {
                            "question_text": "¿Recomendarías nuestro gimnasio a un amigo?",
                            "question_type": "NPS",
                            "is_required": true,
                            "min_value": 0,
                            "max_value": 10,
                            "order": 2
                        },
                        {
                            "question_text": "¿Qué podríamos mejorar?",
                            "question_type": "TEXTAREA",
                            "is_required": false,
                            "order": 3
                        }
                    ]
                }'::json
            )
        """))
        
        # Post-Event Feedback Template
        conn.execute(text("""
            INSERT INTO survey_templates (name, description, category, is_public, template_data)
            VALUES (
                'Feedback Post-Evento',
                'Plantilla para recopilar feedback después de un evento o clase',
                'feedback',
                true,
                '{
                    "description": "Cuéntanos tu experiencia en el evento",
                    "instructions": "Tu opinión nos ayuda a mejorar futuros eventos",
                    "is_anonymous": true,
                    "allow_multiple": false,
                    "questions": [
                        {
                            "question_text": "¿Cómo calificarías el evento en general?",
                            "question_type": "SCALE",
                            "is_required": true,
                            "min_value": 1,
                            "max_value": 5,
                            "order": 0
                        },
                        {
                            "question_text": "¿Qué fue lo que más te gustó?",
                            "question_type": "TEXT",
                            "is_required": false,
                            "order": 1
                        },
                        {
                            "question_text": "¿Asistirías a un evento similar en el futuro?",
                            "question_type": "YES_NO",
                            "is_required": true,
                            "order": 2
                        },
                        {
                            "question_text": "Sugerencias para mejorar",
                            "question_type": "TEXTAREA",
                            "is_required": false,
                            "order": 3
                        }
                    ]
                }'::json
            )
        """))
        
        # Trainer Evaluation Template
        conn.execute(text("""
            INSERT INTO survey_templates (name, description, category, is_public, template_data)
            VALUES (
                'Evaluación de Entrenador',
                'Plantilla para evaluar el desempeño de los entrenadores',
                'evaluation',
                true,
                '{
                    "description": "Evalúa a tu entrenador",
                    "instructions": "Tu feedback es confidencial y nos ayuda a mantener la calidad",
                    "is_anonymous": true,
                    "allow_multiple": true,
                    "target_audience": "members",
                    "questions": [
                        {
                            "question_text": "¿Cuánto tiempo llevas entrenando con este entrenador?",
                            "question_type": "RADIO",
                            "is_required": true,
                            "order": 0,
                            "choices": [
                                {"choice_text": "Menos de 1 mes", "order": 0},
                                {"choice_text": "1-3 meses", "order": 1},
                                {"choice_text": "3-6 meses", "order": 2},
                                {"choice_text": "Más de 6 meses", "order": 3}
                            ]
                        },
                        {
                            "question_text": "¿Qué aspectos evalúas del entrenador?",
                            "question_type": "CHECKBOX",
                            "is_required": true,
                            "order": 1,
                            "choices": [
                                {"choice_text": "Conocimiento técnico", "order": 0},
                                {"choice_text": "Puntualidad", "order": 1},
                                {"choice_text": "Motivación", "order": 2},
                                {"choice_text": "Comunicación", "order": 3},
                                {"choice_text": "Profesionalismo", "order": 4}
                            ]
                        },
                        {
                            "question_text": "Calificación general del entrenador",
                            "question_type": "SCALE",
                            "is_required": true,
                            "min_value": 1,
                            "max_value": 10,
                            "order": 2
                        },
                        {
                            "question_text": "Comentarios adicionales",
                            "question_type": "TEXTAREA",
                            "is_required": false,
                            "order": 3
                        }
                    ]
                }'::json
            )
        """))
        
        conn.commit()
        logger.info("✓ Sample templates created successfully!")
        
    except Exception as e:
        logger.error(f"Error creating sample templates: {e}")


def verify_installation():
    """Verify that all tables were created correctly"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('surveys', 'survey_questions', 'question_choices', 
                               'survey_responses', 'survey_answers', 'survey_templates')
            ORDER BY table_name
        """))
        
        tables = [row[0] for row in result]
        
        logger.info("\n📊 Verification Results:")
        logger.info(f"Tables created: {len(tables)}/6")
        for table in tables:
            logger.info(f"  ✓ {table}")
        
        # Count templates
        result = conn.execute(text("SELECT COUNT(*) FROM survey_templates"))
        template_count = result.scalar()
        logger.info(f"\nTemplates created: {template_count}")
        
        return len(tables) == 6


if __name__ == "__main__":
    try:
        logger.info("🚀 Starting survey system migration...")
        logger.info(f"Database: {engine.url}")
        
        create_survey_tables()
        
        if verify_installation():
            logger.info("\n✅ Migration completed successfully!")
            logger.info("\nYou can now use the survey system endpoints:")
            logger.info("  - GET  /api/v1/surveys/available - View available surveys")
            logger.info("  - POST /api/v1/surveys/ - Create new survey")
            logger.info("  - POST /api/v1/surveys/responses - Submit survey response")
            logger.info("  - GET  /api/v1/surveys/templates - View survey templates")
        else:
            logger.error("\n❌ Migration incomplete. Please check the logs above.")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}")
        sys.exit(1)