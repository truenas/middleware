"""add smb encryption parameter

Revision ID: d8bfbf4e277e
Revises: 91724c382023
Create Date: 2024-06-26 19:44:55.116098+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8bfbf4e277e'
down_revision = '91724c382023'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_cifs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cifs_srv_encryption', sa.String(length=120), nullable=True))
