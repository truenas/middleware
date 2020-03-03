import os
import shutil
from middlewared.utils import osc


def write_certificates(certs, cacerts):
    for cert in certs:
        if not os.path.exists(cert['root_path']):
            os.mkdir(cert['root_path'], 0o755)

        if cert['chain_list']:
            with open(cert['certificate_path'], 'w') as f:
                f.write('\n'.join(cert['chain_list']))

        if cert['privatekey']:
            with open(cert['privatekey_path'], 'w') as f:
                f.write(cert['privatekey'])
            os.chmod(cert['privatekey_path'], 0o400)

        if cert['type'] & 0x20 and cert['CSR']:
            with open(cert['csr_path'], 'w') as f:
                f.write(cert['CSR'])

    """
    Write unified CA certificate file for use with LDAP.
    """
    if not cacerts:
        if osc.IS_FREEBSD:
            ca_root_path = '/usr/local/share/certs/ca-root-nss.crt'
        elif osc.IS_LINUX:
            ca_root_path = '/etc/ssl/certs/ca-certificates.crt'
        else:
            raise NotImplementedError()
        shutil.copyfile(ca_root_path, '/etc/ssl/truenas_cacerts.pem')
    else:
        with open('/etc/ssl/truenas_cacerts.pem', 'w') as f:
            f.write('## USER PROVIDED CA CERTIFICATES ##\n')
            for c in cacerts:
                if cert['chain_list']:
                    f.write('\n'.join(c['chain_list']))
                    f.write('\n\n')


def write_crls(cas, middleware):
    for ca in cas:
        crl = middleware.call_sync(
            'cryptokey.generate_crl',
            ca, list(
                filter(
                    lambda cert: cert['revoked_date'],
                    middleware.call_sync(
                        'certificateauthority.get_ca_chain', ca['id']
                    )
                )
            )
        )
        if crl:
            with open(ca['crl_path'], 'w') as f:
                f.write(crl)


def render(service, middleware):
    certs = middleware.call_sync('certificate.query')
    cas = middleware.call_sync('certificateauthority.query')
    certs.extend(cas)

    write_certificates(certs, cas)

    write_crls(cas, middleware)
