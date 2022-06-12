import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Dict, Int, IPAddr, List, Patch, Str
from middlewared.service import CRUDService, private


class iSCSITargetAuthorizedInitiatorModel(sa.Model):
    __tablename__ = 'services_iscsitargetauthorizedinitiator'

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_target_initiator_initiators = sa.Column(sa.Text(), default="ALL")
    iscsi_target_initiator_auth_network = sa.Column(sa.Text(), default="ALL")
    iscsi_target_initiator_comment = sa.Column(sa.String(120))


class iSCSITargetAuthorizedInitiator(CRUDService):

    class Config:
        namespace = 'iscsi.initiator'
        datastore = 'services.iscsitargetauthorizedinitiator'
        datastore_prefix = 'iscsi_target_initiator_'
        datastore_extend = 'iscsi.initiator.extend'
        cli_namespace = 'sharing.iscsi.target.authorized_initiator'

    @accepts(Dict(
        'iscsi_initiator_create',
        List('initiators'),
        List('auth_network', items=[IPAddr('ip', network=True)]),
        Str('comment'),
        register=True
    ))
    async def do_create(self, data):
        """
        Create an iSCSI Initiator.

        `initiators` is a list of initiator hostnames which are authorized to access an iSCSI Target. To allow all
        possible initiators, `initiators` can be left empty.

        `auth_network` is a list of IP/CIDR addresses which are allowed to use this initiator. If all networks are
        to be allowed, this field should be left empty.
        """
        await self.compress(data)

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(data['id'])

    @accepts(
        Int('id'),
        Patch(
            'iscsi_initiator_create',
            'iscsi_initiator_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        """
        Update iSCSI initiator of `id`.
        """
        old = await self.get_instance(id)

        new = old.copy()
        new.update(data)

        await self.compress(new)
        await self.middleware.call(
            'datastore.update', self._config.datastore, id, new,
            {'prefix': self._config.datastore_prefix})

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(id)

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Delete iSCSI initiator of `id`.
        """
        await self.get_instance(id)
        result = await self.middleware.call(
            'datastore.delete', self._config.datastore, id
        )

        await self._service_change('iscsitarget', 'reload')

        return result

    @private
    async def compress(self, data):
        initiators = data['initiators']
        auth_network = data['auth_network']

        initiators = 'ALL' if not initiators else '\n'.join(initiators)
        auth_network = 'ALL' if not auth_network else '\n'.join(auth_network)

        data['initiators'] = initiators
        data['auth_network'] = auth_network

        return data

    @private
    async def extend(self, data):
        initiators = data['initiators']
        auth_network = data['auth_network']

        initiators = [] if initiators == 'ALL' else initiators.split()
        auth_network = [] if auth_network == 'ALL' else auth_network.split()

        data['initiators'] = initiators
        data['auth_network'] = auth_network

        return data
