"""New schema fields SMB share

Revision ID: 1fc32b52c240
Revises: f8b0ab7c2275
Create Date: 2025-06-02 20:57:13.100313+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1fc32b52c240'
down_revision = 'f8b0ab7c2275'
branch_labels = None
depends_on = None


def migrate_purposes():
    """ Adjust SMB share configuration for new purpose names. """
    conn = op.get_bind()
    shares = conn.execute('SELECT * FROM sharing_cifs_share').fetchall()
    for share in shares:
        update = False
        auto_ds = False
        auto_snap = False
        purpose = None

        match share.cifs_purpose:
            case "DEFAULT_SHARE":
                if share.cifs_guestok or share.cifs_afp:
                    purpose = "LEGACY_SHARE"
                    update = True
            case "ENHANCED_TIMEMACHINE":
                purpose = "TIMEMACHINE_SHARE"
                auto_snap = True
                auto_ds = True
                update = True
            case "TIMEMACHINE":
                purpose = "TIMEMACHINE_SHARE"
                update = True
            case "NO_PRESET":
                purpose = "LEGACY_SHARE"
                update = True
            case "MULTI_PROTOCOL_NFS":
                purpose = "MULTIPROTOCOL_SHARE"
                update = True
            case "PRIVATE_DATASETS":
                purpose = "PRIVATE_DATASETS_SHARE"
                update = True
            case "WORM_DROPBOX":
                purpose = "TIME_LOCKED_SHARE"
                update = True
            case _:
                pass

        if not update:
            continue

        stmt = (
            'UPDATE sharing_CIFS_SHARE SET '
            'cifs_purpose = :purpose, '
            'cifs_auto_dataset_creation = :autods, '
            'cifs_auto_snapshot = :autosnap '
            'WHERE id = :shareid'
        )
        conn.execute(stmt, purpose=purpose, autods=auto_ds, autosnap=auto_snap, shareid=share.id)


def upgrade():
    with op.batch_alter_table('directoryservices', schema=None) as batch_op:
        batch_op.drop_column('ldap_shadow_object_class')

    with op.batch_alter_table('sharing_cifs_share', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cifs_auto_quota', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('cifs_auto_snapshot', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('cifs_auto_dataset_creation', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('cifs_worm_grace_period', sa.Integer(), nullable=False, server_default='0'))

    migrate_purposes()
