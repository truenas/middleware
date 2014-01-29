from django.db import models

from freenasUI.freeadmin.models import Model


class EnclosureLabel(Model):
    encid = models.CharField(
        max_length=200,
        unique=True,
    )
    label = models.CharField(
        max_length=200,
    )
