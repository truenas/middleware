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
    has_fk_system_advanced_adv_syslog_tls_certificate_authority_id_system_certificateauthority = False
    conn = op.get_bind()
    for sql in map(dict, conn.execute(sa.text(
        "SELECT sql FROM sqlite_schema WHERE type = 'table' AND tbl_name = 'system_advanced'"
    )).mappings().all()):
        if "fk_system_advanced_adv_syslog_tls_certificate_authority_id_system_certificateauthority" in sql["sql"]:
            has_fk_system_advanced_adv_syslog_tls_certificate_authority_id_system_certificateauthority = True

    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.drop_index('ix_system_advanced_adv_syslog_tls_certificate_authority_id')
        if has_fk_system_advanced_adv_syslog_tls_certificate_authority_id_system_certificateauthority:
            batch_op.drop_constraint(
                'fk_system_advanced_adv_syslog_tls_certificate_authority_id_system_certificateauthority',
                type_='foreignkey',
            )
        batch_op.drop_column('adv_syslog_tls_certificate_authority_id')


def downgrade():
    pass
