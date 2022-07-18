import errno
import fcntl
import json
import os

from copy import deepcopy
from middlewared.plugins.cluster_linux.utils import CTDBConfig
from middlewared.service import filterable, Service
from middlewared.service_exception import CallError
from middlewared.utils import filter_list

CTDB_MONITORED_SERVICES = ['cifs']
CTDB_SERVICE_DEFAULTS = {srv: {
    'name': srv,
    'enable': False,
    'cluster_state': []
} for srv in CTDB_MONITORED_SERVICES}


class CtdbServicesService(Service):

    class Config:
        namespace = 'ctdb.services'
        private = True

    def read_node_specific_status(self, pnn):
        with open(f'{CTDBConfig.GM_CLUSTERED_SERVICES.value}.{pnn}', 'r') as f:
            return json.load(f)

    def get_node_service_status(self):
        out = []
        for node in self.middleware.call_sync('ctdb.general.listnodes'):
            try:
                out.append({'pnn': node['pnn'], 'status': self.read_node_specific_status(node['pnn'])})
            except FileNotFoundError:
                out.append({'pnn': node['pnn'], 'status': {}})
            except json.decoder.JSONDecodeError:
                self.logger.warning('Service status file for node %d could not be parsed', node['pnn'])
                out.append({'pnn': node['pnn'], 'status': {}})

        return out

    def get_global_state(self):
        if not self.middleware.call_sync('ctdb.general.healthy'):
            raise CallError('Unable to retrieve clustered service state while cluster unhealthy', errno.ENXIO)

        try:
            with open(CTDBConfig.GM_CLUSTERED_SERVICES.value, 'r') as f:
                fcntl.lockf(f.fileno(), fcntl.LOCK_SH)
                try:
                    cl = json.load(f)
                finally:
                    fcntl.lockf(f.fileno(), fcntl.LOCK_UN)

            for srv in CTDB_MONITORED_SERVICES:
                if srv not in cl:
                    cl[srv] = deepcopy(CTDB_SERVICE_DEFAULTS[srv])

            return cl

        except FileNotFoundError:
            pass

        except json.decoder.JSONDecodeError:
            self.logger.warning('failed to parse clustered services state file', exc_info=True)
            os.unlink(CTDBConfig.GM_CLUSTERED_SERVICES.value)

        return deepcopy(CTDB_SERVICE_DEFAULTS)

    @filterable
    def get(self, filters, options):
        """
        Get cluster-wide service state for clustered
        services.

        `enable` service is currently monitored by ctdbd
        `pnn` indicates the immutable node number.
        `state` includes following keys:
        `running` - the service is currently running
        `last_check` - timestamp (CLOCK_REALTIME) on `pnn` when state last updated
        `error` - error message from failure (if service isn't running when it should be)
        """
        cl = self.get_global_state()

        for node in self.get_node_service_status():
            for srv in cl.keys():
                if srv not in node['status']:
                    cl[srv]['cluster_state'].append({
                        'pnn': node['pnn'],
                        'state': 'UNAVAIL'
                    })
                    continue

                cl[srv]['cluster_state'].append({
                    'pnn': node['pnn'],
                    'state': node['status'][srv]
                })

        return filter_list(list(cl.values()), filters, options)

    def set(self, srv, enabled):
        """
        Private method that enables CTDB monitoring for the specifie
        service. This enables cluster-wide.
        """
        if srv not in CTDB_MONITORED_SERVICES:
            raise CallError(f'{srv}: not a CTDB monitored service')

        current_state = self.get_global_state()

        if current_state[srv]['enable'] != enabled:
            current_state[srv]['enable'] = enabled
            with open(CTDBConfig.GM_CLUSTERED_SERVICES.value, 'w') as f:
                fcntl.lockf(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(json.dumps(current_state))
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.lockf(f.fileno(), fcntl.LOCK_UN)
