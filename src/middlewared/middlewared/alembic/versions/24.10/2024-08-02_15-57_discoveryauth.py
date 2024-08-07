"""Add iSCSI discoverauth

Flatten the per-portal discovery auth to a system-wide discovery auth.

Revision ID: 208a066c65f7
Revises: 81b8bae8fb11
Create Date: 2024-08-02 15:57:30.527787+00:00

"""
import json

import sqlalchemy as sa
from alembic import op

from middlewared.plugins.iscsi_.constants import DISCOVERY_AUTH_UPGRADE_COMPLETE_SENTINEL

CHAP_TYPES = ['CHAP', 'CHAP Mutual']

# revision identifiers, used by Alembic.
revision = '208a066c65f7'
down_revision = '81b8bae8fb11'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('services_iscsidiscoveryauth',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('iscsi_discoveryauth_authmethod', sa.String(length=120), nullable=False),
                    sa.Column('iscsi_discoveryauth_authgroup', sa.Integer(), nullable=False),
                    sa.PrimaryKeyConstraint('id', name=op.f('pk_services_iscsidiscoveryauth')),
                    sa.UniqueConstraint('iscsi_discoveryauth_authgroup', name=op.f('uq_services_iscsidiscoveryauth_iscsi_discoveryauth_authgroup')),
                    sqlite_autoincrement=True
                    )

    conn = op.get_bind()
    data = conn.execute("SELECT iscsi_target_portal_discoveryauthgroup, iscsi_target_portal_discoveryauthmethod, id FROM services_iscsitargetportal").fetchall()

    # Migrate the data into the new table.  Let's not carry around 'CHAP Mutual' anymore.
    for authgroup, authmethod, _portal_id in data:
        if authmethod not in CHAP_TYPES:
            continue
        if authmethod == 'CHAP Mutual':
            authmethod = 'CHAP_MUTUAL'
        conn.execute('INSERT INTO services_iscsidiscoveryauth (iscsi_discoveryauth_authmethod, iscsi_discoveryauth_authgroup) VALUES (?,?)', (authmethod, authgroup))

    # Things to test
    # 1. Do we have a mix of None and non-None?
    # 2. If not, do we have more than one CHAP/Mutual CHAP
    # 3. Do we have more than one Mutual CHAP peeruser/secret?
    none_list = list(filter(lambda t: t[1] == 'None', data))
    none_count = len(none_list)
    non_none_count = len(list(filter(lambda t: t[1] in CHAP_TYPES, data)))

    alerts = {}
    if none_count and non_none_count:
        portal_id_strs = list(str(item[2]) for item in none_list)
        none_ips = conn.execute("SELECT iscsi_target_portalip_ip FROM services_iscsitargetportalip WHERE iscsi_target_portalip_portal_id IN (?)", ','.join(portal_id_strs)).fetchall()
        alerts['ISCSIDiscoveryAuthMixed'] = {'ips': [ip[0] for ip in none_ips]}
    elif non_none_count > 1:
        alerts['ISCSIDiscoveryAuthMultipleCHAP'] = {}

    mutual_chap_auth_groups = [item[0] for item in filter(lambda t: t[1] == 'CHAP Mutual', data)]
    if mutual_chap_auth_groups:
        if len(mutual_chap_auth_groups) == 1:
            data = conn.execute(f"SELECT DISTINCT iscsi_target_auth_peeruser FROM services_iscsitargetauthcredential WHERE iscsi_target_auth_tag = {mutual_chap_auth_groups[0]} AND iscsi_target_auth_peeruser != ''").fetchall()
        else:
            tags = ','.join(str(x) for x in mutual_chap_auth_groups)
            data = conn.execute(f"SELECT DISTINCT iscsi_target_auth_peeruser FROM services_iscsitargetauthcredential WHERE iscsi_target_auth_tag in ({tags}) AND iscsi_target_auth_peeruser != ''").fetchall()
        if len(list(data)) > 1:
            active_peeruser = data[0][0]
            alerts['ISCSIDiscoveryAuthMultipleMutualCHAP'] = {'peeruser': active_peeruser}

    # Remove the obsolete columns
    with op.batch_alter_table('services_iscsitargetportal', schema=None) as batch_op:
        batch_op.drop_column('iscsi_target_portal_discoveryauthgroup')
        batch_op.drop_column('iscsi_target_portal_discoveryauthmethod')

    # Save any alerts
    if alerts:
        with open(DISCOVERY_AUTH_UPGRADE_COMPLETE_SENTINEL, 'w') as f:
            json.dump(alerts, f)


def downgrade():
    pass
