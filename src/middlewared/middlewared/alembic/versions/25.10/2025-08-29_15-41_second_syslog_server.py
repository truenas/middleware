"""Add support for multiple remote syslog servers.

Revision ID: 5ea9f662ced4
Revises: 7767afd88989
Create Date: 2025-08-29 15:41:53.637185+00:00

"""
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '5ea9f662ced4'
down_revision = '7767afd88989'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    result = conn.execute(
        text('SELECT adv_syslogserver, adv_syslog_transport, adv_syslog_tls_certificate_id FROM system_advanced')
    ).fetchone()
    if result:
        server, transport, cert_id = result
    else:
        server, transport, cert_id = None, None, None

    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adv_syslogservers', sa.TEXT(), nullable=False, server_default='[]'))
        batch_op.drop_index('ix_system_advanced_adv_syslog_tls_certificate_id')
        batch_op.drop_constraint('fk_system_advanced_adv_syslog_tls_certificate_id_system_certificate', type_='foreignkey')
        batch_op.drop_column('adv_syslog_tls_certificate_id')
        batch_op.drop_column('adv_syslogserver')
        batch_op.drop_column('adv_syslog_transport')

    if server:
        syslogservers = json.dumps([{'host': server, 'transport': transport, 'tls_certificate': cert_id}])
        conn.execute(text(f'UPDATE system_advanced SET adv_syslogservers = {syslogservers!r}'))
