""" Remove syslog_tls_certificate_authority

Revision ID: a156968d5cbb
Revises: 616c19f82016
Create Date: 2025-03-06 01:25:41.245074+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a156968d5cbb'
down_revision = '616c19f82016'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.drop_index('ix_system_advanced_adv_syslog_tls_certificate_authority_id')
        batch_op.drop_constraint('fk_system_advanced_adv_syslog_tls_certificate_authority_id_system_certificateauthority', type_='foreignkey')
        batch_op.drop_column('adv_syslog_tls_certificate_authority_id')


def downgrade():
    pass
