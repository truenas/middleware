"""NTS

Revision ID: 04a6293d595a
Revises: 98358f332844
Create Date: 2026-10-01 12:00:00.000000+00:00

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "04a6293d595a"
down_revision = "98358f332844"
branch_labels = None
depends_on = None

# The NTP servers TrueNAS ships with. A new database still has FreeBSD's pool here: the middleware migration
# `0004_ntp_default_servers_linux` only moves them to Debian's once middleware runs.
DEFAULT_SERVERS = (
    frozenset(f"{i}.freebsd.pool.ntp.org" for i in range(3)),
    frozenset(f"{i}.debian.pool.ntp.org" for i in range(3)),
)
# Run by different operators (Cloudflare and SIDN Labs' TimeNL), so that neither one's outage stops time synchronization
NTS_SERVERS = ("time.cloudflare.com", "ntppool1.time.nl")


def should_add_default_nts(addresses, domain_member):
    """Only a system on exactly the TrueNAS default NTP servers gets the default NTS servers.

    While an NTS server is configured, chronyd uses nothing but NTS servers (`authselectmode prefer`), so adding them
    to any other configuration would silently replace time sources an administrator chose. A domain member is left
    alone too: Kerberos needs its clock to agree with the domain controllers'.
    """
    return not domain_member and len(addresses) == 3 and frozenset(addresses) in DEFAULT_SERVERS


def upgrade():
    with op.batch_alter_table("system_ntpserver", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ntp_nts", sa.Boolean(), nullable=False, server_default="0"))

    with op.batch_alter_table("system_security", schema=None) as batch_op:
        batch_op.add_column(sa.Column("require_nts", sa.Boolean(), nullable=False, server_default="0"))

    conn = op.get_bind()
    addresses = [row[0] for row in conn.execute(sa.text("SELECT ntp_address FROM system_ntpserver"))]
    domain_member = conn.execute(sa.text(
        "SELECT 1 FROM directoryservices WHERE enable = 1 AND service_type IN ('ACTIVEDIRECTORY', 'IPA')"
    )).first() is not None
    if should_add_default_nts(addresses, domain_member):
        for address in NTS_SERVERS:
            conn.execute(
                sa.text(
                    "INSERT INTO system_ntpserver "
                    "(ntp_address, ntp_burst, ntp_iburst, ntp_prefer, ntp_minpoll, ntp_maxpoll, ntp_nts) "
                    "VALUES (:address, 0, 1, 0, 6, 10, 1)"
                ),
                {"address": address},
            )


def downgrade():
    with op.batch_alter_table("system_security", schema=None) as batch_op:
        batch_op.drop_column("require_nts")

    with op.batch_alter_table("system_ntpserver", schema=None) as batch_op:
        batch_op.drop_column("ntp_nts")
