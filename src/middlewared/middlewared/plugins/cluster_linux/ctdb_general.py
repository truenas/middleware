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
    @returns(List('ctdb_status', items=[Dict(
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
    )]))
    def status(self, data):
        """
        List the status of nodes in the ctdb cluster.

        `all_nodes`: Boolean if True, return status
            for all nodes in the cluster else return
            status of this node.
        """

        ctdb_status = ctdb.Client().status()
        if not data['all_nodes']:
            for node in ctdb_status['nodemap']['nodes']:
                if node['this_node']:
                    return [node]

        return ctdb_status['nodemap']['nodes']

    @accepts()
    @returns(List('nodelist', items=[Dict(
        'ctdb_node',
        Int('pnn'),
        Dict(
            'address',
            Str('type', enum=['INET', 'INET6']),
            IPAddr("address"),
        ),
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
            out.append({
                'pnn': node.pnn,
                'address': node.private_address,
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

        return not any(map(lambda x: x['flags_raw'] != 0, status)) if status else False

    @accepts()
    @returns(Int('pnn'))
    def pnn(self):
        """
        Return node number for this node. This value should be static for life of cluster.
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
