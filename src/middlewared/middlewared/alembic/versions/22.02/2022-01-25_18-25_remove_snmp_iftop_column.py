"""remove snmp_iftop column

Revision ID: ecd42897802c
Revises: 184b771fb710
Create Date: 2022-01-25 18:25:01.109629+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'ecd42897802c'
down_revision = '184b771fb710'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_snmp', schema=None) as batch_op:
        batch_op.drop_column('snmp_iftop')


def downgrade():
    pass
