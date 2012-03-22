from django.db import models


class Transmission(models.Model):
    """
    Django model describing every tunable setting for transmission
    """

    enable = models.BooleanField(default=False)
    watch_dir = models.CharField(max_length=500, blank=True)
    conf_dir = models.CharField(max_length=500, blank=True)
    download_dir = models.CharField(max_length=500, blank=True)
    allowed = models.TextField(blank=True)
    blocklist = models.TextField(blank=True)
    logfile = models.CharField(max_length=500, blank=True)
    rpc_port = models.IntegerField(default=9091, blank=True)
    rpc_auth = models.BooleanField(default=True)
    rpc_username = models.CharField(max_length=120, blank=True)
    rpc_password = models.CharField(max_length=120, blank=True)
    rpc_whitelist = models.TextField(blank=True)
    dht = models.BooleanField(default=True)
    lpd = models.BooleanField(default=True)
    utp = models.BooleanField(default=True)
    peer_port = models.IntegerField(default=51413, blank=True)
    portmap = models.BooleanField(default=True)
    peerlimit_global = models.IntegerField(default=240)
    peerlimit_torrent = models.IntegerField(default=60)
    encryption_required = models.BooleanField(default=True)
    encryption_preferred = models.BooleanField(default=True)
    encryption_tolerated = models.BooleanField(default=True)
    global_seedratio = models.IntegerField(default=2)
