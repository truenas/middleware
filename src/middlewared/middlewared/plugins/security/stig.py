import subprocess

from middlewared.api.current import SystemSecurityEntry
from middlewared.plugins.system.reboot import RebootReason
from middlewared.service import ServiceContext
from middlewared.utils.io import set_io_uring_enabled


async def configure_stig(context: ServiceContext, data: SystemSecurityEntry | None = None) -> None:
    if data is None:
        data = await context.call2(context.s.system.security.config)

    if not data.enable_gpos_stig:
        await context.middleware.call("auth.set_authenticator_assurance_level", "LEVEL_1")
        return

    # Per security team STIG compatibility requires that authentication methods
    # use two factors.
    await context.middleware.call("auth.set_authenticator_assurance_level", "LEVEL_2")

    # io_uring significantly complicates ability to use auditd to monitor file
    # access and changes, and so we globally disable it when doing STIG
    # compatibility.
    await context.to_thread(set_io_uring_enabled, False)

    # Disable non-critical outgoing network activity
    await context.middleware.call(
        "network.configuration.update", {"activity": {"type": "DENY", "activities": ["usage", "update", "support"]}}
    )


async def configure_reboot_reason_on_ha(context: ServiceContext, is_ha: bool, reason: RebootReason) -> bool:
    """
    This should return boolean true if the remote node is to be rebooted.
    """
    # TODO: Validate if this should be done, because if we do this - then local operations
    #  will correctly reflect that local node needs to be rebooted etc because of relevant fips/stig
    #  change but if this fails for whatever reason, that won't be true and it won't reflect
    if not is_ha:
        return False

    try:
        return await configure_reboot_reason_on_ha_impl(context, reason)
    except Exception:
        context.logger.error("Failed to configure security on HA", exc_info=True)
        return False


async def configure_reboot_reason_on_ha_impl(context: ServiceContext, reason: RebootReason) -> bool:
    remote_reboot_reasons = await context.middleware.call("failover.call_remote", "system.reboot.list_reasons")
    if reason.name in remote_reboot_reasons:
        # This means that we're toggling a change in security settings but other node is
        # already pending a reboot, which means the user has toggled changes twice and
        # somehow the other node didn't reboot (even though this should be automatic).
        # This is an edge case and means someone or something is doing things behind our backs
        context.logger.error("%s: reboot is already pending on other controller for same reason.", reason.name)
        await context.middleware.call("failover.call_remote", "system.reboot.remove_reason", [reason.name])
        return False
    else:
        # We add a reboot reason here before rebooting the other node so that we are able to
        # grab other node's boot id because we have seen in a support case that a reboot job failed
        # for some reason where the other node actually rebooted already but we were unable to get
        # it's boot id which meant that it needs to be rebooted again even though it has already been rebooted
        await context.middleware.call("failover.reboot.add_remote_reason", reason.name, reason.value)
        return True


def configure_fips(context: ServiceContext, database_path: str | None = None) -> None:
    args = ["configure_fips"]
    if database_path is not None:
        args.append(database_path)

    try:
        p = subprocess.run(args, capture_output=True, check=True, encoding="utf-8", errors="ignore")
        output = p.stderr.strip()
        if output:
            context.logger.error("configure_fips output:\n%s", output)
    except subprocess.CalledProcessError as e:
        context.logger.error("configure_fips error:\n%s", e.stderr)
        raise
