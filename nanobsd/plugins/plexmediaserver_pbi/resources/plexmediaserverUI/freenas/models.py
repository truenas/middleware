import platform

from django.db import models


class PlexMediaServer(models.Model):
    """
    Django model describing every tunable setting for plexmediaserver
    """

    enable = models.BooleanField(default=False)

