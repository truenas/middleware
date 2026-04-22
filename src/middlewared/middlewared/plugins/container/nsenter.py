from middlewared.service import CallError, ServiceContext


# Extracted from man capabilities(7)
CAPABILITIES = frozenset([
    'chown', 'dac_override', 'dac_read_search', 'fowner', 'fsetid', 'kill', 'setgid', 'setuid', 'setpcap',
    'linux_immutable', 'net_bind_service', 'net_broadcast', 'net_admin', 'net_raw', 'ipc_lock', 'ipc_owner',
    'sys_module', 'sys_rawio', 'sys_chroot', 'sys_ptrace', 'sys_pacct', 'sys_admin', 'sys_boot', 'sys_nice',
    'sys_resource', 'sys_time', 'sys_tty_config', 'mknod', 'lease', 'audit_write', 'audit_control', 'setfcap',
    'mac_override', 'mac_admin', 'syslog', 'wake_alarm', 'block_suspend', 'audit_read', 'perfmon', 'bpf',
    'checkpoint_restore',
])


async def nsenter(context: ServiceContext, container_id: int) -> list[str]:
    container = await context.call2(context.s.container.get_instance, container_id)
    pid = container.status.pid
    if pid is None:
        raise CallError('Container is not running')

    drop = []
    match container.capabilities_policy:
        case 'DEFAULT':
            # Standard capabilities disabled by libvirtd by default
            drop = [
                f'cap_{name}'
                for name in ['sys_module', 'sys_time', 'mknod', 'audit_control', 'mac_admin']
                if container.capabilities_state.get(name) is not True
            ]
            drop += [f'cap_{name}' for name, enabled in container.capabilities_state.items() if not enabled]
        case 'ALLOW':
            drop = [f'cap_{name}' for name, enabled in container.capabilities_state.items() if not enabled]
        case 'DENY':
            drop = [f'cap_{name}' for name in CAPABILITIES if container.capabilities_state.get(name) is not True]

    caps = [f'cap_{name}' for name, enabled in container.capabilities_state.items() if enabled]

    capsh = []
    if drop:
        capsh.append(f'--drop={','.join(drop)}')
    if caps:
        capsh.append(f'--caps={','.join(caps)}+ep')

    nsenter_cmd = ['/usr/bin/nsenter', '--target', f'{pid}', '--mount', '--uts', '--ipc', '--net', '--pid']
    if container.idmap:
        nsenter_cmd.append('--user')
    # capsh runs on the host (not inside the container) because minimal
    # images such as Alpine do not ship capsh. Bounding-set restrictions
    # are per-task and survive both execve and the nsenter namespace
    # switch, so the final shell ends up with the same capabilities it
    # would have had if capsh had been invoked inside the container.
    return (
        ['/sbin/capsh'] + capsh + ['--', '-c', 'exec "$@"', '_'] +
        nsenter_cmd + ['--', '/bin/sh', '-c']
    )
