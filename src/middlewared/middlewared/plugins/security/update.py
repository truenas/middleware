import middlewared.sqlalchemy as sa

from middlewared.plugins.failover_.disabled_reasons import DisabledReasonsEnum
from middlewared.plugins.failover_.reboot import FIPS_KEY
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
        boot_info = await self.middleware.call('failover.reboot.info')
        if boot_info['this_node']['reboot_required']:
            # means FIPS is being toggled but this node is already pending a reboot
            # so it means the user toggled FIPS twice without a reboot in between
            boot_info['this_node']['reboot_required'] = False
            await self.middleware.call('keyvalue.set', FIPS_KEY, boot_info)
        else:
            # means FIPS is toggled and this node isn't pending a reboot, so mark it
            # as such
            boot_info['this_node']['reboot_required'] = True
            await self.middleware.call('keyvalue.set', FIPS_KEY, boot_info)

        if boot_info['other_node']['reboot_required']:
            # means FIPS is being toggled but other node is already pending a reboot
            # so it means the user toggled FIPS twice and somehow the other node
            # didn't reboot (even though we do this automatically). This is an edge
            # case and means someone or something is doing things behind our backs
            boot_info['other_node']['reboot_required'] = False
            await self.middleware.call('keyvalue.set', FIPS_KEY, boot_info)
        else:
            try:
                # we automatically reboot (and wait for) the other controller
                reboot_job = await self.middleware.call('failover.reboot.other_node')
                await job.wrap(reboot_job)
            except Exception:
                self.logger.error('Unexpected failure rebooting the other node', exc_info=True)
                # something extravagant happened so we'll just play it safe and say that
                # another reboot is required
                boot_info['other_node']['reboot_required'] = True
            else:
                new_info = await self.middleware.call('failover.reboot.info')
                if boot_info['other_node']['id'] == new_info['other_node']['id']:
                    # standby "rebooted" but the boot id is the same....not good
                    self.logger.warning('Other node claims it rebooted but boot id is the same')
                    boot_info['other_node']['reboot_required'] = True
                else:
                    boot_info['other_node']['id'] = new_info['other_node']['id']
                    boot_info['other_node']['reboot_required'] = False

            await self.middleware.call('keyvalue.set', FIPS_KEY, boot_info)

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
            # TODO: We need to fix this for non-HA iX hardware...
            await self.configure_fips_on_ha(is_ha, job)

        return await self.config()
