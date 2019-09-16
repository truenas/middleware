import os
import shutil


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
        shutil.copyfile('/usr/local/share/certs/ca-root-nss.crt',
                        '/etc/ssl/truenas_cacerts.pem')
    else:
        with open('/etc/ssl/truenas_cacerts.pem', 'a+') as f:
            f.write('## USER PROVIDED CA CERTIFICATES ##\n')
            for c in cacerts:
                if cert['chain_list']:
                    f.write('\n'.join(c['chain_list']))
                    f.write('\n\n')


async def render(service, middleware):
    certs = await middleware.call('certificate.query')
    cacerts = await middleware.call('certificateauthority.query')
    certs.extend(cacerts)

    await middleware.run_in_thread(write_certificates, certs, cacerts)
