"""
Apps catalog integration

Revision ID: 91724c382023
Revises: 0dc9c3f51393
Create Date: 2024-05-19 16:25:17.935672+00:00
"""
import json

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op


revision = '91724c382023'
down_revision = '0dc9c3f51393'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # We will drop all old catalogs
    conn.execute(text('DELETE FROM services_catalog'))

    with op.batch_alter_table('services_catalog', schema=None) as batch_op:
        batch_op.drop_column('repository')
        batch_op.drop_column('branch')
        batch_op.drop_column('builtin')

    # Now we will add our catalog
    conn.execute(
        "INSERT INTO services_catalog (label, preferred_trains) VALUES ('TRUENAS', ?)", (json.dumps(['stable']),)
    )

    # We will add the model which will be used for docker
    op.create_table(
        'services_docker',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pool', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_services_docker')),
    )


def downgrade():
    pass
