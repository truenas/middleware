"""
Add docker cidr subnet

Revision ID: 98c1ebde0079
Revises: d24d6760fda4
Create Date: 2024-08-30 20:33:47.996994+00:00
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '98c1ebde0079'
down_revision = 'd24d6760fda4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_docker', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'address_pools',
                sa.TEXT(),
                nullable=False,
                server_default='[{"base": "172.30.0.0/16", "size": 27}, {"base": "172.31.0.0/16", "size": 27}]'
            )
        )


def downgrade():
    pass
