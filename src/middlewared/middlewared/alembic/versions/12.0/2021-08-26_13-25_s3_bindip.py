from sqlalchemy import text

"""
Normalize s3 bindip

Revision ID: 26de83f45a9d
Revises: 2e2c8b0e787b
Create Date: 2021-08-26 13:25:29.872200+00:00

"""
from alembic import op


revision = '26de83f45a9d'
down_revision = '2e2c8b0e787b'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text("UPDATE services_s3 SET s3_bindip = '0.0.0.0' WHERE s3_bindip = ''"))


def downgrade():
    pass
