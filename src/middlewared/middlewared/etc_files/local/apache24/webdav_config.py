import re


def empty_webdav_config_files():
    path = '/usr/local/etc/apache24/Includes/'
    for p in [path + 'webdav.conf', path + 'webdav-ssl.conf']:
        with open(p, 'w') as f:
            f.write('')


def generate_webdav_config(middleware):
    webdav_config = middleware.call_sync('webdav.config')
    if webdav_config['protocol'] in ('HTTPS', 'HTTPHTTPS'):
        with open('/usr/local/etc/apache24/Includes/webdav.conf', 'r') as f:
            data = f.read()

        data = re.sub(
            'Listen .*\n',
            f'Listen {webdav_config["tcpportssl"]}\n\t'
            f'<VirtualHost *:8081>\n\t\tSSLEngine on\n\t\t'
            f'SSLCertificateFile "{webdav_config["certssl"]["certificate_path"]}"\n\t\t'
            f'SSLCertificateKeyFiile "${webdav_config["certssl"]["privatekey_path"]}"\n\t\t'
            f'SSLProtocol +TLSv1 +TLSv1.1 +TLSv1.2\n\t\t'
            f'SSLCipherSuite HIGH:MEDIUM\n\n',
            data
        )

        with open('/usr/local/etc/apache24/Includes/webdav-ssl.conf', 'w') as f:
            f.write(data)

        if webdav_config['protocol'] == 'HTTPS':
            # Empty webdav.conf
            with open('/usr/local/etc/apache24/Includes/webdav.conf', 'w') as f:
                f.write('')


async def render(service, middleware):

    if (await middleware.call('service.query', [['service', '=', 'webdav']]))['state'] != 'RUNNING':
        await middleware.run_in_thread(empty_webdav_config_files)
    else:
        await middleware.run_in_thread(generate_webdav_config, middleware)
