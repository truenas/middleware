"""VM video model

Revision ID: c5c3dfe24ea8
Revises: 09cc64d01836
Create Date: 2026-10-12 13:24:00.000000+00:00

"""

# revision identifiers, used by Alembic.
revision = "c5c3dfe24ea8"
down_revision = "09cc64d01836"
branch_labels = None
depends_on = None


def upgrade():
    # Superseded by revision e2a7c4f19b63, which adds and populates vm_vm.video_model. Kept as a no-op so
    # installs that already recorded this revision keep a valid chain.
    pass


def downgrade():
    pass
