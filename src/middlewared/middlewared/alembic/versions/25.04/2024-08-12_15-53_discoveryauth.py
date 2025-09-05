"""Add iSCSI discoverauth

Flatten the per-portal discovery auth to a system-wide discovery auth.

Revision ID: 504a7bd32680
Revises: 5654da8713d1
Create Date: 2024-08-12 15:53:48.342351+00:00

"""
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '504a7bd32680'
down_revision = '5654da8713d1'
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
    data = conn.execute(text("SELECT iscsi_target_portal_discoveryauthgroup, iscsi_target_portal_discoveryauthmethod, id FROM services_iscsitargetportal")).fetchall()

    # Migrate the data into the new table.
    # - Mutual CHAP first.
    mutual_chap_auth_groups = []
    for authgroup, authmethod, _portal_id in data:
        if authmethod == 'CHAP Mutual' and authgroup not in mutual_chap_auth_groups:
            # Let's not carry around 'CHAP Mutual' anymore.
            conn.execute('INSERT INTO services_iscsidiscoveryauth (iscsi_discoveryauth_authmethod, iscsi_discoveryauth_authgroup) VALUES ("CHAP_MUTUAL",?)', authgroup)
            mutual_chap_auth_groups.append(authgroup)
    # - Simple CHAP next.
    simple_chap_auth_groups = []
    for authgroup, authmethod, _portal_id in data:
        if authmethod == 'CHAP' and authgroup not in mutual_chap_auth_groups + simple_chap_auth_groups:
            conn.execute('INSERT INTO services_iscsidiscoveryauth (iscsi_discoveryauth_authmethod, iscsi_discoveryauth_authgroup) VALUES ("CHAP",?)', authgroup)
            simple_chap_auth_groups.append(authgroup)

    # Things to test
    # 1. Do we have a mix of None and non-None?
    # 2. If not, do we have more than one CHAP/Mutual CHAP
    # 3. Do we have more than one Mutual CHAP peeruser/secret?
    none_list = list(filter(lambda t: t[1] == 'None', data))
    none_count = len(none_list)
    non_none_count = len(mutual_chap_auth_groups) + len(simple_chap_auth_groups)

    if none_count and non_none_count:
        portal_id_strs = list(str(item[2]) for item in none_list)
        none_ips = conn.execute("SELECT iscsi_target_portalip_ip FROM services_iscsitargetportalip WHERE iscsi_target_portalip_portal_id IN (?)", ','.join(portal_id_strs)).fetchall()
        conn.execute("INSERT INTO system_keyvalue (\"key\", value) VALUES (?, ?)",
                     ("ISCSIDiscoveryAuthMixed", json.dumps({'ips': [ip[0] for ip in none_ips]})))
    elif non_none_count > 1:
        conn.execute("INSERT INTO system_keyvalue (\"key\", value) VALUES (?, ?)",
                     ("ISCSIDiscoveryAuthMultipleCHAP", json.dumps({})))

    if mutual_chap_auth_groups:
        if len(mutual_chap_auth_groups) == 1:
            data = conn.execute(text(f"SELECT DISTINCT iscsi_target_auth_peeruser FROM services_iscsitargetauthcredential WHERE iscsi_target_auth_tag = {mutual_chap_auth_groups[0]} AND iscsi_target_auth_peeruser != ''")).fetchall()
        else:
            tags = ','.join(str(x) for x in mutual_chap_auth_groups)
            data = conn.execute(text(f"SELECT DISTINCT iscsi_target_auth_peeruser FROM services_iscsitargetauthcredential WHERE iscsi_target_auth_tag in ({tags}) AND iscsi_target_auth_peeruser != ''")).fetchall()
        if len(list(data)) > 1:
            active_peeruser = data[0][0]
            conn.execute("INSERT INTO system_keyvalue (\"key\", value) VALUES (?, ?)",
                         ("ISCSIDiscoveryAuthMultipleMutualCHAP", json.dumps({'peeruser': active_peeruser})))

    # Remove the obsolete columns
    with op.batch_alter_table('services_iscsitargetportal', schema=None) as batch_op:
        batch_op.drop_column('iscsi_target_portal_discoveryauthgroup')
        batch_op.drop_column('iscsi_target_portal_discoveryauthmethod')


def downgrade():
    pass
