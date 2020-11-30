from middlewared.schema import Dict, IPAddr, Int
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
    def common_validation(self, data, schema_name, verrors):

        # get the current ips in the cluster
        cur_data = {'private_ips': [], 'public_ips': []}
        cur_data['private_ips'] = self.middleware.call_sync('ctdb.private.ips.query')
        cur_data['public_ips'] = self.middleware.call_sync('ctdb.public.ips.query')

        # need to make sure the new private ip(s) don't already exist in the cluster
        if data['ip'] in set(i['ip'] for i in cur_data['private_ips'] + cur_data['public_ips']):
            verrors.add(
                f'{schema_name}.ip',
                f'Private IP address: {data["ip"]} already in the cluster.',
            )

        verrors.check()

    @private
    def write_private_ips_to_ctdb(self):

        with open(PRIVATE_IP_FILE, 'w') as f:
            for i in map(lambda i: i['ip'], self.middleware.call_sync('ctdb.private.ips.query')):
                f.write(f'{i}\n')

    @accepts(Dict(
        'node_create',
        IPAddr('ip'),
    ))
    @job(lock=JOB_LOCK)
    def do_create(self, job, data):

        """
        Create private IPs to be used in the ctdb cluster.

        `ip` is an IP v4/v6 address that will be used
            for the intra-cluster communication between nodes.
            This ip address should be on a phyically separate
            network and should be non-routable.
        """

        schema_name = 'node_create'
        verrors = ValidationErrors()

        # normalize the data and remove netmask info (if its given to us)
        # from `ip` key since it's not used
        data['ip'] = data['ip'].split('/')[0]

        self.common_validation(data, schema_name, verrors)

        self.middleware.call_sync('datastore.insert', 'ctdb.private.ips', data)

        self.write_private_ips_to_ctdb()

        return data

    @accepts(Int('id'))
    @job(lock=JOB_LOCK)
    def do_delete(self, job, id):

        """
        Delete private IP with `id` from ctdb cluster.
        """

        result = self.middleware.call_sync('datastore.delete', self._config.datastore, id)

        self.write_private_ips_to_ctdb()

        return result
