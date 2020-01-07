import platform

if platform.system() == "FreeBSD":
    import netif  # noqa
if platform.system() == "Linux":
    import middlewared.plugins.interface.netif_linux as netif  # noqa
