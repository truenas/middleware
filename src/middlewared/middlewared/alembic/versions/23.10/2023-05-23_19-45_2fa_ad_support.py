"""
2FA AD Support

Revision ID: cf91fa3d0696
Revises: 2c0646015ca5
Create Date: 2023-05-23 19:45:17.935672+00:00
"""
from alembic import op
import sqlalchemy as sa


revision = 'cf91fa3d0696'
down_revision = '2c0646015ca5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('account_twofactor_user_auth', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_sid', sa.String(length=255), nullable=True))
        batch_op.create_index(batch_op.f('ix_account_twofactor_user_auth_user_sid'), ['user_sid'], unique=True)


def downgrade():
    pass
