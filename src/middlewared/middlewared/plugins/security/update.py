import middlewared.sqlalchemy as sa

from middlewared.plugins.failover_.disabled_reasons import DisabledReasonsEnum
from middlewared.plugins.system.reboot import RebootReason
from middlewared.schema import accepts, Bool, Dict, Int, Patch
from middlewared.service import ConfigService, ValidationError, job, private


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

    @private
    async def configure_fips_on_ha(self, is_ha, job):
        if not is_ha:
            return

        await self.middleware.call('failover.call_remote', 'etc.generate', ['fips'])

        remote_reboot_reasons = await self.middleware.call('failover.call_remote', 'system.reboot.list_reasons')
        if RebootReason.FIPS.name in remote_reboot_reasons:
            # means FIPS is being toggled but other node is already pending a reboot,
            # so it means the user toggled FIPS twice and somehow the other node
            # didn't reboot (even though we do this automatically). This is an edge
            # case and means someone or something is doing things behind our backs
            await self.middleware.call('failover.call_remote', 'system.reboot.remove_reason', [RebootReason.FIPS.name])
        else:
            try:
                # we automatically reboot (and wait for) the other controller
                reboot_job = await self.middleware.call('failover.reboot.other_node')
                await job.wrap(reboot_job)
            except Exception:
                # something extravagant happened, so we'll just play it safe and say that
                # another reboot is required
                await self.middleware.call('failover.reboot.add_remote_reason', RebootReason.FIPS.name,
                                           RebootReason.FIPS.value)

    @private
    async def validate(self, is_ha, ha_disabled_reasons):
        schema = 'system_security_update.enable_fips'
        if not await self.middleware.call('system.security.info.fips_available'):
            raise ValidationError(
                schema,
                'This feature can only be enabled on licensed iX enterprise systems. '
                'Please contact iX sales for more information.'
            )

        if is_ha and ha_disabled_reasons:
            bad_reasons = set(ha_disabled_reasons) - {
                DisabledReasonsEnum.LOC_FIPS_REBOOT_REQ.name,
                DisabledReasonsEnum.REM_FIPS_REBOOT_REQ.name,
            }
            if bad_reasons:
                formatted = '\n'.join([DisabledReasonsEnum[i].value for i in bad_reasons])
                raise ValidationError(
                    schema,
                    f'Security settings cannot be updated while HA is in an unhealthy state: ({formatted})'
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
        is_ha = await self.middleware.call('failover.licensed')
        reasons = await self.middleware.call('failover.disabled.reasons')
        await self.validate(is_ha, reasons)

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
            await self.middleware.call('system.reboot.toggle_reason', RebootReason.FIPS.name, RebootReason.FIPS.value)
            await self.configure_fips_on_ha(is_ha, job)

        return await self.config()
