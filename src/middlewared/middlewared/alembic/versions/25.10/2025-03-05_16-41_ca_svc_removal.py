"""
Remove CA plugin

Revision ID: 9a5b103ec2e4
Revises: 5fda0931889d
Create Date: 2025-03-05 16:41:53.749089+00:00

"""
import datetime
import dateutil
import dateutil.parser
import re
from OpenSSL import crypto

from alembic import op
import sqlalchemy as sa


revision = '9a5b103ec2e4'
down_revision = '5fda0931889d'
branch_labels = None
depends_on = None

'''
Okay so what we would like to do here is essentially are the following steps:

1. Remove signedby attribute from CA/certs table
2. Make sure cert chain is valid after removal of signedby
'''

CA_TYPE_EXISTING = 0x01
CA_TYPE_INTERNAL = 0x02
CA_TYPE_INTERMEDIATE = 0x04
CERT_TYPE_EXISTING = 0x08
CERT_TYPE_INTERNAL = 0x10
CERT_TYPE_CSR = 0x20
RE_CERTIFICATE = re.compile(r"(-{5}BEGIN[\s\w]+-{5}[^-]+-{5}END[\s\w]+-{5})+", re.M | re.S)


def cert_issuer(cert: dict, cas: dict[str, dict]) -> str | dict | None:
    issuer = None
    if cert['cert_type'] in (CA_TYPE_EXISTING, CERT_TYPE_EXISTING):
        issuer = 'external'
    elif cert['cert_type'] == CA_TYPE_INTERNAL:
        issuer = 'self-signed'
    elif cert['cert_type'] in (CERT_TYPE_INTERNAL, CA_TYPE_INTERMEDIATE):
        issuer = cas[cert['cert_signedby_id']]
    elif cert['cert_type'] == CERT_TYPE_CSR:
        issuer = 'external - signature pending'
    return issuer


def parse_cert_date_string(date_value: str) -> str:
    t1 = dateutil.parser.parse(date_value)
    t2 = t1.astimezone(dateutil.tz.tzlocal())
    return t2.ctime()


def load_certificate(certificate: str) -> bool:
    """
    Just load certificate to ensure it is valid and there is nothing amiss when we build
    cert chains
    """
    try:
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, certificate)
        parse_cert_date_string(cert.get_notBefore())
        parse_cert_date_string(cert.get_notAfter())
        datetime.datetime.now() > datetime.datetime.strptime(
            parse_cert_date_string(cert.get_notAfter()), '%a %b %d %H:%M:%S %Y'
        )
    except (crypto.Error, OverflowError):
        # Overflow error is raised when the certificate has a lifetime which will never expire
        # and we don't support such certificates
        return False
    else:
        return True


def get_chain_list(cert: dict, cas: dict[str, dict]) -> list[str]:
    identified_certs = []
    cert['cert_issuer'] = cert_issuer(cert, cas)
    if len(RE_CERTIFICATE.findall(cert['cert_certificate'] or '')) > 1:
        identified_certs = RE_CERTIFICATE.findall(cert['cert_certificate'])
    elif cert['cert_type'] != CERT_TYPE_CSR:
        identified_certs = [cert['cert_certificate']]
        signing_CA = cert['cert_issuer']
        while signing_CA not in ['external', 'self-signed', 'external - signature pending', None]:
            identified_certs.append(signing_CA['cert_certificate'])
            signing_CA['cert_issuer'] = cert_issuer(signing_CA, cas)
            signing_CA = signing_CA['cert_issuer']

    cert_chain = []
    for c in identified_certs:
        if c and load_certificate(c):
            cert_chain.append(c)
        else:
            break

    return cert_chain


def upgrade():
    conn = op.get_bind()
    cas = {ca['id']: ca for ca in map(dict, conn.execute("SELECT * FROM system_certificateauthority").fetchall())}
    for cert in map(dict, conn.execute("SELECT * FROM system_certificate").fetchall()):
        chain = get_chain_list(cert, cas)
        if not chain:
            continue

        public_key = '\n'.join(chain)
        conn.execute(
            sa.text("UPDATE system_certificate SET cert_certificate = :cert WHERE id = :id"),
            {'cert': public_key, 'id': cert['id']}
        )

    for ca in cas:
        chain = get_chain_list(ca, cas)
        if not chain:
            continue

        public_key = '\n'.join(chain)
        conn.execute(
            sa.text("UPDATE system_certificateauthority SET cert_certificate = :cert WHERE id = :id"),
            {'cert': public_key, 'id': ca['id']}
        )

    with op.batch_alter_table('system_certificate', schema=None) as batch_op:
        batch_op.drop_index('ix_system_certificate_cert_signedby_id')
        batch_op.drop_column('cert_signedby_id')

    with op.batch_alter_table('system_certificateauthority', schema=None) as batch_op:
        batch_op.drop_index('ix_system_certificateauthority_cert_signedby_id')
        batch_op.drop_column('cert_signedby_id')


def downgrade():
    pass
