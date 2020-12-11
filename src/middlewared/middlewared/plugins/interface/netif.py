from middlewared.utils import osc

if osc.IS_FREEBSD:
    import netif  # noqa
if osc.IS_LINUX:
    import middlewared.plugins.interface.netif_linux as netif  # noqa
