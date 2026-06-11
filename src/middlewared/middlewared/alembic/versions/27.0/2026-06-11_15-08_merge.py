"""Merge migration for NAS-141321: suspend VMs on snapshot by default (revision 7d3a1f9c2e84).

Revision ID: de51ca6f583a
Revises: 9ca2e97e239c, 7d3a1f9c2e84
Create Date: 2026-06-11 15:08:52.992346+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'de51ca6f583a'
down_revision = ('9ca2e97e239c', '7d3a1f9c2e84')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
