from django.db import models


class Firefly(models.Model):
    """
    Django model describing every tunable setting for firefly
    """

    enable = models.BooleanField(default=False)
    port = models.IntegerField(default=3689)
    admin_pw = models.CharField(max_length=50)
    servername = models.CharField(max_length=500, default='Firefly %v on %h', blank=True)
    extensions = models.CharField(max_length=500, default='.mp3,.m4a,.m4p,.ogg,.flac', blank=True)
    mp3_dir = models.CharField(max_length=500)
    logfile = models.CharField(max_length=500, default='/var/log/mt-daapd.log')
    rescan_interval = models.IntegerField(default=0)
    always_scan = models.BooleanField(default=False)
    scan_type = models.IntegerField(default=2,
        choices=(
            (0, 'Normal'),
            (1, 'Aggressive'),
            (2, 'Painfully aggressive'),
        ),
        )
    process_playlists = models.BooleanField(default=True)
    process_itunes = models.BooleanField(default=True)
    process_m3u = models.BooleanField(default=True)
    auxiliary = models.TextField(verbose_name="Auxiliary parameters", blank=True)
