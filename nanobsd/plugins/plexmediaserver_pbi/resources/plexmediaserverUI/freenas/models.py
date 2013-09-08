import platform

from django.db import models


def conf_dir():
    return '/usr/pbi/plexmediaserver-%s/etc/plexmediaserver/home' % (
        platform.machine(),
        )


def download_dir():
    return '/usr/pbi/plexmediaserver-%s/etc/plexmediaserver/home/Downloads' % (
        platform.machine(),
        )


class PlexMediaServer(models.Model):
    """
    Django model describing every tunable setting for plexmediaserver
    """

    enable = models.BooleanField(default=False)

