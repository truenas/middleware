import os


def write_certificates(certs):
    for cert in certs:
        if not os.path.exists(cert['root_path']):
            os.mkdir(cert['root_path'], 0o755)

        if cert['chain_list']:
            with open(cert['certificate_path'], 'w') as f:
                f.write('\n'.join(cert['chain_list']))

        if cert['hash_symlink_path']:
            os.symlink(cert['certificate_path'], cert['hash_symlink_path'])

        if cert['privatekey']:
            with open(cert['privatekey_path'], 'w') as f:
                f.write(cert['privatekey'])
            os.chmod(cert['privatekey_path'], 0o400)

        if cert['type'] & 0x20 and cert['CSR']:
            with open(cert['csr_path'], 'w') as f:
                f.write(cert['CSR'])


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

    write_certificates(certs)

    write_crls(cas, middleware)
