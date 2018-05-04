#!/usr/local/bin/python
from middlewared.client import Client

import os


def write_certificates(certs):
    for cert in certs:
        if not os.path.exists(cert['root_path']):
            os.mkdir(cert['root_path'], 0o755)

        if cert['chain_list']:
            with open(cert['certificate_path'], 'w') as f:
                for i in cert['chain_list']:
                    f.write(i)

        if cert['privatekey']:
            with open(cert['privatekey_path'], 'w') as f:
                f.write(cert['privatekey'])
            os.chmod(cert['privatekey_path'], 0o400)

        if cert['type'] & 0x20 and cert['CSR']:
            with open(cert['csr_path'], 'w') as f:
                f.write(cert['CSR'])


def main():
    client = Client()

    certs = client.call('certificate.query')
    write_certificates(certs)

    certs = client.call('certificateauthority.query')
    write_certificates(certs)

if __name__ == '__main__':
    main()
