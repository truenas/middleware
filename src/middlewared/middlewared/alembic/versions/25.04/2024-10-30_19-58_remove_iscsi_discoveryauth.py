"""Remove iscsi.discoveryauth in favor of updating iscsi.auth

Revision ID: 65964bb7b139
Revises: f1ca9deb82b9
Create Date: 2024-10-30 19:58:06.237170+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '65964bb7b139'
down_revision = 'f1ca9deb82b9'
branch_labels = None
depends_on = None


def set_discovery_auth(conn, authtype, authgroups):
    if authgroups:
        if len(authgroups) == 1:
            conn.execute(text(f'UPDATE services_iscsitargetauthcredential SET iscsi_target_auth_discovery_auth = "{authtype}" WHERE iscsi_target_auth_tag == {authgroups[0]}'))
        else:
            conn.execute(text(f'UPDATE services_iscsitargetauthcredential SET iscsi_target_auth_discovery_auth = "{authtype}" WHERE iscsi_target_auth_tag IN {tuple(authgroups)}'))


def upgrade():

    authgroup_select = 'SELECT iscsi_discoveryauth_authgroup FROM services_iscsidiscoveryauth WHERE iscsi_discoveryauth_authmethod = ?'

    with op.batch_alter_table('services_iscsitargetauthcredential', schema=None) as batch_op:
        batch_op.add_column(sa.Column('iscsi_target_auth_discovery_auth', sa.String(length=20), nullable=False, server_default='NONE'))

    conn = op.get_bind()
    chap_authgroups = [item[0] for item in conn.execute(authgroup_select, 'CHAP').fetchall()]
    chap_mutual_authgroups = [item[0] for item in conn.execute(authgroup_select, 'CHAP_MUTUAL').fetchall()]

    set_discovery_auth(conn, 'CHAP', chap_authgroups)
    set_discovery_auth(conn, 'CHAP_MUTUAL', chap_mutual_authgroups)

    op.drop_table('services_iscsidiscoveryauth')


def downgrade():
    pass
