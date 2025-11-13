import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (iSCSITargetAuthorizedInitiatorCreateArgs, iSCSITargetAuthorizedInitiatorCreateResult, iSCSITargetAuthorizedInitiatorDeleteArgs,
                                     iSCSITargetAuthorizedInitiatorDeleteResult, iSCSITargetAuthorizedInitiatorEntry, iSCSITargetAuthorizedInitiatorUpdateArgs,
                                     iSCSITargetAuthorizedInitiatorUpdateResult)
from middlewared.service import CRUDService, private


def initiator_summary(data):
    """Select a human-readable string representing this initiator"""
    if title := data.get('comment'):
        return title
    initiators = data.get('initiators', [])
    count = len(initiators)
    if count == 0:
        return 'Allow All initiators'
    elif count == 1:
        return initiators[0]
    else:
        return initiators[0] + ',...'


class iSCSITargetAuthorizedInitiatorModel(sa.Model):
    __tablename__ = 'services_iscsitargetauthorizedinitiator'

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_target_initiator_initiators = sa.Column(sa.Text(), default="ALL")
    iscsi_target_initiator_comment = sa.Column(sa.String(120))


class iSCSITargetAuthorizedInitiator(CRUDService):

    class Config:
        namespace = 'iscsi.initiator'
        datastore = 'services.iscsitargetauthorizedinitiator'
        datastore_prefix = 'iscsi_target_initiator_'
        datastore_extend = 'iscsi.initiator.extend'
        cli_namespace = 'sharing.iscsi.target.authorized_initiator'
        role_prefix = 'SHARING_ISCSI_INITIATOR'
        entry = iSCSITargetAuthorizedInitiatorEntry

    @api_method(
        iSCSITargetAuthorizedInitiatorCreateArgs,
        iSCSITargetAuthorizedInitiatorCreateResult,
        audit='Create iSCSI initiator',
        audit_extended=lambda data: initiator_summary(data)
    )
    async def do_create(self, data):
        """
        Create an iSCSI Initiator.

        `initiators` is a list of initiator hostnames which are authorized to access an iSCSI Target. To allow all
        possible initiators, `initiators` can be left empty.
        """
        await self.compress(data)

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(data['id'])

    @api_method(
        iSCSITargetAuthorizedInitiatorUpdateArgs,
        iSCSITargetAuthorizedInitiatorUpdateResult,
        audit='Update iSCSI initiator',
        audit_callback=True,
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update iSCSI initiator of `id`.
        """
        old = await self.get_instance(id_)
        audit_callback(initiator_summary(old))

        new = old.copy()
        new.update(data)

        await self.compress(new)
        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix})

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(id_)

    @api_method(
        iSCSITargetAuthorizedInitiatorDeleteArgs,
        iSCSITargetAuthorizedInitiatorDeleteResult,
        audit='Delete iSCSI initiator',
        audit_callback=True,
    )
    async def do_delete(self, audit_callback, id_):
        """
        Delete iSCSI initiator of `id`.
        """
        old = await self.get_instance(id_)
        audit_callback(initiator_summary(old))
        result = await self.middleware.call(
            'datastore.delete', self._config.datastore, id_
        )

        await self._service_change('iscsitarget', 'reload')

        return result

    @private
    async def compress(self, data):
        initiators = data['initiators']
        initiators = 'ALL' if not initiators else '\n'.join(initiators)
        data['initiators'] = initiators
        return data

    @private
    async def extend(self, data):
        initiators = data['initiators']
        initiators = [] if initiators == 'ALL' else initiators.split()
        data['initiators'] = initiators
        return data
