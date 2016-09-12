#!/usr/local/bin/python
from middlewared.client import Client

import pybonjour
import select
import socket
import threading


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
    client = Client()

    try:
        hostname = socket.gethostname().split(".")[0]
    except IndexError:
        hostname = socket.gethostname()

    ssh_service = client.call('datastore.query', 'services.services', [('srv_service', '=', 'ssh'), ('srv_enable', '=', True)])
    if ssh_service:
        sshport = client.call('datastore.query', 'services.ssh', None, {'get': True})['ssh_tcpport']
        t = threading.Thread(target=register,
                             args=(hostname, '_ssh._tcp.', sshport))
        t.daemon = False
        t.start()
        t = threading.Thread(target=register,
                             args=(hostname, '_sftp-ssh._tcp.', sshport))
        t.daemon = False
        t.start()

    webui = client.call('datastore.query', 'system.settings')

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
