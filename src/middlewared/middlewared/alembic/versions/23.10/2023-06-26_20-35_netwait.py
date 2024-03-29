"""Remove netwait

Revision ID: bd11aee1c4b7
Revises: 0e5949153c20
Create Date: 2023-06-26 20:35:25.259010+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bd11aee1c4b7'
down_revision = '0e5949153c20'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('network_globalconfiguration', schema=None) as batch_op:
        batch_op.drop_column('gc_netwait_enabled')
        batch_op.drop_column('gc_netwait_ip')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('network_globalconfiguration', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gc_netwait_ip', sa.VARCHAR(length=300), nullable=False))
        batch_op.add_column(sa.Column('gc_netwait_enabled', sa.BOOLEAN(), nullable=False))

    # ### end Alembic commands ###
