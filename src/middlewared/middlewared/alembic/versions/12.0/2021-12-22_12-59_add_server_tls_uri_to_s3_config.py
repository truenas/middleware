"""Add tls_server_uri to s3 config

Revision ID: 9c11f6c6f152
Revises: fee786dfe121
Create Date: 2021-12-22 12:59:17.737066+00:00
"""
import re

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from OpenSSL import crypto

# revision identifiers, used by Alembic.
revision = '9c11f6c6f152'
down_revision = 'fee786dfe121'
branch_labels = None
depends_on = None

# Pattern is taken from middlewared.validators.Hostname
hostname_re = re.compile(r'^[a-z\.\-0-9]*[a-z0-9]$', flags=re.IGNORECASE)


def is_valid_hostname(hostname: str):
    """
    Validates hostname and makes sure it
    does not contain a wild card.
    """
    return hostname_re.match(hostname)


def upgrade():
    with op.batch_alter_table('services_s3', schema=None) as batch_op:
        batch_op.add_column(sa.Column('s3_tls_server_uri', sa.String(length=128), nullable=True))

    # Try to get tls_server_uri in following order:
    # 1. SAN from certificate
    # 2. Common name from certificate
    # 3. Fallback to localhost
    conn = op.get_bind()
    if s3_conf := conn.execute(text("SELECT s3_certificate_id FROM services_s3 WHERE s3_certificate_id IS NOT NULL")).fetchone():
        if cert_data := conn.execute("SELECT cert_certificate FROM system_certificate WHERE id = :cert_id", cert_id=s3_conf[0]).fetchone():
            s3_tls_server_uri = 'localhost'
            try:
                cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert_data[0])
                cert_cn = cert.get_subject().CN
                if cert_cn and is_valid_hostname(cert_cn):
                    s3_tls_server_uri = cert_cn

                cert_sans = []
                for ext in filter(lambda e: e.get_short_name().decode() != 'UNDEF', (
                    map(lambda i: cert.get_extension(i), range(cert.get_extension_count()))
                    if isinstance(cert, crypto.X509)
                    else cert.get_extensions()
                )):
                    if 'subjectAltName' == ext.get_short_name().decode():
                        cert_sans = [s.strip() for s in ext.__str__().split(',') if s]

                for cert_san in cert_sans:
                    san = cert_san.split(':')[-1].strip()
                    if san and is_valid_hostname(san):
                        s3_tls_server_uri = san
                        break
            except Exception:
                pass

            conn.execute(
                "UPDATE services_s3 SET s3_tls_server_uri = :s3_tls_server_uri",
                s3_tls_server_uri=s3_tls_server_uri
            )


def downgrade():
    with op.batch_alter_table('services_s3', schema=None) as batch_op:
        batch_op.drop_column('s3_tls_server_uri')
