"""Cleanup orphaned ACME registrations

Revision ID: 7a8b9c0d1e2f
Revises: 30c9619bf9e7
Create Date: 2025-06-12 10:00:00.000000+00:00
"""
from alembic import op


revision = '7a8b9c0d1e2f'
down_revision = '30c9619bf9e7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Find orphaned entries in system_acmeregistration that don't have
    # corresponding entries in system_acmeregistrationbody
    orphaned_registrations = conn.execute("""
        SELECT ar.id 
        FROM system_acmeregistration ar
        LEFT JOIN system_acmeregistrationbody arb ON ar.id = arb.acme_id
        WHERE arb.id IS NULL
    """).fetchall()
    
    if orphaned_registrations:
        orphaned_ids = [row[0] for row in orphaned_registrations]

        # Delete orphaned entries from system_acmeregistration
        conn.execute(
            "DELETE FROM system_acmeregistration WHERE id IN ({})".format(
                ','.join('?' * len(orphaned_ids))
            ),
            orphaned_ids
        )


def downgrade():
    # This migration is a cleanup operation, no downgrade needed
    pass
