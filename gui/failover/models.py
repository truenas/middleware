# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from django.db import models, transaction
from django.utils.translation import ugettext_lazy as _

from freenasUI.contrib.IPAddressField import IPAddressField
from freenasUI.freeadmin.models import Model
from freenasUI.middleware.notifier import notifier
from freenasUI.network.models import Interfaces, VLAN


class Failover(Model):
    disabled = models.BooleanField(
        default=False,
        blank=True,
    )
    master = models.BooleanField(
        default=False,
        blank=True,
    )
    timeout = models.IntegerField(
        default=0
    )

    @property
    def ipaddress(self):
        return notifier().failover_pair_ip()

    class Meta:
        db_table = 'system_failover'
        verbose_name = _("Failover")
        verbose_name_plural = _("Failovers")

    class FreeAdmin:
        deletable = False
