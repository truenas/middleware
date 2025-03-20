"""Remove SMART support

Revision ID: f15312414057
Revises: 9a5b103ec2e4
Create Date: 2025-03-20 11:52:20.261454+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f15312414057'
down_revision = '9a5b103ec2e4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('tasks_smarttest_smarttest_disks', schema=None) as batch_op:
        batch_op.drop_index('tasks_smarttest_smarttest_disks_smarttest_id__disk_id')

    op.drop_table('tasks_smarttest_smarttest_disks')
    op.drop_table('services_smart')
    op.drop_table('tasks_smarttest')
    with op.batch_alter_table('storage_disk', schema=None) as batch_op:
        batch_op.drop_column('disk_critical')
        batch_op.drop_column('disk_togglesmart')
        batch_op.drop_column('disk_informational')
        batch_op.drop_column('disk_difference')

    op.execute("DELETE FROM services_services WHERE srv_service = 'smartd'")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('storage_disk', schema=None) as batch_op:
        batch_op.add_column(sa.Column('disk_difference', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('disk_informational', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('disk_togglesmart', sa.BOOLEAN(), nullable=False))
        batch_op.add_column(sa.Column('disk_critical', sa.INTEGER(), nullable=True))

    op.create_table('tasks_smarttest',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('smarttest_type', sa.VARCHAR(length=2), nullable=False),
    sa.Column('smarttest_desc', sa.VARCHAR(length=120), nullable=False),
    sa.Column('smarttest_hour', sa.VARCHAR(length=100), nullable=False),
    sa.Column('smarttest_daymonth', sa.VARCHAR(length=100), nullable=False),
    sa.Column('smarttest_month', sa.VARCHAR(length=100), nullable=False),
    sa.Column('smarttest_dayweek', sa.VARCHAR(length=100), nullable=False),
    sa.Column('smarttest_all_disks', sa.BOOLEAN(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('services_smart',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('smart_interval', sa.INTEGER(), nullable=False),
    sa.Column('smart_powermode', sa.VARCHAR(length=60), nullable=False),
    sa.Column('smart_difference', sa.INTEGER(), nullable=False),
    sa.Column('smart_informational', sa.INTEGER(), nullable=False),
    sa.Column('smart_critical', sa.INTEGER(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tasks_smarttest_smarttest_disks',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('smarttest_id', sa.INTEGER(), nullable=False),
    sa.Column('disk_id', sa.VARCHAR(length=100), nullable=False),
    sa.ForeignKeyConstraint(['disk_id'], ['storage_disk.disk_identifier'], name='fk_tasks_smarttest_smarttest_disks_disk_id_storage_disk', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['smarttest_id'], ['tasks_smarttest.id'], name='fk_tasks_smarttest_smarttest_disks_smarttest_id_tasks_smarttest', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tasks_smarttest_smarttest_disks', schema=None) as batch_op:
        batch_op.create_index('tasks_smarttest_smarttest_disks_smarttest_id__disk_id', ['smarttest_id', 'disk_id'], unique=False)

    # ### end Alembic commands ###
