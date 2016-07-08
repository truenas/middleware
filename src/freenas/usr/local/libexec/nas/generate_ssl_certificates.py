#!/usr/local/bin/python
from middlewared.client import Client
from middlewared.client.utils import Struct

import os
import sys


def write_certificates(certs):
    for cert in certs:
        if not os.path.exists(cert['cert_root_path']):
            os.mkdir(cert['cert_root_path'], 0755)

        if cert['cert_chain_list']:
            with open(cert['cert_certificate_path'], 'w') as f:
                for i in cert['cert_chain_list']:
                    f.write(i)

        if cert['cert_privatekey']:
            with open(cert['cert_privatekey_path'], 'w') as f:
                f.write(cert['cert_privatekey'])
            os.chmod(cert['cert_privatekey_path'], 0400)

        if cert['cert_type'] & 0x20 and cert['cert_CSR']:
            with open(cert['cert_csr_path'], 'w') as f:
                f.write(cert['cert_CSR'])


def main():
    client = Client()

    certs = client.call('certificate.query')
    write_certificates(certs)

    certs = client.call('certificateauthority.query')
    write_certificates(certs)

if __name__ == '__main__':
    main()
