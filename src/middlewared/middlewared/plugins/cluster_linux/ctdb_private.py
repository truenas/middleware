from middlewared.schema import List, Dict, IPAddr, Int
from middlewared.service import accepts, private, job, CRUDService, ValidationErrors
import middlewared.sqlalchemy as sa
from .utils import CTDBConfig, JOB_LOCK


PRIVATE_IP_FILE = CTDBConfig.PRIVATE_IP_FILE.value


class CtdbPrivateIpModel(sa.Model):
    __tablename__ = 'ctdb_private_ips'

    id = sa.Column(sa.Integer(), primary_key=True)
    ip = sa.Column(sa.String(45), nullable=True)


class CtdbPrivateIpService(CRUDService):

    class Config:
        namespace = datastore = 'ctdb.private.ips'

    @private
    async def common_validation(self, data, schema_name, verrors):

        # make sure something was given to us
        if not data['private_ips']:
            verrors.add(
                f'{schema_name}.no_ips',
                'Private IP(s) must be specified.',
            )

        verrors.check()

        # normalize the data and remove netmask info (if its given to us)
        # from `ip` keys since it's not used
        for i in data['private_ips']:
            i['ip'] = i['ip'].split('/')[0]

        if schema_name == 'node_create':
            # get the current ips in the cluster
            cur_data = {'private_ips': [], 'public_ips': []}
            cur_data['private_ips'] = await self.query()
            cur_data['public_ips'] = await self.middleware.call('datastore.query', 'ctdb.public.ips')

            # need to make sure the new private ip(s) don't already exist in the cluster
            if m := list(set(i['ip'] for i in data['private_ips']).intersection(set(i['ip'] for i in cur_data['private_ips']))):
                verrors.add(
                    f'{schema_name}.private_ip_exists',
                    f'Private IP address(es): {m} already in the cluster.',
                )

            # need to make sure the new private ip(s) don't already exist in the cluster as public ip(s)
            if m := list(set(i['ip'] for i in data['private_ips']).intersection(set(i['ip'] for i in cur_data['public_ips']))):
                verrors.add(
                    f'{schema_name}.public_ip_exists',
                    f'Private IP address(es): {m} have already been added to the cluster as public IP(s).',
                )

        verrors.check()

        return data

    @private
    async def write_private_ips_to_ctdb(self):

        data = {'private_ips': []}
        data['private_ips'] = await self.query()

        with open(PRIVATE_IP_FILE, 'w') as f:
            for i in map(lambda i: i['ip'], data['private_ips']):
                f.write(f'{i}\n')

        return data

    @accepts(Dict(
        'node_create',
        List('private_ips', unique=True, items=[
            Dict('private_ip', IPAddr('ip'))
        ], default=[]),
    ))
    @job(lock=JOB_LOCK)
    async def do_create(self, job, data):

        """
        Create private IPs to be used in the ctdb cluster.

        `private_ips` is a list of `ip` addresses that will be used
            for the intra-cluster communication between nodes.
            These ip addresses should be on a phyically separate
            network and should be non-routable.
        """

        schema_name = 'node_create'
        verrors = ValidationErrors()

        data = await self.common_validation(data, schema_name, verrors)

        for i in data['private_ips']:
            await self.middleware.call(
                'datastore.insert', 'ctdb.private.ips', i,
            )

        return await self.write_private_ips_to_ctdb()

    @accepts(Dict(
        'node_update',
        List('private_ips', items=[IPAddr('ip', network=False)], default=[]),
    ))
    @job(lock=JOB_LOCK)
    async def do_update(self, job, data):

        """
        Add nodes to the ctdb cluster.

        `private_ips` is a list of `ip` addresses that will be used
            for the intra-cluster communication between nodes.
            These ip addresses should be on a phyically separate
            network and should be non-routable.
        """

        schema_name = 'node_update'
        data = await self.common_validation(data, schema_name)

        return await self.write_private_ips_to_ctdb()

    @accepts(Int('id'))
    @job(lock=JOB_LOCK)
    async def do_delete(self, job, id):

        """
        Delete private IP with `id` from ctdb cluster.
        """

        result = await self.middleware.call('datastore.delete', self._config.datastore, id)

        await self.write_private_ips_to_ctdb()

        return result
