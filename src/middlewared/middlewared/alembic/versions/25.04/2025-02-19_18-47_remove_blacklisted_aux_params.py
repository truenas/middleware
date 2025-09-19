"""Remove blacklisted SMB share aux params

Revision ID: ae78ab5ebf07
Revises: d93139a68db5
Create Date: 2025-02-19 18:47:53.749089+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'ae78ab5ebf07'
down_revision = 'd93139a68db5'
branch_labels = None
depends_on = None


SHARE_BLACKLIST = (
    'wide links',
    'use sendfile',
    'vfs objects',
    'allow insecure',
)

def upgrade():

    conn = op.get_bind()
    for share in conn.execute(text("SELECT * FROM sharing_cifs_share")).mappings().all():
        changed = False
        not_blacklisted = []
        for param in share.get('cifs_auxsmbconf', '').splitlines():
            if param.lower().strip().startswith(SHARE_BLACKLIST):
                changed = True
                continue

            not_blacklisted.append(param)

        if not changed:
            continue

        new_aux = '\n'.join(not_blacklisted)

        conn.execute(
            text('UPDATE sharing_cifs_share SET cifs_auxsmbconf = :aux WHERE id = :share_id'),
            {'aux': new_aux, 'share_id': share['id']}
        )
