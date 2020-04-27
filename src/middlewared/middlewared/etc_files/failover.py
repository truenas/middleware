# Copyright (c) 2020 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from collections import defaultdict
import json
import os

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
