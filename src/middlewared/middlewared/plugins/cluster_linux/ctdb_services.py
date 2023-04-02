import errno
import json
import os
import pyglfs

from copy import deepcopy
from middlewared.plugins.cluster_linux.utils import CTDBConfig
from middlewared.plugins.gluster_linux.pyglfs_utils import glfs, DEFAULT_GLFS_OPTIONS, lock_file_open
from middlewared.schema import Dict, Str, Bool
from middlewared.service import accepts, filterable, Service
from middlewared.service_exception import CallError
from middlewared.utils import filter_list

CTDB_MONITORED_SERVICES = ['cifs']
CTDB_SERVICE_DEFAULTS = {srv: {
    'name': srv,
    'service_enable': False,
    'monitor_enable': False,
    'cluster_state': []
} for srv in CTDB_MONITORED_SERVICES}


class CtdbServicesService(Service):

    class Config:
        namespace = 'ctdb.services'
        private = True

    def read_node_specific_status(self, parent, pnn):
        obj = parent.lookup(f'{CTDBConfig.CLUSTERED_SERVICES.value}.{pnn}')
        with lock_file_open(obj, os.O_RDONLY):
            return json.loads(obj.contents().decode())

    def get_node_service_status(self, parent):
        out = []
        for node in self.middleware.call_sync('ctdb.general.listnodes'):
            try:
                out.append({'pnn': node['pnn'], 'status': self.read_node_specific_status(parent, node['pnn'])})
            except pyglfs.GLFSError as e:
                if e.errno != errno.ENOENT:
                    raise

                out.append({'pnn': node['pnn'], 'status': {}})
            except json.decoder.JSONDecodeError:
                self.logger.warning('Service status file for node %d could not be parsed', node['pnn'])
                out.append({'pnn': node['pnn'], 'status': {}})

        return out

    def get_global_state(self, parent, obj):
        if not self.middleware.call_sync('ctdb.general.healthy'):
            raise CallError('Unable to retrieve clustered service state while cluster unhealthy', errno.ENXIO)

        if obj.cached_stat.st_size == 0:
            return deepcopy(CTDB_SERVICE_DEFAULTS)

        try:
            with lock_file_open(obj, os.O_RDONLY):
                cl = json.loads(obj.contents().decode())

            for srv in CTDB_MONITORED_SERVICES:
                if srv not in cl:
                    cl[srv] = deepcopy(CTDB_SERVICE_DEFAULTS[srv])

            return cl

        except json.decoder.JSONDecodeError:
            self.logger.warning('failed to parse clustered services state file: %s', obj.contents(), exc_info=True)
            parent.unlink(CTDBConfig.CLUSTERED_SERVICES.value)

        return deepcopy(CTDB_SERVICE_DEFAULTS)

    @filterable
    def get(self, filters, options):
        """
        Get cluster-wide service state for clustered
        services.

        `monitor_enable` service is currently monitored by ctdbd
        `service_enable` monitored service should be enabled
        `pnn` indicates the immutable node number.
        `state` includes following keys:
        `running` - the service is currently running
        `last_check` - timestamp (CLOCK_REALTIME) on `pnn` when state last updated
        `error` - error message from failure (if service isn't running when it should be)
        """
        sv_config = self.middleware.call_sync('ctdb.shared.volume.config')

        with glfs.get_volume_handle(sv_config['volume_name'], DEFAULT_GLFS_OPTIONS) as gl_vol:
            parent = gl_vol.open_by_uuid(sv_config['uuid'])
            try:
                obj = parent.lookup(CTDBConfig.CLUSTERED_SERVICES.value)

            except pyglfs.GLFSError as e:
                if e.errno != errno.ENOENT:
                    raise

                obj = parent.create(CTDBConfig.CLUSTERED_SERVICES.value, os.O_RDWR, mode=0o600)

            cl = self.get_global_state(parent, obj)

            for node in self.get_node_service_status(parent):
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

    @accepts(
        Str('clustered_service', enum=CTDB_MONITORED_SERVICES),
        Dict(
            'clustered_service_config',
            Bool('monitor_enable'),
            Bool('service_enable')
        )
    )
    def set(self, srv, data):
        """
        Private method that enables CTDB monitoring for the specifie
        service. This enables cluster-wide.
        """
        sv_config = self.middleware.call_sync('ctdb.shared.volume.config')

        with glfs.get_volume_handle(sv_config['volume_name'], DEFAULT_GLFS_OPTIONS) as gl_vol:
            parent = gl_vol.open_by_uuid(sv_config['uuid'])
            try:
                obj = parent.lookup(CTDBConfig.CLUSTERED_SERVICES.value)
            except pyglfs.GLFSError as e:
                if e.errno != errno.ENOENT:
                    raise

                obj = parent.create(CTDBConfig.CLUSTERED_SERVICES.value, os.O_RDWR, mode=0o600)

            current_state = self.get_global_state(parent, obj)
            current_service_config = {
                'monitor_enable': current_state[srv]['monitor_enable'],
                'service_enable': current_state[srv]['service_enable']
            }
            if data != current_service_config:
                current_state[srv]['monitor_enable'] = data['monitor_enable']
                current_state[srv]['service_enable'] = data['service_enable']

            with lock_file_open(obj, os.O_RDWR) as fd:
                fd.ftruncate(0)
                fd.pwrite(json.dumps(current_state).encode(), 0)
                fd.fsync()
