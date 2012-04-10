from django.db import models


class Firefly(models.Model):
    """
    Django model describing every tunable setting for firefly
    """

    enable = models.BooleanField(default=False)
    port = models.IntegerField(default=3689)
    servername = models.CharField(max_length=500, default='Firefly %v on %h', blank=True)
    extensions = models.CharField(max_length=500, default='.mp3,.m4a,.m4p,.ogg,.flac', blank=True)
    logfile = models.CharField(max_length=500, default='/var/log/mt-daapd.log')
    process_playlists = models.BooleanField(default=True)
    process_itunes = models.BooleanField(default=True)
    process_m3u = models.BooleanField(default=True)
