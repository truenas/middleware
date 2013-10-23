from django.db import models
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.contrib.IPAddressField import IPAddressField, IP4AddressField
from freenasUI.freeadmin.models import Model
from freenasUI.storage.models import Volume


class CARP(Model):
    carp_vhid = models.PositiveIntegerField(
        verbose_name=_("Virtual Host ID"),
        unique=True,
    )
    carp_pass = models.CharField(
        max_length=100,
        blank=False,
        verbose_name=_("Password")
    )
    carp_v4address = IP4AddressField(
        verbose_name=_("IPv4 Address"),
        blank=True,
        default='',
    )
    carp_v4netmaskbit = models.CharField(
        max_length=3,
        choices=choices.v4NetmaskBitList,
        blank=True,
        default='',
        verbose_name=_("IPv4 Netmask"),
        help_text=""
    )
    carp_skew = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Advertisements Skew"),
        blank=True,
        null=True,
    )

    def __unicode__(self):
        return u'%d:%s' % (self.carp_vhid, self.carp_v4address)

    class Meta:
        verbose_name = _("CARP")
        verbose_name_plural = _("CARPs")
        db_table = 'network_carp'

    class FreeAdmin:
        icon_object = u"CARPIcon"
        icon_model = u"CARPIcon"
        icon_add = u"AddCARPIcon"
        icon_view = u"ViewAllCARPsIcon"
        menu_child_of = 'network'


class Failover(Model):
    volume = models.ForeignKey(
        Volume,
        limit_choices_to={'vol_fstype__exact': 'ZFS'},
        verbose_name=_("Volume"),
    )
    carp = models.ForeignKey(
        CARP,
        verbose_name=_("CARP"),
    )
    ipaddress = IPAddressField(verbose_name=_("IP Address"))

    def __unicode__(self):
        return u"%s[%s]" % (self.volume, self.carp)

    class Meta:
        db_table = 'system_failover'
        verbose_name = _("Failover")
        verbose_name_plural = _("Failovers")
        unique_together = (
            ('volume', 'carp'),
        )
