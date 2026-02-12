import os
import shutil
import subprocess

from middlewared.main import Middleware
from middlewared.service import CallError, Service
from middlewared.utils.io import atomic_write


def write_certificates(certs: list) -> set:
    expected_files = set()
    for cert in certs:
        if cert['chain_list']:
            expected_files.add(cert['certificate_path'])
            with atomic_write(cert['certificate_path'], 'w') as f:
                f.write('\n'.join(cert['chain_list']))

        if cert['privatekey']:
            expected_files.add(cert['privatekey_path'])
            with atomic_write(cert['privatekey_path'], 'w', perms=0o400) as f:
                f.write(cert['privatekey'])

        if cert['type'] & 0x20 and cert['CSR']:
            expected_files.add(cert['csr_path'])
            with atomic_write(cert['csr_path'], 'w') as f:
                f.write(cert['CSR'])

    # trusted_cas_path is a ZFS dataset mountpoint and so it does
    # not need to be recreated after the rmtree. This call is simply
    # to forcibly remove all locally-added CAs.
    trusted_cas_path = '/var/local/ca-certificates'
    shutil.rmtree(trusted_cas_path, ignore_errors=True)
    for cert in filter(lambda c: c['chain_list'] and c['add_to_trusted_store'], certs):
        with atomic_write(os.path.join(trusted_cas_path, f'cert_{cert["name"]}.crt'), 'w') as f:
            f.write('\n'.join(cert['chain_list']))

    cp = subprocess.Popen('update-ca-certificates', stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    err = cp.communicate()[1]
    if cp.returncode:
        raise CallError(f'Failed to update system\'s trusted certificate store: {err.decode()}')

    return expected_files


def render(service: Service, middleware: Middleware) -> None:
    os.makedirs('/etc/certificates', 0o755, exist_ok=True)

    expected_files = set()
    certs = middleware.call_sync('certificate.query')

    expected_files |= write_certificates(certs)

    # We would like to remove certificates which have been deleted
    found_files = {'/etc/certificates/' + f for f in os.listdir('/etc/certificates')}
    for to_remove in found_files - expected_files:
        if os.path.isdir(to_remove):
            shutil.rmtree(to_remove)
        else:
            os.unlink(to_remove)
