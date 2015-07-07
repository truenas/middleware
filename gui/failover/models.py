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


class CARP(Model):
    carp_number = models.PositiveIntegerField(
        verbose_name=_("Interface Number"),
        unique=True,
        help_text=_(
            'Number used to identify the CARP interface, e.g. carp0, where 0 '
            'is the interface number'
        ),
    )
    carp_vhid = models.PositiveIntegerField(
        verbose_name=_("Virtual Host ID"),
        unique=True,
    )
    carp_pass = models.CharField(
        max_length=100,
        blank=False,
        verbose_name=_("Password")
    )
    carp_skew = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Advertisements Skew"),
        blank=True,
        null=True,
    )
    carp_critical = models.BooleanField(
        default=False,
        verbose_name=_("Critical for Failover"),
    )
    carp_group = models.IntegerField(
        verbose_name=_('Group'),
        choices=[(i, i) for i in range(1, 33)],
        null=True,
        blank=True,
    )

    @property
    def carp_name(self):
        return 'carp%d' % self.carp_number

    def __unicode__(self):
        try:
            iface = Interfaces.objects.get(int_interface=self.carp_name)
            return u'%d:%s' % (self.carp_vhid, iface.int_ipv4address)
        except:
            return unicode(self.carp_vhid)

    class Meta:
        verbose_name = _("CARP")
        verbose_name_plural = _("CARPs")
        db_table = 'network_carp'

    class FreeAdmin:
        icon_object = u"CARPIcon"
        icon_model = u"CARPIcon"
        icon_add = u"AddCARPIcon"
        icon_view = u"ViewAllCARPsIcon"

    def delete(self):
        super(CARP, self).delete()
        VLAN.objects.filter(vlan_pint=self.carp_name).delete()
        Interfaces.objects.filter(int_interface=self.carp_name).delete()
        notifier().iface_destroy(self.carp_name)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            qs = Interfaces.objects.filter(int_interface=self.carp_name)
            if not qs.exists():
                Interfaces.objects.create(
                    int_interface=self.carp_name,
                    int_name=self.carp_name,
                    int_v4netmaskbit='32',
                )
            return super(CARP, self).save(*args, **kwargs)


class Failover(Model):
    ipaddress = IPAddressField(
        verbose_name=_("IP Address"),
        blank=True,
    )
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

    def __unicode__(self):
        return u"%s[%s]" % (self.volume, self.carp)

    @property
    def ipaddress(self):
        if notifier().failover_node() == 'A':
            return '169.254.10.80'
        else:
            return '169.254.10.20'

    class Meta:
        db_table = 'system_failover'
        verbose_name = _("Failover")
        verbose_name_plural = _("Failovers")

    class FreeAdmin:
        deletable = False
