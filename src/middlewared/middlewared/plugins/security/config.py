from __future__ import annotations

import typing

from middlewared.api.current import SystemSecurityEntry, SystemSecurityUpdate
from middlewared.plugins.system.reboot import RebootReason
from middlewared.service import ConfigServicePart, ValidationError
import middlewared.sqlalchemy as sa

from .stig import configure_reboot_reason_on_ha, configure_stig
from .validate import validate_password_security, validate_security, validate_stig

if typing.TYPE_CHECKING:
    from middlewared.job import Job


class SystemSecurityModel(sa.Model):
    __tablename__ = "system_security"

    id = sa.Column(sa.Integer(), primary_key=True)
    enable_fips = sa.Column(sa.Boolean(), default=False)
    enable_gpos_stig = sa.Column(sa.Boolean(), default=False)
    min_password_age = sa.Column(sa.Integer(), nullable=True)
    max_password_age = sa.Column(sa.Integer(), nullable=True)
    password_complexity_ruleset = sa.Column(sa.JSON(set), nullable=True)
    min_password_length = sa.Column(sa.Integer(), nullable=True)
    password_history_length = sa.Column(sa.Integer(), nullable=True)


class SystemSecurityConfigServicePart(ConfigServicePart[SystemSecurityEntry]):
    _datastore = "system.security"
    _entry = SystemSecurityEntry

    async def do_update(self, job: Job, data: SystemSecurityUpdate) -> SystemSecurityEntry:
        is_ha = await self.middleware.call("failover.licensed")
        reasons = await self.middleware.call("failover.disabled.reasons")

        old_config = await self.config()
        new = old_config.updated(data)
        if new == old_config:
            return old_config

        await validate_security(self, is_ha, new, reasons)

        must_update_account_policy = validate_password_security(old_config, new)

        if new.enable_gpos_stig:
            if not new.enable_fips:
                raise ValidationError(
                    "system_security_update.enable_gpos_stig",
                    "FIPS mode is required in General Purpose OS STIG compatibility mode.",
                )

            await validate_stig(self, job.credentials)

        await self._update(new)

        reboot_reason = None
        reboot_other_node = False
        if new.enable_fips != old_config.enable_fips:
            # TODO: We likely need to do some SSH magic as well
            #  let's investigate the exact configuration there
            reboot_reason = RebootReason.FIPS
            await self.middleware.call("etc.generate", "fips")

        if new.enable_gpos_stig != old_config.enable_gpos_stig:
            reboot_reason = RebootReason.GPOSSTIG
            await configure_stig(self, new)

        if reboot_reason:
            await self.middleware.call("system.reboot.toggle_reason", reboot_reason.name, reboot_reason.value)
            reboot_other_node |= await configure_reboot_reason_on_ha(self, is_ha, reboot_reason)

        if reboot_reason and reboot_other_node:
            # Let's pick the first reboot reason when rebooting the other node
            try:
                # Send the datastore to the remote node to ensure that the
                # FIPS/STIG configuration has been synced up before reboot
                await self.middleware.call("failover.datastore.send")
                await self.middleware.call("failover.call_remote", "etc.generate", ["fips"])
                await self.middleware.call("failover.call_remote", "system.security.configure_stig")

                # Reboot reasons are already added at this point, as necessary configuration has been generated
                # Let's go ahead and reboot the remote node

                # Automatically reboot (and wait for) the other controller. Passing {'graceful': True} allows the OS to
                # write pending changes (e.g. the FIPS configuration generated above) to disk before rebooting;
                # otherwise those file changes can be lost on reboot.
                reboot_job = await self.middleware.call(
                    "failover.reboot.other_node",
                    {"reason": reboot_reason.value, "graceful": True},
                )
                await job.wrap(reboot_job)
            except Exception:
                self.logger.error("Failed to sync security configuration changes on remote node", exc_info=True)

        if must_update_account_policy:
            await self.middleware.call("etc.generate", "shadow")
            await self.middleware.call("smb.apply_account_policy")

        return await self.config()
