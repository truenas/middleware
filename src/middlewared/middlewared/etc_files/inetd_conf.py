import os
import re

BASE = '/conf/base/etc/'


def inetd_config(middleware):
    with open(os.path.join(BASE, 'services'), 'r') as f:
        service_base = f.read()

    with open(os.path.join(BASE, 'inetd.conf'), 'r') as f:
        inetd_base = f.read()

    inetd_base += '\n' if inetd_base[-1] != '\n' else ''
    service_base += '\n' if service_base[-1] != '\n' else ''

    tftp = middleware.call_sync('tftp.config')
    srv = 'tftp' if tftp['port'] == 69 else 'freenas-tftp'
    srv_exists = re.findall(fr'({srv}.*{tftp["port"]})', service_base)
    cmd = f'tftpd -l -s {tftp["directory"]} -u {tftp["username"]} -U 0{tftp["umask"]} ' \
        f'{tftp["options"]}{" -w" if tftp["newfiles"] else ""}'

    with open('/etc/services', 'w') as f:
        f.write(service_base)
        if not srv_exists:
            f.write(f'{srv}\t\t{tftp["port"]}/udp #Trivial File Transfer\n')

    with open('/etc/inetd.conf', 'w') as f:
        f.write(inetd_base)
        f.write(f'{srv} dgram udp wait root /usr/libexec/tftpd {cmd}\n')

    os.chmod('/etc/services', 0o644)
    os.chmod('/etc/inetd.conf', 0o644)


def render(service, middleware):
    inetd_config(middleware)
