from sqlalchemy import text

"""
Reporting exporters type attr normalization

Revision ID: 2b59607575b8
Revises: 0972c1f572b8
Create Date: 2024-11-08 09:09:45.960915+00:00

"""
import json

from alembic import op

revision = '2b59607575b8'
down_revision = '0972c1f572b8'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for exporter_config in conn.execute(text("SELECT * FROM reporting_exporters")).fetchall():
        exporter_config = dict(exporter_config)
        attributes = json.loads(exporter_config['attributes'])
        attributes['exporter_type'] = exporter_config['type']
        conn.execute(
            "UPDATE reporting_exporters SET attributes = ? WHERE id = ?",
            (json.dumps(attributes), exporter_config['id'])
        )

    with op.batch_alter_table('reporting_exporters', schema=None) as batch_op:
        batch_op.drop_column('type')


def downgrade():
    pass
