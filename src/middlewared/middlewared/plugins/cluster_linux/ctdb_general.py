import ctdb
import json
import os

from middlewared.schema import Bool, Dict, Int, IPAddr, List, returns, Str
from middlewared.service import CallError, Service, accepts, private, filterable
from middlewared.utils import run, filter_list
from middlewared.plugins.cluster_linux.utils import CTDBConfig


CTDB_VOL = CTDBConfig.CTDB_VOL_NAME.value


class CtdbGeneralService(Service):

    class Config:
        namespace = 'ctdb.general'
        cli_namespace = 'service.ctdb.general'

    this_node = None

    @private
    async def wrapper(self, command):

        command.insert(0, 'ctdb')
        command.insert(1, '-j')

        result = {}

        cp = await run(command, check=False)
        if not cp.returncode:
            try:
                result = json.loads(cp.stdout)
            except Exception as e:
                raise CallError(f'ctdb parsing failed with error: {e}')
        else:
            raise CallError(
                f'ctdb command failed with error {cp.stderr.decode().strip()}'
            )

        return result

    @private
    @filterable
    def getdbmap(self, filters, options):
        """
        List all clustered TDB databases that the CTDB daemon has attached to.
        """
        result = ctdb.Client().dbmap()
        return filter_list(result['dbmap'], filters, options)

    @accepts(Dict(
        'ctdb_status',
        Bool('all_nodes', default=True)
    ))
    @returns(Dict(
        'ctdb_status',
        Dict(
            'nodemap',
            Int('node_count'),
            Int('deleted_node_count'),
            List('nodes', items=[Dict(
                'ctdb_nodemap_entry',
                Int('pnn'),
                Dict(
                    'address',
                    Str('type', enum=['INET', 'INET6']),
                    IPAddr("address"),
                ),
                List('flags', items=[Str(
                    'ctdb_status_flag',
                    enum=[
                        'DISCONNECTED',
                        'UNHEALTHY',
                        'INACTIVE',
                        'DISABLED',
                        'STOPPED',
                        'DELETED',
                        'BANNED',
                    ],
                    register=True
                )]),
                Int('flags_raw'),
                Bool('partially_online'),
                Bool('this_node'),
                register=True
            )])
        ),
        Dict(
            'vnnmap',
            Int('size'),
            Int('generation'),
            List('entries', items=[Dict(
                Int('hash'),
                Int('lmaster'),
            )]),
        ),
        Int('recovery_mode_raw'),
        Str('recovery_mode_str', enum=['NORMAL', 'RECOVERY']),
        Int('recovery_master'),
        Bool('all_healthy')
    ))
    def status(self, data):
        """
        List the status of the ctdb cluster.

        `all_nodes`: Boolean if True, return status
            for all nodes in the cluster else return
            status of this node.

        `nodemap` contains the current nodemap in-memory for ctdb daemon on
        this particular cluster node.

        `vnnmap` list of all nodes in the cluster that are participating in
        hosting the cluster databases. BANNED nodes are excluded from vnnmap.

        `recovery_master` the node number of the cluster node that currently
        holds the cluster recovery lock in the ctdb shared volume. This node
        is responsible for performing full cluster checks and cluster node
        consistency. It is also responsible for performing databse recovery
        procedures. Database recovery related logs will be primarily located
        on this node and so troubleshooting cluster health and recovery
        operations should start here.

        `recovery_mode_str` will be either 'NORMAL' or 'RECOVERY' depending
        on whether database recovery is in progress in the cluster.

        `recovery_mode_raw` provides raw the internal raw recovery_state of
        ctdbd. Currently defined values are:
        CTDB_RECOVERY_NORMAL 0
        CTDB_RECOVERY_ACTIVE 1

        `all_healthy` provides a summary of whether all nodes in internal
        nodelist are healthy. This is a convenience feature and not an
        explicit ctdb client response.
        """

        ctdb_status = ctdb.Client().status()
        all_healthy = not any(x['flags_raw'] != 0 for x in ctdb_status['nodemap']['nodes'])
        if not data['all_nodes']:
            new_nodes = []
            for node in ctdb_status['nodemap']['nodes']:
                if node['this_node']:
                    new_nodes = [node]

            ctdb_status['nodemap']['nodes'] = new_nodes

        ctdb_status['all_healthy'] = all_healthy
        return ctdb_status

    @accepts()
    @returns(List('nodelist', items=[Dict(
        'ctdb_node',
        Int('pnn'),
        IPAddr('address'),
        Str('address_type', enum=['INET', 'INET6']),
        Bool('enabled'),
        Bool('this_node')
    )]))
    def listnodes(self):
        """
        Return a list of nodes in the ctdb cluster.
        """
        nodelist = ctdb.Client().listnodes()
        out = []
        for node in nodelist['nodes']:
            private_address = node.private_address
            out.append({
                'pnn': node.pnn,
                'address': private_address['address'],
                'address_type': private_address['type'],
                'enabled': 'DELETED' not in node.flags,
                'this_node': node.current_node,
            })

        return out

    @accepts(Dict(
        'ctdb_ips',
        Bool('all_nodes', default=True)
    ))
    @returns(List('ctdb_public_ips', items=[Dict(
        'ctdb_public_ip',
        IPAddr('public_ip'),
        Int('pnn'),
        List('interfaces', items=[Dict(
            'ctdb_interface_info',
            Str('name'),
            Bool('active'),
            Bool('available')
        )]),
    )]))
    def ips(self, data):
        """
        Return a list of public ip addresses in the ctdb cluster.

        Public IPs will float between nodes in the cluster and
        should automatically rebalance as nodes become available.
        """
        return ctdb.Client().ips(data['all_nodes'])

    @accepts()
    @returns(Bool('status'))
    def healthy(self):
        """
        Returns a boolean if the ctdb cluster is healthy.
        """
        # TODO: ctdb has event scripts that can be run when the
        # health of the cluster has changed. We should use this
        # approach and use a lock on a file as a means of knowing
        # if the cluster status is changing when we try to read it.
        # something like:
        #   writer does this:
        #       health_file = LockFile('/file/on/disk')
        #       open('/file/on/disk').write('True or False')
        #   reader does this:
        #       health_file = LockFile('/file/on/disk')
        #       while not health_file.is_locked():
        #           return bool(open('/file/on/disk', 'r').read())
        # or something...
        try:
            # gluster volume root has inode of 1.
            # if gluster isn't mounted it will be different
            # if volume is unhealthy this will fail
            if os.stat(f'/cluster/{CTDB_VOL}').st_ino != 1:
                return False
        except Exception:
            return False

        try:
            status = self.status()
        except Exception:
            return False

        return status['all_healthy']

    @accepts()
    @returns(Int('pnn'))
    def pnn(self):
        """
        Return node number for this node.
        This value should be static for life of cluster.
        """
        if self.this_node is not None:
            return self.this_node

        try:
            # gluster volume root has inode of 1.
            # if gluster isn't mounted it will be different
            # if volume is unhealthy this will fail
            if os.stat(f'/cluster/{CTDB_VOL}').st_ino != 1:
                return False
        except Exception:
            return False

        self.this_node = ctdb.Client().pnn
        return self.this_node
