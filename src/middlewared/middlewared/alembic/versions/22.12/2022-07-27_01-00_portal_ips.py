"""
Migrate iSCSI Portal IPs

Revision ID: 14899f89b885
Revises: 75d84034adcb
Create Date: 2022-07-27 01:00:58.755371+00:00

"""
from collections import defaultdict

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = '14899f89b885'
down_revision = '75d84034adcb'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    with op.batch_alter_table('services_iscsitargetglobalconfiguration', schema=None) as batch_op:
        batch_op.add_column(sa.Column('iscsi_listen_port', sa.INTEGER(), nullable=False, server_default='3260'))

    ip_to_port_to_id = defaultdict(dict)
    ports_popularity = defaultdict(int)
    for row in map(dict, conn.execute(text("SELECT * FROM services_iscsitargetportalip")).fetchall()):
        ip_to_port_to_id[row['iscsi_target_portalip_ip']][row['iscsi_target_portalip_port']] = row['id']
        ports_popularity[row['iscsi_target_portalip_port']] += 1

    if '0.0.0.0' in ip_to_port_to_id:
        if 3260 in ip_to_port_to_id['0.0.0.0']:
            listen_port = 3260
        else:
            listen_port = min(ip_to_port_to_id['0.0.0.0'].keys())
    elif ports_popularity:
        listen_port = sorted(
            ports_popularity.keys(),
            key=lambda port: (
                ports_popularity[port],
                1 if port == 3260 else 0,
            )
        )[-1]
    else:
        listen_port = 3260

    for ip, port_to_id in ip_to_port_to_id.items():
        if listen_port in port_to_id:
            leave_id = port_to_id[listen_port]
        else:
            leave_id = sorted(port_to_id.values())[0]
        conn.execute("DELETE FROM services_iscsitargetportalip WHERE iscsi_target_portalip_ip = ? AND id != ?",
                     ip, leave_id)

    conn.execute("UPDATE services_iscsitargetglobalconfiguration SET iscsi_listen_port = ?", listen_port)

    with op.batch_alter_table('services_iscsitargetportalip', schema=None) as batch_op:
        batch_op.create_index(
            'services_iscsitargetportalip_iscsi_target_portalip_ip', ['iscsi_target_portalip_ip'], unique=True
        )
        batch_op.drop_index('services_iscsitargetportalip_iscsi_target_portalip_ip__iscsi_target_portalip_port')
        batch_op.drop_column('iscsi_target_portalip_port')


def downgrade():
    pass
