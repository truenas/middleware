"""remove raw disks from iscsi

Revision ID: 370ff38939fd
Revises: 382b7ca9bb51
Create Date: 2021-03-15 14:22:19.009163+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '370ff38939fd'
down_revision = '382b7ca9bb51'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    main_table = 'services_iscsitargetextent'
    main_col = 'iscsi_target_extent_type'
    tartoext_table = 'services_iscsitargettoextent'

    tar_ids = set()
    # query db for entries that point to raw disks
    for disk_id, in conn.execute(f'SELECT id FROM {main_table} WHERE {main_col} = "Disk"').fetchall():
        # delete the target to extent associations first
        for id, tar_id in conn.execute(
            f'SELECT id, iscsi_target_id FROM {tartoext_table} WHERE iscsi_extent_id = {disk_id}'
        ).fetchall():
            tar_ids.add(tar_id)
            conn.execute(f'DELETE FROM {tartoext_table} WHERE id = {id}')

        # delete extent next
        conn.execute(f'DELETE FROM {main_table} WHERE id = {disk_id}')

    # delete target(s) information last
    for tar_id in tar_ids:
        try:
            conn.execute(f'DELETE FROM services_iscsitargetgroups WHERE iscsi_target_id = {tar_id}')
            conn.execute(f'DELETE FROM services_iscsitarget WHERE id = {tar_id}')
        except Exception:
            # dont fail the transaction for all targets since this can fail on
            # on foreign key constraint since targets can have multiple assignments
            continue


def downgrade():
    pass
