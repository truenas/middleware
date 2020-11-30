from middlewared.schema import List, Dict, Str, IPAddr, Int
from middlewared.service import accepts, private, job, CRUDService, ValidationErrors
import middlewared.sqlalchemy as sa
from .utils import CTDBConfig, JOB_LOCK


PUBLIC_IP_FILE = CTDBConfig.PUBLIC_IP_FILE.value


class CtdbPublicIpModel(sa.Model):
    __tablename__ = 'ctdb_public_ips'

    id = sa.Column(sa.Integer(), primary_key=True)
    ip = sa.Column(sa.String(45), nullable=True)
    netmask = sa.Column(sa.String(3), nullable=True)
    interface = sa.Column(sa.String(256), nullable=True)


class CtdbPublicIpService(CRUDService):

    class Config:
        namespace = datastore = 'ctdb.public.ips'

    @private
    async def common_validation(self, data, schema_name, verrors):

        # make sure something was given to us
        if not data['public_ips']:
            verrors.add(
                f'{schema_name}.no_ips',
                'Public IP(s) must be specified.',
            )

        verrors.check()

        # normalize the data and remove netmask info (if its given to us)
        # from `ip` keys since it's not used
        for i in data['public_ips']:
            i['ip'] = i['ip'].split('/')[0]

        if schema_name == 'node_create':
            # get copy of current data
            cur_data = {'public_ips': [], 'private_ips': []}
            cur_data['public_ips'] = await self.query()
            cur_data['private_ips'] = await self.middleware.call('datastore.query', 'ctdb.private.ips')

            # need to make sure the new public ip(s) don't already exist in the cluster
            if m := list(set(i['ip'] for i in data['public_ips']).intersection(set(i['ip'] for i in cur_data['public_ips']))):
                verrors.add(
                    f'{schema_name}.public_ip_exists',
                    f'Public IP address(es): {m} already in the cluster.',
                )

            # need to make sure the new public ip(s) don't already exist in the cluster as private ip(s)
            if m := list(set(i['ip'] for i in data['public_ips']).intersection(set(i['ip'] for i in cur_data['private_ips']))):
                verrors.add(
                    f'{schema_name}.public_ip_exists',
                    f'Public IP address(es): {m} have already been added to the cluster as private IP(s).',
                )

        # need to make sure that the interface specified for the public IP exists
        ints = [i['name'] for i in await self.middleware.call('interface.query')]
        if m := list(set(i['interface'] for i in data['public_ips']) - set(ints)):
            verrors.add(
                f'{schema_name}.invalid_interface',
                f'Invalid interface(s) specified {m}.',
            )

        verrors.check()

        return data

    @private
    async def write_public_ips_to_ctdb(self):

        data = {'public_ips': []}
        data['public_ips'] = await self.query()

        with open(PUBLIC_IP_FILE, 'w') as f:
            for i in data['public_ips']:
                f.write(f'{i["ip"]}/{i["netmask"]} {i["interface"]}\n')

        return data

    @accepts(Dict(
        'node_create',
        List('public_ips', unique=True, items=[
            Dict('public_ip', IPAddr('ip'), Int('netmask', required=True), Str('interface', required=True))
        ], default=[]),
    ))
    @job(lock=JOB_LOCK)
    async def do_create(self, job, data):

        """
        Create public IPs to be used in the ctdb cluster.

        `public_ips` is a list of:
            `ip` address
            `netmask` CIDR representation of netmask
            `interface` which interface to assign the `ip` to
        """

        schema_name = 'node_create'
        verrors = ValidationErrors()

        data = await self.common_validation(data, schema_name, verrors)

        for i in data['public_ips']:
            await self.middleware.call(
                'datastore.insert', self._config.datastore, i,
            )

        return await self.write_public_ips_to_ctdb()

    @accepts(Dict(
        'node_update',
        List('public_ips', unique=True, items=[
            Dict('public_ip', IPAddr('ip'), Int('netmask', required=True), Str('interface', required=True))
        ], default=[]),
    ))
    @job(lock=JOB_LOCK)
    async def do_update(self, job, data):

        """
        Update public IPs in the ctdb cluster.

        `public_ips` is a list of:
            `ip` ip v4/v6 address
            `netmask` CIDR representation of netmask
            `interface` which interface to assign the `ip` to
        """

        old = await self.config()
        new = old.copy()
        new.update(data)

        schema_name = 'node_update'
        new = await self.common_validation(new, schema_name)

        await self.middleware.call('datastore.update', self._config.datastore, id, new)

        return await self.write_public_ips_to_ctdb()

    @accepts(Int('id'))
    @job(lock=JOB_LOCK)
    async def do_delete(self, job, id):

        """
        Delete public IP with `id` from ctdb cluster.
        """

        result = await self.middleware.call('datastore.delete', self._config.datastore, id)

        await self.write_public_ips_to_ctdb()

        return result
