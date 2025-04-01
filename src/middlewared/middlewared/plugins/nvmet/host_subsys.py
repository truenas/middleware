import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (NVMetHostSubsysCreateArgs, NVMetHostSubsysCreateResult, NVMetHostSubsysDeleteArgs,
                                     NVMetHostSubsysDeleteResult, NVMetHostSubsysEntry, NVMetHostSubsysUpdateArgs,
                                     NVMetHostSubsysUpdateResult)
from middlewared.service import CRUDService, ValidationErrors, private
from middlewared.service_exception import MatchNotFound


class NVMetHostSubsysModel(sa.Model):
    __tablename__ = 'services_nvmet_host_subsys'

    id = sa.Column(sa.Integer(), primary_key=True)
    nvmet_host_subsys_host_id = sa.Column(sa.ForeignKey('services_nvmet_host.id'), index=True)
    nvmet_host_subsys_subsys_id = sa.Column(sa.ForeignKey('services_nvmet_subsys.id'), index=True)


class NVMetHostSubsysService(CRUDService):

    class Config:
        namespace = 'nvmet.host_subsys'
        datastore = 'services.nvmet_host_subsys'
        datastore_prefix = 'nvmet_host_subsys_'
        cli_namespace = 'sharing.nvmet.host_subsys'
        role_prefix = 'SHARING_NVME_TARGET'
        entry = NVMetHostSubsysEntry

    @api_method(
        NVMetHostSubsysCreateArgs,
        NVMetHostSubsysCreateResult,
        audit='Create NVMe target host to subsystem mapping',
        audit_extended=lambda data: data['name']
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        await self.__validate(verrors, data, 'nvmet_host_subsys_create')
        verrors.check()

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self._service_change('nvmet', 'reload')
        return await self.get_instance(data['id'])

    @api_method(
        NVMetHostSubsysUpdateArgs,
        NVMetHostSubsysUpdateResult,
        audit='Update NVMe target host to subsystem mapping',
        audit_callback=True
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update iSCSI Target of `id`.
        """
        old = await self.get_instance(id_)
        audit_callback(self.__audit_summary(old))
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self.__validate(verrors, new, 'nvmet_host_subsys_update', old=old)
        verrors.check()

        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('nvmet', 'reload')
        return await self.get_instance(id_)

    @api_method(
        NVMetHostSubsysDeleteArgs,
        NVMetHostSubsysDeleteResult,
        audit='Delete NVMe target host to subsystem mapping',
        audit_callback=True
    )
    async def do_delete(self, audit_callback, id_):
        data = await self.get_instance(id_)
        audit_callback(self.__audit_summary(data))

        rv = await self.middleware.call('datastore.delete', self._config.datastore, id_)

        await self._service_change('nvmet', 'reload')
        return rv

    @private
    async def delete_ids(self, to_remove):
        # This is called internally (from nvmet.host.delete).  Does not require
        # a reload, because the caller will perform one
        return await self.middleware.call('datastore.delete', self._config.datastore, [['id', 'in', to_remove]])

    async def __validate(self, verrors, data, schema_name, old=None):
        host_id = data.get('host_id')
        subsys_id = data.get('subsys_id')

        # Ensure host_id exists
        try:
            await self.middleware.call('nvmet.host.query', [['id', '=', host_id]], {'get': True})
        except MatchNotFound:
            verrors.add(f'{schema_name}.host_id', f"No host with ID {host_id}")

        # Ensure subsys_id exists
        try:
            await self.middleware.call('nvmet.subsys.query', [['id', '=', subsys_id]], {'get': True})
        except MatchNotFound:
            verrors.add(f'{schema_name}.subsys_id', f"No subsystem with ID {subsys_id}")

        # Ensure we're not making a duplicate
        _filter = [('host_id', '=', host_id), ('subsys_id', '=', subsys_id)]
        if old:
            _filter.append(('id', '!=', data['id']))
        if await self.query(_filter, {'force_sql_filters': True}):
            verrors.add(f'{schema_name}.host_id',
                        f"This record already exists (Host ID: {host_id}/Subsystem ID: {subsys_id})")

    def __audit_summary(self, data):
        return f'{data["host"]["nvmet_host_hostnqn"]}/{data["subsys"]["nvmet_subsys_name"]}'
