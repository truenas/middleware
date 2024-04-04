import middlewared.sqlalchemy as sa

from middlewared.plugins.failover_.disabled_reasons import DisabledReasonsEnum
from middlewared.schema import accepts, Bool, Dict, Int, Patch
from middlewared.service import CallError, ConfigService, ValidationError, job


class SystemSecurityModel(sa.Model):
    __tablename__ = 'system_security'

    id = sa.Column(sa.Integer(), primary_key=True)
    enable_fips = sa.Column(sa.Boolean(), default=False)


class SystemSecurityService(ConfigService):

    class Config:
        cli_namespace = 'system.security'
        datastore = 'system.security'
        namespace = 'system.security'

    ENTRY = Dict(
        'system_security_entry',
        Bool('enable_fips', required=True),
        Int('id', required=True),
    )

    @accepts(
        Patch(
            'system_security_entry', 'system_security_update',
            ('rm', {'name': 'id'}),
            ('attr', {'update': True}),
        )
    )
    @job(lock='security_update')
    async def do_update(self, job, data):
        """
        Update System Security Service Configuration.

        `enable_fips` when set, enables FIPS mode.
        """
        if not await self.middleware.call('system.security.info.fips_available'):
            raise ValidationError(
                'system_security_update.enable_fips',
                'This feature can only be enabled on licensed iX enterprise systems. '
                'Please contact iX sales for more information.'
            )

        is_ha = await self.middleware.call('failover.licensed')
        if is_ha and (reasons := await self.middleware.call('failover.disabled.reasons')):
            if set(reasons) - {
                DisabledReasonsEnum.LOC_FIPS_REBOOT_REQ,
                DisabledReasonsEnum.REM_FIPS_REBOOT_REQ,
            }:
                raise CallError('Security settings cannot be updated while HA is in an unhealthy state')

        old = await self.config()
        new = old.copy()
        new.update(data)
        if new == old:
            return new

        await self.middleware.call('datastore.update', self._config.datastore, old['id'], new)

        if new['enable_fips'] != old['enable_fips']:
            # TODO: We likely need to do some SSH magic as well
            #  let's investigate the exact configuration there
            await self.middleware.call('etc.generate', 'fips')
            if is_ha:
                boot_id_info = await self.middleware.call('failover.reboot.retrieve_boot_ids')
                await self.middleware.call('keyvalue.set', 'fips_toggled', boot_id_info)
                reboot_job = await self.middleware.call('failover.reboot.other_node')
                await job.wrap(reboot_job)

        return await self.config()
