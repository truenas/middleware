"""
Apps catalog integration

Revision ID: 91724c382023
Revises: 135a7e02cbec
Create Date: 2024-05-19 16:25:17.935672+00:00
"""
import sqlalchemy as sa

from alembic import op


revision = '91724c382023'
down_revision = '135a7e02cbec'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # We will drop all old catalogs
    conn.execute('DELETE FROM services_catalog')

    # Now we will add our catalog
    op.execute(
        "INSERT INTO services_catalog (label, repository, branch, builtin) VALUES"
        " ('TRUENAS', 'https://github.com/sonicaj/apps', 'master', 1)"
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
