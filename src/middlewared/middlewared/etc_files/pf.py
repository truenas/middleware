# Copyright (c) 2020 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from subprocess import Popen, PIPE
import os
import itertools

PF_BLOCK_FILE = '/etc/pf.conf.block'


def render(service, middleware):

    if not middleware.call_sync('failover.licensed'):
        if os.path.exists(PF_BLOCK_FILE):
            try:
                os.unlink(PF_BLOCK_FILE)
            except Exception as e:
                middleware.logger.warning(
                    f'Failed to remove {PF_BLOCK_FILE} with error: {e}'
                )
                pass
        return

    interfaces = middleware.call_sync('interface.query')

    ips = list(map(
        lambda x: x['address'],
        itertools.chain(*[
            i['failover_virtual_aliases'] for i in interfaces
        ]),
    ))

    ssh = middleware.call_sync('ssh.config')
    general = middleware.call_sync('system.general.config')

    with open(PF_BLOCK_FILE, 'w+') as f:
        f.write('set block-policy drop\n')
        f.write('''
ips = '{ %(ips)s }'
ports = '{ %(ssh)s, %(http)s, %(https)s }'
pass in quick proto tcp from any to any port $ports
block drop in quick proto tcp from any to $ips
block drop in quick proto udp from any to $ips\n''' % {
            'ssh': ssh['tcpport'],
            'http': general['ui_port'],
            'https': general['ui_httpsport'],
            'ips': ', '.join(ips),
        })

    Popen(['pfctl', '-f', PF_BLOCK_FILE], stderr=PIPE, stdout=PIPE).communicate()
