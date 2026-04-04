"""Add outline and full_content to drafts table

Revision ID: 002
Revises: 001
Create Date: 2026-02-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to drafts table
    op.add_column('drafts', sa.Column('full_content', sa.Text(), nullable=True))
    op.add_column('drafts', sa.Column('outline', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove columns
    op.drop_column('drafts', 'outline')
    op.drop_column('drafts', 'full_content')
