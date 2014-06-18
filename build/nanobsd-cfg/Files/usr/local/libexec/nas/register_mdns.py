#!/usr/local/bin/python

import os
import pybonjour
import select
import socket
import sys
import threading

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()


def register(name, regtype, port):
    sdRef = pybonjour.DNSServiceRegister(name=name,
                                         regtype=regtype,
                                         port=port,
                                         callBack=None)
    try:
        try:
            while True:
                ready = select.select([sdRef], [], [])
                if sdRef in ready[0]:
                    pybonjour.DNSServiceProcessResult(sdRef)
        except KeyboardInterrupt:
            pass
    finally:
        sdRef.close()


def main():
    from freenasUI.services.models import services
    from freenasUI.services.models import SSH
    from freenasUI.system.models import Settings

    try:
        hostname = socket.gethostname().split(".")[0]
    except IndexError:
        hostname = socket.gethostname()

    ssh_service = services.objects.filter(srv_service='ssh', srv_enable=1)
    if ssh_service:
        sshport = int(SSH.objects.values('ssh_tcpport')[0]['ssh_tcpport'])
        t = threading.Thread(target=register,
                             args=(hostname, '_ssh._tcp.', sshport))
        t.daemon = False
        t.start()
        t = threading.Thread(target=register,
                             args=(hostname, '_sftp-ssh._tcp.', sshport))
        t.daemon = False
        t.start()

    webui = Settings.objects.values('stg_guiprotocol',
                                    'stg_guiport',
                                    'stg_guihttpsport')

    if (webui[0]['stg_guiprotocol'] == 'http' or
            webui[0]['stg_guiprotocol'] == 'httphttps'):
        http_port = int(webui[0]['stg_guiport'] or 80)
        t = threading.Thread(target=register,
                             args=(hostname, '_http._tcp.', http_port))
        t.daemon = False
        t.start()

    if (webui[0]['stg_guiprotocol'] == 'https' or
            webui[0]['stg_guiprotocol'] == 'httphttps'):
        https_port = int(webui[0]['stg_guihttpsport'] or 443)
        t = threading.Thread(target=register,
                             args=(hostname, '_https._tcp.', https_port))
        t.daemon = False
        t.start()

if __name__ == "__main__":
    main()
