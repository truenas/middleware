"""Split dataset paths into dataset and relative path components.

This migration adds dataset and relative_path columns to all sharing/task tables
that contain filesystem paths. The columns are added but not populated - data
population happens in middlewared migration 0018_resolve_dataset_paths.py after
boot when datasets are mounted.

Tables updated:
- sharing_cifs_share (SMB shares)
- sharing_nfs_share (NFS shares)
- sharing_webshare_share (Webshare shares)
- services_iscsitargetextent (iSCSI FILE extents)
- tasks_rsync (Rsync tasks)
- tasks_cloud_backup (Cloud backup tasks)
- tasks_cloudsync (Cloud sync tasks)
- services_nvmet_namespace (NVMe-oF FILE namespaces)

Revision ID: a8f5d9e2c1b7
Revises: 9202ee4732cf
Create Date: 2026-01-27 20:27:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a8f5d9e2c1b7'
down_revision = '9202ee4732cf'
branch_labels = None
depends_on = None


def upgrade():
    # Add columns for dataset path splitting
    # Data population happens in middlewared migration after boot
    for table, field_prefix in (
        # SMB shares
        ('sharing_cifs_share', 'cifs_'),
        # NFS shares
        ('sharing_nfs_share', 'nfs_'),
        # Webshare shares
        ('sharing_webshare_share', ''),
        # iSCSI FILE extents
        ('services_iscsitargetextent', 'iscsi_target_extent_'),
        # Rsync tasks
        ('tasks_rsync', 'rsync_'),
        # Cloud backup tasks
        ('tasks_cloud_backup', ''),
        # Cloud sync tasks
        ('tasks_cloudsync', ''),
        # NVMe-oF FILE namespaces
        ('services_nvmet_namespace', 'nvmet_namespace_'),
    ):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column(f'{field_prefix}dataset', sa.String(length=255), nullable=True))
            batch_op.add_column(sa.Column(f'{field_prefix}relative_path', sa.String(length=255), nullable=True))
