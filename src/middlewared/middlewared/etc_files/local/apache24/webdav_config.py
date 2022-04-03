import re
import os
import secrets
import hashlib
import crypt

from contextlib import suppress
from middlewared.plugins.etc import EtcUSR, EtcGRP
from string import digits, ascii_uppercase, ascii_lowercase


def generate_webdav_auth(middlewared, render_ctx, dirfd):
    def salt():
        letters = f'{ascii_lowercase}{ascii_uppercase}{digits}/.'
        return '$6${0}'.format(''.join([secrets.choice(letters) for i in range(16)]))

    def remove_auth(dirfd):
        with suppress(FileNotFoundError):
            os.remove('webdavhtbasic', dir_fd=dirfd)

        with suppress(FileNotFoundError):
            os.remove('webdavhtdigest', dir_fd=dirfd)

    auth_type = render_ctx['webdav.config']['htauth'].upper()
    password = render_ctx['webdav.config']['password']

    if auth_type not in ['NONE', 'BASIC', 'DIGEST']:
        remove_auth(dirfd)
        raise ValueError("Invalid auth_type (must be one of 'NONE', 'BASIC', 'DIGEST')")

    if auth_type == 'BASIC':
        with suppress(FileNotFoundError):
            os.remove('webdavhtdigest', dir_fd=dirfd)

        with open(os.open('webdavhtbasic', os.O_WRONLY | os.O_CREAT | os.O_TRUNC, dir_fd=dirfd), 'w') as f:
            os.fchmod(f.fileno(), 0o600)
            os.fchown(f.fileno(), EtcUSR.WEBDAV, EtcGRP.WEBDAV)
            f.write(f'webdav:{crypt.crypt(password, salt())}')

    elif auth_type == 'DIGEST':
        with suppress(FileNotFoundError):
            os.remove('webdavhtbasic', dir_fd=dirfd)

        with open(os.open('webdavhtdigest', os.O_WRONLY | os.O_CREAT | os.O_TRUNC, dir_fd=dirfd), 'w') as f:
            os.fchmod(f.fileno(), 0o600)
            os.fchown(f.fileno(), EtcUSR.WEBDAV, EtcGRP.WEBDAV)
            f.write(
                "webdav:webdav:{0}".format(hashlib.md5(f"webdav:webdav:{password}".encode()).hexdigest())
            )

    else:
        remove_auth(dirfd)


def generate_webdav_config(middleware, render_ctx, dirfd):
    webdav_config = render_ctx['webdav.config']
    to_blank = None

    if webdav_config['protocol'] in ('HTTPS', 'HTTPHTTPS'):
        middleware.call_sync('certificate.cert_services_validation', webdav_config['certssl'], 'webdav.certssl')

        with open(os.open('Includes/webdav.conf', os.O_RDONLY, dir_fd=dirfd), 'r') as f:
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
            f'SSLProtocol +TLSv1.2 +TLSv1.3\n\t\t'
            f'SSLCipherSuite HIGH:MEDIUM\n\n',
            data
        )

        with open(os.open('Includes/webdav-ssl.conf', os.O_WRONLY | os.O_CREAT | os.O_TRUNC, dir_fd=dirfd), 'w') as f:
            f.write(data)

        if webdav_config['protocol'] == 'HTTPS':
            to_blank = 'Includes/webdav.conf'

    elif webdav_config['protocol'] == 'HTTP':
        to_blank = 'Includes/webdav-ssl.conf'

    if to_blank is not None:
        try:
            fd = os.open(to_blank, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, dir_fd=dirfd)
        finally:
            os.close(fd)


def render(service, middleware, render_ctx):
    dirfd = os.open("/etc/apache2", os.O_PATH | os.O_DIRECTORY)
    try:
        generate_webdav_config(middleware, render_ctx, dirfd)
        generate_webdav_auth(middleware, render_ctx, dirfd)
    finally:
        os.close(dirfd)
