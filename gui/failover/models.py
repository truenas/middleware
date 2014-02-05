from django.db import models
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.contrib.IPAddressField import IPAddressField, IP4AddressField
from freenasUI.freeadmin.models import Model
from freenasUI.network.models import Interfaces, VLAN
from freenasUI.storage.models import Volume


class CARP(Model):
    carp_interface = models.ForeignKey(
        Interfaces,
        unique=True,
        verbose_name=_("Interface")
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

    def __unicode__(self):
        try:
            return u'%d:%s' % (self.carp_vhid, self.carp_interface.int_ipv4address)
        except:
            return self.carp_vhid

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

    def delete(self):
        super(CARP, self).delete()
        VLAN.objects.filter(
            vlan_pint=self.carp_interface.int_interface
            ).delete()
        self.carp_interface.delete()
        notifier().iface_destroy(self.carp_interface.int_interface)


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
