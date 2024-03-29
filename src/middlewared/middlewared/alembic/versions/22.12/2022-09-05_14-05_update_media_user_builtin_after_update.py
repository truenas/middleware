"""Update media user builtin after update

Revision ID: aef1177c39c5
Revises: eba33d756a77
Create Date: 2022-09-05 14:17:54.745653+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'aef1177c39c5'
down_revision = 'eba33d756a77'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    con = op.get_bind()
    con.execute('UPDATE account_bsdusers SET bsdusr_builtin=0 WHERE bsdusr_username="media"')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
