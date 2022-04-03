import itertools
import os
import shutil
import subprocess

from middlewared.main import Middleware
from middlewared.service import CallError, Service


def write_certificates(certs: list, cacerts: list) -> set:
    expected_files = set()
    for cert in certs:
        if cert['chain_list']:
            expected_files.add(cert['certificate_path'])
            with open(cert['certificate_path'], 'w') as f:
                f.write('\n'.join(cert['chain_list']))

        if cert['privatekey']:
            expected_files.add(cert['privatekey_path'])
            with open(cert['privatekey_path'], 'w') as f:
                os.fchmod(f.fileno(), 0o400)
                f.write(cert['privatekey'])

        if cert['type'] & 0x20 and cert['CSR']:
            expected_files.add(cert['csr_path'])
            with open(cert['csr_path'], 'w') as f:
                f.write(cert['CSR'])

    trusted_cas_path = '/usr/local/share/ca-certificates'
    shutil.rmtree(trusted_cas_path, ignore_errors=True)
    os.makedirs(trusted_cas_path)
    for ca in filter(lambda c: c['chain_list'] and c['add_to_trusted_store'], cacerts):
        with open(os.path.join(trusted_cas_path, f'{ca["name"]}.crt'), 'w') as f:
            f.write('\n'.join(ca['chain_list']))

    cp = subprocess.Popen('update-ca-certificates', stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    err = cp.communicate()[1]
    if cp.returncode:
        raise CallError(f'Failed to update system\'s trusted certificate store: {err.decode()}')

    return expected_files


def write_crls(cas: list, middleware: Middleware) -> set:
    expected_files = set()
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
            expected_files.add(ca['crl_path'])
            with open(ca['crl_path'], 'w') as f:
                f.write(crl)

    return expected_files


def render(service: Service, middleware: Middleware) -> None:
    os.makedirs('/etc/certificates', 0o755, exist_ok=True)
    os.makedirs('/etc/certificates/CA', 0o755, exist_ok=True)

    expected_files = {'/etc/certificates/CA'}
    certs = middleware.call_sync('certificate.query')
    cas = middleware.call_sync('certificateauthority.query')

    expected_files |= write_certificates(certs + cas, cas)
    expected_files |= write_crls(cas, middleware)

    # We would like to remove certificates which have been deleted
    found_files = set(itertools.chain(
        map(lambda f: '/etc/certificates/' + f, os.listdir('/etc/certificates')),
        map(lambda f: '/etc/certificates/CA/' + f, os.listdir('/etc/certificates/CA'))
    ))
    for to_remove in found_files - expected_files:
        if os.path.isdir(to_remove):
            shutil.rmtree(to_remove)
        else:
            os.unlink(to_remove)
