"""add xmit_hash_policy and lacpdu_rate

Revision ID: c02971570fb0
Revises: 1fd17693941f
Create Date: 2021-06-29 15:45:54.309469+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'c02971570fb0'
down_revision = '1fd17693941f'


def upgrade():
    with op.batch_alter_table('network_lagginterface', schema=None) as batch_op:
        batch_op.add_column(sa.Column('lagg_lacpdu_rate', sa.String(length=4), nullable=True))
        batch_op.add_column(sa.Column('lagg_xmit_hash_policy', sa.String(length=8), nullable=True))


def downgrade():
    with op.batch_alter_table('network_lagginterface', schema=None) as batch_op:
        batch_op.drop_column('lagg_xmit_hash_policy')
        batch_op.drop_column('lagg_lacpdu_rate')
