"""
Add s3 console bindport

Revision ID: 37298ef77ee8
Revises: 9c11f6c6f152
Create Date: 2022-01-03 11:46:50.848183+00:00
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '37298ef77ee8'
down_revision = '9c11f6c6f152'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_s3', schema=None) as batch_op:
        batch_op.add_column(sa.Column('s3_console_bindport', sa.SmallInteger(), nullable=False, server_default='9001'))


def downgrade():
    with op.batch_alter_table('services_s3', schema=None) as batch_op:
        batch_op.drop_column('s3_console_bindport')
