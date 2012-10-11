import platform

from django.db import models


def conf_dir():
    return '/usr/pbi/transmission-%s/etc/transmission/home' % (
        platform.machine(),
        )


def download_dir():
    return '/usr/pbi/transmission-%s/etc/transmission/home/Downloads' % (
        platform.machine(),
        )


class Transmission(models.Model):
    """
    Django model describing every tunable setting for transmission
    """

    enable = models.BooleanField(default=False)
    watch_dir = models.CharField(
        verbose_name="Watch Directory",
        max_length=500,
        default=download_dir,
        )
    conf_dir = models.CharField(
        verbose_name="Configuration Directory",
        max_length=500,
        default=conf_dir,
        )
    download_dir = models.CharField(
        verbose_name="Download Directory",
        max_length=500,
        default=download_dir,
        )
    logfile = models.CharField(max_length=500, blank=True)
    rpc_auth = models.BooleanField(
        verbose_name="RPC/WebUI Enabled",
        default=True,
        )
    rpc_port = models.IntegerField(
        verbose_name="RPC Port",
        default=9091,
        blank=True,
        )
    rpc_auth_required = models.BooleanField(
        verbose_name="RPC Auth. Required",
        default=False,
        )
    rpc_username = models.CharField(
        verbose_name="RPC Username",
        max_length=120,
        blank=True,
        )
    rpc_password = models.CharField(
        verbose_name="RPC Password",
        max_length=120,
        blank=True,
        )
    rpc_whitelist_enabled = models.BooleanField(
        verbose_name="RPC Whitelist Enabled",
        default=False,
        )
    rpc_whitelist = models.TextField(
        verbose_name="RPC Whitelist",
        blank=True,
        )
    dht = models.BooleanField(
        default=True,
        verbose_name="Distributed Hash Table (DHT)",
        )
    lpd = models.BooleanField(
        default=False,
        verbose_name="Local Peer Discovery (LPD)",
        )
    utp = models.BooleanField(
        default=True,
        verbose_name=u"Micro Transport Protocol (\xb5TP)"
        )
    peer_port = models.IntegerField(default=51413, blank=True)
    portmap = models.BooleanField(default=True)
    peerlimit_global = models.IntegerField(
        verbose_name="Max. number of peers",
        default=240,
        )
    peerlimit_torrent = models.IntegerField(
        verbose_name="Max. number of peers per torrent",
        default=60,
        )
    encryption = models.IntegerField(
        default=1,
        choices=(
            (0, 'Prefer unencrypted'),
            (1, 'Prefer encrypted'),
            (2, 'Require encrypted'),
        ),
        )
    global_seedratio = models.DecimalField(
        verbose_name="Global Seed Ratio",
        decimal_places=2,
        max_digits=6,
        default=2,
        )
