"""rsync SSH credentials

Revision ID: 32a49386d6c3
Revises: 34df1ca8a04e
Create Date: 2022-05-31 12:11:48.231515+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '32a49386d6c3'
down_revision = '34df1ca8a04e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('tasks_rsync', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rsync_ssh_credentials_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_tasks_rsync_rsync_ssh_credentials_id'), ['rsync_ssh_credentials_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_tasks_rsync_rsync_ssh_credentials_id_system_keychaincredential'), 'system_keychaincredential', ['rsync_ssh_credentials_id'], ['id'])

        batch_op.alter_column('rsync_remotehost',
               existing_type=sa.VARCHAR(length=120),
               nullable=True)
        batch_op.alter_column('rsync_remotemodule',
               existing_type=sa.VARCHAR(length=120),
               nullable=True)
        batch_op.alter_column('rsync_remoteport',
               existing_type=sa.SMALLINT(),
               nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('tasks_rsync', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_tasks_rsync_rsync_ssh_credentials_id_system_keychaincredential'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_tasks_rsync_rsync_ssh_credentials_id'))
        batch_op.drop_column('rsync_ssh_credentials_id')

    # ### end Alembic commands ###
