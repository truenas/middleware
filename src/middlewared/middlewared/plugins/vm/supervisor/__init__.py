from middlewared.utils import osc

if osc.IS_LINUX:
    from .supervisor_linux import VMSupervisor # noqa
else:
    from .supervisor_freebsd import VMSupervisor # noqa

__all__ = ['VMSupervisor']
