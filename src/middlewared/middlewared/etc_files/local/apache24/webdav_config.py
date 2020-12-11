import re
from middlewared.utils import osc


def generate_webdav_config(service, middleware):
    webdav_config = middleware.call_sync('webdav.config')
    apache_dir = service.APACHE_DIR.replace('local/', '')
    if osc.IS_LINUX:
        apache_dir = f'/etc/{apache_dir}'
    elif osc.IS_FREEBSD:
        apache_dir = f'/usr/local/etc/{apache_dir}'
    else:
        raise NotImplementedError()

    if webdav_config['protocol'] in ('HTTPS', 'HTTPHTTPS'):
        middleware.call_sync('certificate.cert_services_validation', webdav_config['certssl'], 'webdav.certssl')

        with open(f'{apache_dir}/Includes/webdav.conf', 'r') as f:
            data = f.read()

        webdav_config['certssl'] = middleware.call_sync(
            'certificate.query',
            [['id', '=', webdav_config['certssl']]],
            {'get': True}
        )

        data = re.sub(
            'Listen .*\n\t<VirtualHost.*\n',
            f'Listen {webdav_config["tcpportssl"]}\n\t'
            f'<VirtualHost *:{webdav_config["tcpportssl"]}>\n\t\tSSLEngine on\n\t\t'
            f'SSLCertificateFile "{webdav_config["certssl"]["certificate_path"]}"\n\t\t'
            f'SSLCertificateKeyFile "{webdav_config["certssl"]["privatekey_path"]}"\n\t\t'
            f'SSLProtocol +TLSv1 +TLSv1.1 +TLSv1.2\n\t\t'
            f'SSLCipherSuite HIGH:MEDIUM\n\n',
            data
        )

        with open(f'{apache_dir}/Includes/webdav-ssl.conf', 'w') as f:
            f.write(data)

        if webdav_config['protocol'] == 'HTTPS':
            # Empty webdav.conf
            with open(f'{apache_dir}/Includes/webdav.conf', 'w+') as f:
                pass
    else:
        if webdav_config['protocol'] == 'HTTP':
            # Empty webdav-ssl.conf
            with open(f'{apache_dir}/Includes/webdav-ssl.conf', 'w+') as f:
                pass


def render(service, middleware):
    generate_webdav_config(service, middleware)
