import json
import subprocess

from middlewared.schema import Dict, IPAddr, Int, Bool, Str
from middlewared.service import (accepts, job, filterable,
                                 private, CRUDService, ValidationErrors)
from middlewared.utils import filter_list
from middlewared.plugins.cluster_linux.utils import CTDBConfig
from middlewared.plugins.gluster_linux.utils import get_parsed_glusterd_uuid as get_glusterd_uuid
from middlewared.validators import UUID


PRI_LOCK = CTDBConfig.PRI_LOCK.value


class CtdbPrivateIpService(CRUDService):

    class Config:
        namespace = 'ctdb.private.ips'
        cli_namespace = 'service.ctdb.private.ips'

    @private
    def reload(self):
        """
        Reload the nodes file on the ctdb nodes. This is required when a new
        ctdb node is added or existing one is disabled.
        """
        re = subprocess.run(['ctdb', 'reloadnodes'], check=False, capture_output=True)
        if re.returncode:
            self.logger.warning('Failed to reload nodes file %r', re.stderr.decode())

    @filterable
    def query(self, filters, options):
        """
        This returns contents of the CTDB nodes file (private IP addresses)
        Explanation of keys are as follows:

        `pnn` private node number of the CTDB node. This is a unique identifier
        for this node within the CTDB daemon. It is based on line number in the
        nodes file. Any operation that requires changing node numbers of existing
        nodes will require cluster-wide maintenance window.

        `address` the private address of this node. This _must_ be on an isolated
        network as ctdb traffic is unencrypted.

        `this_node` boolean indicating whether the entry indicated here is this
        particular cluster node

        `node_uuid` the gluster peer uuid of the entry
        """
        ips = []
        node_uuid = get_glusterd_uuid()

        data = self.middleware.call_sync('ctdb.shared.volume.config')
        data['ip_file'] = CTDBConfig.PRIVATE_IP_FILE.value
        for idx, i in enumerate(self.middleware.call_sync('ctdb.ips.contents', data)):
            enabled = not i.startswith('#')
            address = i[1:] if i.startswith('#') else i
            address, gluster_info = address.split('#', 1)
            gluster_info = json.loads(gluster_info)

            ips.append({
                'id': idx,
                'pnn': idx,
                'address': address,
                'enabled': enabled,
                'this_node': gluster_info['uuid'] == node_uuid,
                'node_uuid': gluster_info['uuid']
            })

        return filter_list(ips, filters, options)

    @private
    async def validate_node_uuid(self, schema_name, node_uuid, verrors):
        if not await self.middleware.call('gluster.peer.query', [['uuid', '=', node_uuid]]):
            verrors.add(
                f'{schema_name}.node_uuid', f'{node_uuid}: node does not exist in trusted storage pool'
            )

    @accepts(Dict(
        'private_create',
        IPAddr('ip', required=True),
        Str('node_uuid', validators=[UUID()], required=True),
    ))
    @job(lock=PRI_LOCK)
    async def do_create(self, job, data):
        """
        Add a ctdb private address to the cluster

        `ip` string representing an IP v4/v6 address
        `node_uuid` uuid of gluster peer assocated with the address

        WARNING: clustering APIs are not intended for 3rd-party consumption and may result
        in a misconfigured SCALE cluster, production outage, or data loss.
        """

        schema_name = 'private_create'
        verrors = ValidationErrors()
        await self.validate_node_uuid(schema_name, data['node_uuid'], verrors)
        verrors.check()
        data |= await self.middleware.call('ctdb.shared.volume.config')
        await self.middleware.call('ctdb.ips.common_validation', data, schema_name, verrors)
        await self.middleware.call('ctdb.ips.update_file', data, schema_name)

        return await self.middleware.call('ctdb.private.ips.query', [('address', '=', data['ip'])])

    @accepts(
        Int('id'),
        Dict(
            'private_update',
            Bool('enable', required=True),
            Str('node_uuid', validators=[UUID()], required=True),
        )
    )
    @job(lock=PRI_LOCK)
    async def do_update(self, job, node_id, option):
        """
        Update Private IP address from the ctdb cluster with pnn value of `id`.

        `id` integer representing the PNN value for the node.

        `enable` boolean. When True, enable the node else disable the node.

        `node_uuid`. When specified, replace node UUID associated with this nodes entry.

        WARNING: clustering APIs are not intended for 3rd-party consumption and may result
        in a misconfigured SCALE cluster, production outage, or data loss.
        """

        schema_name = 'private_update'
        verrors = ValidationErrors()
        if option.get('node_uuid'):
            await self.validate_node_uuid(schema_name, option['node_uuid'], verrors)

        verrors.check()

        data = await self.get_instance(node_id)
        data['enable'] = option['enable']

        data |= await self.middleware.call('ctdb.shared.volume.config')
        await self.middleware.call('ctdb.ips.common_validation', data, schema_name, verrors)
        await self.middleware.call('ctdb.ips.update_file', data, schema_name)

        return await self.get_instance(node_id)
