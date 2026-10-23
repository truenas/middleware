"""S3 bucket layout

Revision ID: bbce11d3cbd7
Revises: e2a7c4f19b63
Create Date: 2026-10-20 12:00:00.000000+00:00

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "bbce11d3cbd7"
down_revision = "e2a7c4f19b63"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("truenas_s3_bucket", schema=None) as batch_op:
        batch_op.add_column(sa.Column("layout", sa.String(16), nullable=False, server_default="BUCKET"))


def downgrade():
    with op.batch_alter_table("truenas_s3_bucket", schema=None) as batch_op:
        batch_op.drop_column("layout")
