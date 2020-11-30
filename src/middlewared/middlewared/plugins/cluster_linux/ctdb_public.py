from middlewared.schema import Dict, Str, IPAddr, Int
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
    def common_validation(self, data, schema_name, verrors):

        # get copy of current data
        cur_data = {'public_ips': [], 'private_ips': []}
        cur_data['public_ips'] = self.middleware.call_sync('ctdb.public.ips.query')
        cur_data['private_ips'] = self.middleware.call_sync('ctdb.private.ips.query')

        # need to make sure the new public ip(s) don't already exist in the cluster
        if data['ip'] in set(i['ip'] for i in cur_data['public_ips'] + cur_data['private_ips']):
            verrors.add(
                f'{schema_name}.ip',
                f'Public IP address: {data["ip"]} already in the cluster.',
            )

        # need to make sure that the interface specified for the public IP exists
        ints = [i['name'] for i in self.middleware.call_sync('interface.query')]
        if data['interface'] not in ints:
            verrors.add(
                f'{schema_name}.interface',
                f'Invalid interface specified {data["interface"]}.',
            )

        verrors.check()

    @private
    def write_public_ips_to_ctdb(self):

        with open(PUBLIC_IP_FILE, 'w') as f:
            for i in self.middleware.call_sync('ctdb.public.ips.query'):
                f.write(f'{i["ip"]}/{i["netmask"]} {i["interface"]}\n')

    @accepts(Dict(
        'node_create',
        IPAddr('ip'),
        Int('netmask', required=True),
        Str('interface', required=True)
    ))
    @job(lock=JOB_LOCK)
    def do_create(self, job, data):

        """
        Create public IP to be used in the ctdb cluster.

        `ip` address
        `netmask` CIDR representation of netmask
        `interface` which interface to assign the `ip` to
        """

        schema_name = 'node_create'
        verrors = ValidationErrors()

        # normalize the data and remove netmask info (if its given to us)
        # from `ip` keys since it's not used
        data['ip'] = data['ip'].split('/')[0]

        self.common_validation(data, schema_name, verrors)

        self.middleware.call_sync('datastore.insert', self._config.datastore, data)

        self.write_public_ips_to_ctdb()

        return self.middleware.call_sync('ctdb.public.ips.get_instance', id)

    @accepts(Int('id'))
    @job(lock=JOB_LOCK)
    def do_delete(self, job, id):

        """
        Delete public IP with `id` from ctdb cluster.
        """

        result = self.middleware.call_sync('datastore.delete', self._config.datastore, id)

        self.write_public_ips_to_ctdb()

        return result
