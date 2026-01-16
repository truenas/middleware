"""Split SMB path into dataset and relative path.

Revision ID: 087290abbc0c
Revises: ec5dad4625ad
Create Date: 2025-12-31 15:39:37.327297+00:00

"""
import os

from alembic import op
import sqlalchemy as sa

from middlewared.utils.mount import statmount


# revision identifiers, used by Alembic.
revision = '087290abbc0c'
down_revision = 'ec5dad4625ad'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('sharing_cifs_share', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cifs_dataset', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('cifs_relative_path', sa.String(length=255), nullable=True))

    # Migrate data from cifs_path to new columns
    conn = op.get_bind()
    shares = conn.execute(sa.text(
        'SELECT id, cifs_path FROM sharing_cifs_share'
    )).fetchall()

    # Build list of updates to batch execute
    updates = []
    for share in shares:
        share_id, path = share.id, share.cifs_path

        if path.startswith('EXTERNAL'):
            dataset = relative_path = None
        else:
            try:
                mntinfo = statmount(path=path, as_dict=False)
            except Exception:
                # Do not crash if path no longer exists, etc.
                # Invalid SMB share
                dataset = relative_path = None
            else:
                dataset = mntinfo.sb_source
                relative_path = os.path.relpath(path, mntinfo.mnt_point)
                if relative_path == '.':
                    relative_path = ''

        updates.append({'dataset': dataset, 'relpath': relative_path, 'id': share_id})

    # Batch execute all updates in one database round-trip
    if updates:
        conn.execute(
            sa.text(
                "UPDATE sharing_cifs_share SET cifs_dataset = :dataset, cifs_relative_path = :relpath WHERE id = :id"
            ),
            updates
        )
