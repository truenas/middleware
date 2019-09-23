# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from collections import defaultdict
from subprocess import Popen, PIPE
import itertools
import json
import os
import shutil
import textwrap

from middlewared.utils import filter_list


def render(service, middleware):
    failover_json = '/tmp/failover.json'
    try:
        os.unlink(failover_json)
    except OSError:
        pass

    failovercfg = middleware.call_sync('failover.config')
    pools = middleware.call_sync('pool.query')
    interfaces = middleware.call_sync('interface.query')

    data = {
        'disabled': failovercfg['disabled'],
        'master': failovercfg['master'],
        'timeout': failovercfg['timeout'],
        'groups': defaultdict(list),
        'volumes': [
            i['name'] for i in filter_list(pools, [('encrypt', '<', 2)])
        ],
        'phrasedvolumes': [
            i['name'] for i in filter_list(pools, [('encrypt', '=', 2)])
        ],
        'non_crit_interfaces': [
            i['id'] for i in filter_list(interfaces, [
                ('failover_virtual_aliases', '!=', []),
                ('failover_critical', '=', True),
            ])
        ],
        'internal_interfaces': middleware.call_sync('failover.internal_interfaces'),
    }

    for i in filter_list(interfaces, [('failover_critical', '=', True)]):
        data['groups'][i['failover_group']].append(i['id'])

    with open(failover_json, 'w+') as fh:
        fh.write(json.dumps(data))

    ips = list(map(
        lambda x: x['address'],
        itertools.chain(*[
            i['failover_virtual_aliases'] for i in interfaces
        ]),
    ))

    # Cook data['ips'] which will be empty in the single
    # head case.  Bug #16116
    if not ips:
        ips = ['0.0.0.0']

    ssh = middleware.call_sync('ssh.config')
    general = middleware.call_sync('system.general.config')

    with open('/etc/pf.conf.block', 'w+') as f:
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

    Popen(['pfctl', '-f', '/etc/pf.conf.block'], stderr=PIPE, stdout=PIPE).communicate()

    shutil.copy('/conf/base/etc/devd.conf', '/etc/devd.conf')
    if middleware.call_sync('failover.licensed'):
        # TODO: use devd hook in failover plugin
        with open('/etc/devd.conf', 'a') as f:
            f.write(textwrap.dedent(r'''
                notify 100 {
                   match "system"   "CARP";
                   match "subsystem"      "[0-9]+@[0-9a-z]+";
                   action "/usr/local/bin/python /usr/local/libexec/truenas/carp-state-change-hook.py \$subsystem \$type";
                };'''))
