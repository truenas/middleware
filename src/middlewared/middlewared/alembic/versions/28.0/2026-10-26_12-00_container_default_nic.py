"""Give containers without a NIC device one on the configured bridge

Revision ID: c9ebd3e3cfbc
Revises: 2f08b4c7a1d9
Create Date: 2026-10-26 12:00:00.000000+00:00

"""

# revision identifiers, used by Alembic.
revision = "c9ebd3e3cfbc"
down_revision = "2f08b4c7a1d9"
branch_labels = None
depends_on = None


def upgrade():
    # Superseded by revision 36eb34176424, which adds the default NIC. Kept as a no-op so installs that already
    # recorded this revision keep a valid chain, and so a 27.0 install that ran 36eb34176424 does not get a NIC
    # added again to containers left without one.
    pass


def downgrade():
    pass
