"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2026-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create projects table
    op.create_table('projects',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('mode', sa.String(length=50), nullable=False),
    sa.Column('current_phase', sa.Enum('DISCOVERY', 'READING', 'ANALYSIS', 'DRAFTING', 'REVISION', name='projectphase'), nullable=True),
    sa.Column('phase_history', sa.JSON(), nullable=True),
    sa.Column('methodology', sa.Text(), nullable=True),
    sa.Column('findings', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create library_items table
    op.create_table('library_items',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('project_id', sa.String(), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('authors', sa.JSON(), nullable=True),
    sa.Column('year', sa.Integer(), nullable=True),
    sa.Column('abstract', sa.Text(), nullable=True),
    sa.Column('pdf_path', sa.String(length=500), nullable=True),
    sa.Column('vector_id', sa.String(length=100), nullable=True),
    sa.Column('chunk_count', sa.Integer(), nullable=True),
    sa.Column('is_selected_for_context', sa.Boolean(), nullable=True),
    sa.Column('relevance_score', sa.Float(), nullable=True),
    sa.Column('arxiv_id', sa.String(length=100), nullable=True),
    sa.Column('doi', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create lab_assets table
    op.create_table('lab_assets',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('project_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('asset_type', sa.String(length=50), nullable=False),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('ai_description', sa.Text(), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('mime_type', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create research_assets table
    op.create_table('research_assets',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('project_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('asset_type', sa.String(length=50), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('methodology_note', sa.Text(), nullable=True),
    sa.Column('section_hint', sa.String(length=50), nullable=True),
    sa.Column('is_included_in_draft', sa.Boolean(), nullable=True),
    sa.Column('ai_analysis', sa.Text(), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('mime_type', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create drafts table
    op.create_table('drafts',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('project_id', sa.String(), nullable=False),
    sa.Column('content_blocks', sa.JSON(), nullable=True),
    sa.Column('bibliography', sa.JSON(), nullable=True),
    sa.Column('word_count', sa.Integer(), nullable=True),
    sa.Column('revision_count', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create chat_sessions table
    op.create_table('chat_sessions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('project_id', sa.String(), nullable=False),
    sa.Column('messages', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('chat_sessions')
    op.drop_table('drafts')
    op.drop_table('research_assets')
    op.drop_table('lab_assets')
    op.drop_table('library_items')
    op.drop_table('projects')
