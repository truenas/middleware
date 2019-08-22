# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from django.db import models

from freenasUI.freeadmin.models import Model


class CustomerInformation(Model):
    data = models.TextField()
    updated_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True)
    form_dismissed = models.BooleanField()


class EnclosureLabel(Model):
    encid = models.CharField(
        max_length=200,
        unique=True,
    )
    label = models.CharField(
        max_length=200,
    )
