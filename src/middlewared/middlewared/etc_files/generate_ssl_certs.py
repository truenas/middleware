import os
import shutil
import subprocess

from middlewared.service import CallError


def write_certificates(certs, cacerts):
    for cert in certs:
        if cert['chain_list']:
            with open(cert['certificate_path'], 'w') as f:
                f.write('\n'.join(cert['chain_list']))

        if cert['privatekey']:
            with open(cert['privatekey_path'], 'w') as f:
                os.fchmod(f.fileno(), 0o400)
                f.write(cert['privatekey'])

        if cert['type'] & 0x20 and cert['CSR']:
            with open(cert['csr_path'], 'w') as f:
                f.write(cert['CSR'])

    trusted_cas_path = '/usr/local/share/ca-certificates'
    shutil.rmtree(trusted_cas_path, ignore_errors=True)
    os.makedirs(trusted_cas_path)
    for ca in filter(lambda c: c['chain_list'] and c['add_to_trusted_store'], cacerts):
        with open(os.path.join(trusted_cas_path, f'{ca["name"]}.crt'), 'w') as f:
            f.write('\n'.join(cert['chain_list']))

    cp = subprocess.Popen('update-ca-certificates', stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    err = cp.communicate()[1]
    if cp.returncode:
        raise CallError(f'Failed to update system\'s trusted certificate store: {err.decode()}')


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
    os.makedirs('/etc/certificates', 0o755, exist_ok=True)
    os.makedirs('/etc/certificates/CA', 0o755, exist_ok=True)

    certs = middleware.call_sync('certificate.query')
    cas = middleware.call_sync('certificateauthority.query')
    certs.extend(cas)

    write_certificates(certs, cas)

    write_crls(cas, middleware)
