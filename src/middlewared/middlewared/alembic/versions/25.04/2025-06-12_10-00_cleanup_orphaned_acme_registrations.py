"""Cleanup orphaned ACME registrations and remove unused contact column

Revision ID: 7a8b9c0d1e2f
Revises: 30c9619bf9e7
Create Date: 2025-06-12 10:00:00.000000+00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = '7a8b9c0d1e2f'
down_revision = '30c9619bf9e7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Find orphaned entries in system_acmeregistration that don't have
    # corresponding entries in system_acmeregistrationbody
    orphaned_registrations = conn.execute(text("""
        SELECT ar.id 
        FROM system_acmeregistration ar
        LEFT JOIN system_acmeregistrationbody arb ON ar.id = arb.acme_id
        WHERE arb.id IS NULL
    """)).fetchall()
    
    if orphaned_registrations:
        orphaned_ids = [row[0] for row in orphaned_registrations]

        # Delete orphaned entries from system_acmeregistration
        placeholders = ','.join([f':id{i}' for i in range(len(orphaned_ids))])
        params = {f'id{i}': orphaned_id for i, orphaned_id in enumerate(orphaned_ids)}
        conn.execute(
            text(f"DELETE FROM system_acmeregistration WHERE id IN ({placeholders})"), params
        )

    # Drop the contact column from system_acmeregistrationbody
    # as ACME services no longer provide contact information
    with op.batch_alter_table('system_acmeregistrationbody', schema=None) as batch_op:
        batch_op.drop_column('contact')


def downgrade():
    # Add back the contact column
    with op.batch_alter_table('system_acmeregistrationbody', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contact', sa.String(254), nullable=True))
