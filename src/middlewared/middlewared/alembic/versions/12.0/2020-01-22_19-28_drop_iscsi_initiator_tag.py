"""Drop iSCSI initiator tag column

Revision ID: 536cbfca20e6
Revises: f3875acb8d76
Create Date: 2020-01-22 19:28:06.324970+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '536cbfca20e6'
down_revision = 'f3875acb8d76'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_iscsitargetauthorizedinitiator', schema=None) as batch_op:
        batch_op.drop_column('iscsi_target_initiator_tag')


def downgrade():
    pass
