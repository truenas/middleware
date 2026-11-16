"""NTS

Revision ID: 04a6293d595a
Revises: 6d08137a3def
Create Date: 2026-11-12 12:00:00.000000+00:00

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "04a6293d595a"
down_revision = "6d08137a3def"
branch_labels = None
depends_on = None


def is_single_word(address):
    """Whether the API would take `address`. chronyd reads what follows whitespace in a `server` line as options, and
    what follows a line break as directives of its own."""
    return bool(address) and not any(c.isspace() for c in address)


def upgrade():
    with op.batch_alter_table("system_ntpserver", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ntp_nts", sa.Boolean(), nullable=False, server_default="0"))

    with op.batch_alter_table("system_security", schema=None) as batch_op:
        batch_op.add_column(sa.Column("require_nts", sa.Boolean(), nullable=False, server_default="0"))

    conn = op.get_bind()
    servers = conn.execute(sa.text("SELECT id, ntp_address FROM system_ntpserver")).fetchall()

    # Stored before the API took only single words
    for id_, address in servers:
        if not is_single_word(address):
            conn.execute(sa.text("DELETE FROM system_ntpserver WHERE id = :id"), {"id": id_})


def downgrade():
    with op.batch_alter_table("system_security", schema=None) as batch_op:
        batch_op.drop_column("require_nts")

    with op.batch_alter_table("system_ntpserver", schema=None) as batch_op:
        batch_op.drop_column("ntp_nts")
