"""remove snmp iftop integration (never worked)

Revision ID: cd7569a7b973
Revises: 7132a60093ce
Create Date: 2022-02-07 13:36:26.041217+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'cd7569a7b973'
down_revision = '7132a60093ce'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_snmp', schema=None) as batch_op:
        batch_op.drop_column('snmp_iftop')


def downgrade():
    pass
