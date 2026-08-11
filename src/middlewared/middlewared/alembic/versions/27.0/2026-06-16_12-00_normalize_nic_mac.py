"""Normalize NIC MAC addresses to libvirt's colon-separated form

Revision ID: 4a7e1c9b2f30
Revises: de51ca6f583a
Create Date: 2026-06-16 12:00:00.000000+00:00

"""

# revision identifiers, used by Alembic.
revision = '4a7e1c9b2f30'
down_revision = 'de51ca6f583a'
branch_labels = None
depends_on = None


def upgrade():
    # Superseded by revision 9c31be47d5a2, which runs the same normalization and additionally handles
    # a mac that isn't a string at all. Kept as a no-op so installs that already recorded this revision
    # keep a valid chain.
    pass


def downgrade():
    pass
