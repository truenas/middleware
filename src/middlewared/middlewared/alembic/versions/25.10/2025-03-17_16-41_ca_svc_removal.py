"""
Remove CA plugin

Revision ID: 9a5b103ec2e4
Revises: cf1f98f4c3b1
Create Date: 2025-03-17 16:41:53.749089+00:00

"""
import datetime
import dateutil
import dateutil.parser
import re
from OpenSSL import crypto

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = '9a5b103ec2e4'
down_revision = 'cf1f98f4c3b1'
branch_labels = None
depends_on = None

'''
Okay so what we would like to do here is essentially are the following steps:

1. Update certificate attr for both certs/cas to include complete chain
2. While doing (1), make sure we adjust cert types of certs too to existing certs only
3. Copy over CAs to certs table
4. Drop cert_signedby_id from both tables and revoked date column from cert table
5. Update usages of CA foreign key to certs table
6. Drop CA table
'''

CA_TYPE_EXISTING = 0x01
CA_TYPE_INTERNAL = 0x02
CA_TYPE_INTERMEDIATE = 0x04
CERT_TYPE_EXISTING = 0x08
CERT_TYPE_INTERNAL = 0x10
CERT_TYPE_CSR = 0x20
IPA_CA_CERT_NAME = 'IPA_DOMAIN_CACERT'
RE_CERTIFICATE = re.compile(r"(-{5}BEGIN[\s\w]+-{5}[^-]+-{5}END[\s\w]+-{5})+", re.M | re.S)
UPGRADE_CA_PREFIX = 'MIGRATED_CA_'


def get_cert_name(ca_name: str, certs: dict) -> str:
    ca_name = f'{UPGRADE_CA_PREFIX}{ca_name}'
    suffix = 2
    while ca_name in certs:
        ca_name = f'{UPGRADE_CA_PREFIX}{ca_name}_{suffix}'

    return ca_name


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
    cas = {ca['id']: ca for ca in [r._asdict() for r in conn.execute(text("SELECT * FROM system_certificateauthority")).fetchall()]}
    for cert in [r._asdict() for r in conn.execute(text("SELECT * FROM system_certificate")).fetchall()]:
        chain = get_chain_list(cert, cas)
        if not chain:
            continue

        public_key = '\n'.join(chain)
        cert_type = cert['cert_type']
        if cert_type != CERT_TYPE_CSR:
            cert_type = CERT_TYPE_EXISTING

        conn.execute(
            sa.text("UPDATE system_certificate SET cert_certificate = :cert, cert_type = :cert_type WHERE id = :id"),
            {'cert': public_key, 'id': cert['id'], 'cert_type': cert_type}
        )

    for ca in cas.values():
        chain = get_chain_list(ca, cas)
        if not chain:
            continue

        public_key = '\n'.join(chain)
        conn.execute(
            sa.text("UPDATE system_certificateauthority SET cert_certificate = :cert WHERE id = :id"),
            {'cert': public_key, 'id': ca['id']}
        )

    # We are going to migrate CAs to cert table now
    certs = {cert['cert_name']: cert for cert in [r._asdict() for r in conn.execute(text("SELECT * FROM system_certificate")).fetchall()]}
    cas = {ca['id']: ca for ca in [r._asdict() for r in conn.execute(text("SELECT * FROM system_certificateauthority")).fetchall()]}
    cas_id_to_name_mapping = {}
    for ca in cas.values():
        if ca['cert_name'] == IPA_CA_CERT_NAME:
            if IPA_CA_CERT_NAME in certs:
                # This should not happen but covering edge case just to be sure
                continue
            else:
                # We treat this specially because that is how it is being consumed in ipa join mixin
                new_cert_name = IPA_CA_CERT_NAME
        else:
            new_cert_name = get_cert_name(ca['cert_name'], certs)

        cas_id_to_name_mapping[ca['id']] = new_cert_name
        conn.execute(sa.text("""
                INSERT INTO system_certificate (
                    cert_type, cert_name, cert_certificate, cert_privatekey, cert_add_to_trusted_store
                ) VALUES (
                    :cert_type, :cert_name, :cert_certificate, :cert_privatekey, :cert_add_to_trusted_store
                )
            """), {
            'cert_type': CERT_TYPE_EXISTING,
            'cert_name': cas_id_to_name_mapping[ca['id']],
            'cert_certificate': ca['cert_certificate'],
            'cert_privatekey': ca['cert_privatekey'],
            'cert_add_to_trusted_store': ca['cert_add_to_trusted_store'],
        })

    with op.batch_alter_table('system_certificate', schema=None) as batch_op:
        batch_op.drop_index('ix_system_certificate_cert_signedby_id')
        batch_op.drop_column('cert_signedby_id')
        batch_op.drop_column('cert_revoked_date')

    with op.batch_alter_table('system_certificateauthority', schema=None) as batch_op:
        batch_op.drop_index('ix_system_certificateauthority_cert_signedby_id')
        batch_op.drop_column('cert_signedby_id')

    certs = {cert['cert_name']: cert for cert in [r._asdict() for r in conn.execute(text("SELECT * FROM system_certificate")).fetchall()]}
    kmip_config = next(
        iter([r._asdict() for r in conn.execute(text("SELECT * FROM system_kmip")).fetchall()]), {'certificate_authority_id': None}
    )
    # We need to set existing usages to NULL
    conn.execute(text('UPDATE system_kmip SET certificate_authority_id = NULL'))

    with op.batch_alter_table('system_kmip', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_system_kmip_certificate_authority_id_system_certificateauthority',
            type_='foreignkey'
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_system_kmip_certificate_authority_id_system_certificate'),
            'system_certificate',
            ['certificate_authority_id'],
            ['id']
        )

    if kmip_config['certificate_authority_id'] is not None:
        conn.execute(
            sa.text("UPDATE system_kmip SET certificate_authority_id = :id WHERE certificate_authority_id IS NULL"),
            {'id': certs[cas_id_to_name_mapping[kmip_config['certificate_authority_id']]]['id']}
        )

    # Finally dropping CA table
    op.drop_table('system_certificateauthority')


def downgrade():
    pass
