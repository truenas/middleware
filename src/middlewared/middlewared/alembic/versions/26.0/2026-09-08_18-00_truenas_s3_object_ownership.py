"""Give S3 object ownership its own column

`permissions_model` carried two questions: whether anything but the S3
service reads a bucket's tree, and which account an S3 operation runs
as. The second is AWS's own per-bucket S3 Object Ownership setting, so
it becomes `object_ownership`, and the model keeps `S3` and
`MULTIPROTOCOL` alone.

Every row takes `BUCKET_OWNER_ENFORCED`, the S3 service's own default
and AWS's for a new bucket, except a `MULTIPROTOCOL` one: the other
protocols' users own the file modes there, so only the caller's own uid
may act and the service folds the row to `OBJECT_WRITER` whatever it is
given. `S3_BUCKET_OWNER_ENFORCED` was the pair spelled as one value and
becomes `S3` beside the default.

Revision ID: f1a6c48e2d70
Revises: e4b8d2f6a1c3
Create Date: 2026-09-08 18:00:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a6c48e2d70'
down_revision = 'e4b8d2f6a1c3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('truenas_s3_bucket', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'object_ownership', sa.String(length=32), nullable=False, server_default='BUCKET_OWNER_ENFORCED',
        ))

    op.execute(sa.text(
        "UPDATE truenas_s3_bucket SET object_ownership = 'OBJECT_WRITER' "
        "WHERE permissions_model = 'MULTIPROTOCOL'"
    ))
    op.execute(sa.text(
        "UPDATE truenas_s3_bucket SET permissions_model = 'S3' "
        "WHERE permissions_model = 'S3_BUCKET_OWNER_ENFORCED'"
    ))


def downgrade():
    op.execute(sa.text(
        "UPDATE truenas_s3_bucket SET permissions_model = 'S3_BUCKET_OWNER_ENFORCED' "
        "WHERE permissions_model = 'S3' AND object_ownership = 'BUCKET_OWNER_ENFORCED'"
    ))
    with op.batch_alter_table('truenas_s3_bucket', schema=None) as batch_op:
        batch_op.drop_column('object_ownership')
