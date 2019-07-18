import os


def write_certificates(certs):
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


async def render(service, middleware):
    certs = await middleware.call('certificate.query')
    certs.extend((await middleware.call('certificateauthority.query')))

    await middleware.run_in_thread(write_certificates, certs)
