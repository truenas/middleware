""" Merge migration after adding account policy columns

Revision ID: d7e3a916db65
Revises: f15312414057, 249b95f63f76
Create Date: 2025-04-02 15:40:46.829354+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7e3a916db65'
down_revision = ('f15312414057', '249b95f63f76')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
