"""
Docker registry mirrors unification

Revision ID: 6d590ec44faf
Revises: 6041af215ccd
Create Date: 2025-11-09 12:00:00.000000+00:00
"""
import json

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6d590ec44faf'
down_revision = '6041af215ccd'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Add the new registry_mirrors column
    with op.batch_alter_table('services_docker', schema=None) as batch_op:
        batch_op.add_column(sa.Column('registry_mirrors', sa.Text(), nullable=False, server_default='[]'))

    # Migrate data from old columns to new column
    for row in conn.execute(text("SELECT id, secure_registry_mirrors, insecure_registry_mirrors FROM services_docker")).mappings().all():
        secure_mirrors = json.loads(row['secure_registry_mirrors']) if row['secure_registry_mirrors'] else []
        insecure_mirrors = json.loads(row['insecure_registry_mirrors']) if row['insecure_registry_mirrors'] else []

        # Convert to new format
        registry_mirrors = []
        for url in secure_mirrors:
            registry_mirrors.append({'url': url, 'insecure': False})
        for url in insecure_mirrors:
            registry_mirrors.append({'url': url, 'insecure': True})

        conn.execute(
            text("UPDATE services_docker SET registry_mirrors = :registry_mirrors WHERE id = :id"),
            {"registry_mirrors": json.dumps(registry_mirrors), "id": row['id']}
        )

    # Drop the old columns
    with op.batch_alter_table('services_docker', schema=None) as batch_op:
        batch_op.drop_column('secure_registry_mirrors')
        batch_op.drop_column('insecure_registry_mirrors')


def downgrade():
    # Add back the old columns
    with op.batch_alter_table('services_docker', schema=None) as batch_op:
        batch_op.add_column(sa.Column('secure_registry_mirrors', sa.Text(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('insecure_registry_mirrors', sa.Text(), nullable=False, server_default='[]'))

    conn = op.get_bind()

    # Migrate data back from new column to old columns
    for row in conn.execute(text("SELECT id, registry_mirrors FROM services_docker")).mappings().all():
        registry_mirrors = json.loads(row['registry_mirrors']) if row['registry_mirrors'] else []

        # Convert back to old format
        secure_mirrors = []
        insecure_mirrors = []
        for mirror in registry_mirrors:
            if mirror.get('insecure', False):
                insecure_mirrors.append(mirror['url'])
            else:
                secure_mirrors.append(mirror['url'])

        conn.execute(
            text("UPDATE services_docker SET secure_registry_mirrors = :secure, insecure_registry_mirrors = :insecure WHERE id = :id"),
            {"secure": json.dumps(secure_mirrors), "insecure": json.dumps(insecure_mirrors), "id": row['id']}
        )

    # Drop the new column
    with op.batch_alter_table('services_docker', schema=None) as batch_op:
        batch_op.drop_column('registry_mirrors')
