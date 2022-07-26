"""
Migrate iSCSI Portal IPs

Revision ID: 14899f89b885
Revises: 3ac384af617f
Create Date: 2022-07-27 01:00:58.755371+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '14899f89b885'
down_revision = '3ac384af617f'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    with op.batch_alter_table('services_iscsitargetglobalconfiguration', schema=None) as batch_op:
        batch_op.add_column(sa.Column('iscsi_listen_port', sa.INTEGER(), nullable=False, server_default='3260'))

    listen_port = None
    all_ports = set()
    for row in map(dict, conn.execute("SELECT * FROM services_iscsitargetportalip").fetchall()):
        all_ports.add(row['iscsi_target_portalip_port'])
        if row['iscsi_target_portalip_ip'] == '0.0.0.0':
            listen_port = row['iscsi_target_portalip_port']
            break
    else:
        if len(all_ports) == 1:
            listen_port = all_ports.pop()

    if listen_port is None:
        listen_port = 3260

    conn.execute("UPDATE services_iscsitargetglobalconfiguration SET iscsi_listen_port = ?", listen_port)

    with op.batch_alter_table('services_iscsitargetportalip', schema=None) as batch_op:
        batch_op.create_index(
            'services_iscsitargetportalip_iscsi_target_portalip_ip', ['iscsi_target_portalip_ip'], unique=True
        )
        batch_op.drop_index('services_iscsitargetportalip_iscsi_target_portalip_ip__iscsi_target_portalip_port')
        batch_op.drop_column('iscsi_target_portalip_port')


def downgrade():
    pass
