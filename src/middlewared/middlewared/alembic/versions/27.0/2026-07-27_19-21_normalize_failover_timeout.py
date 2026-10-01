"""Normalize failover timeout to at most 120 seconds

Values above 120 produce a VRRPv3 advertisement interval larger than the
protocol maximum of 40.95 seconds (RFC 5798 section 5.2.7), which keepalived
rejects, breaking failover entirely.

Revision ID: 1dc145b1f6fa
Revises: b3f0a9c41d7e
Create Date: 2026-07-27 19:21:01.865610+00:00

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "1dc145b1f6fa"
down_revision = "b3f0a9c41d7e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE system_failover SET timeout = 120 WHERE timeout > 120")
    op.execute("UPDATE system_failover SET timeout = 0 WHERE timeout < 0")


def downgrade():
    pass
