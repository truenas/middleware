from django.db import models, transaction
from django.utils.translation import ugettext_lazy as _

from freenasUI.contrib.IPAddressField import IPAddressField
from freenasUI.freeadmin.models import Model
from freenasUI.middleware.notifier import notifier
from freenasUI.network.models import Interfaces, VLAN
from freenasUI.storage.models import Volume


class CARP(Model):
    carp_interface = models.ForeignKey(
        Interfaces,
        unique=True,
        verbose_name=_("Interface")
    )
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

    def save(self, *args, **kwargs):
        carpname = 'carp%d' % self.carp_number
        with transaction.atomic():
            if not self.id:
                iface = Interfaces.objects.create(
                    int_interface=carpname,
                    int_v4netmaskbit='32',
                )
                self.carp_interface = iface
            else:
                iface = self.carp_interface
                iface.int_interface = carpname
                iface.int_v4netmaskbit = '32'
                iface.save()
            return super(CARP, self).save(*args, **kwargs)


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

    disabled = models.BooleanField(
        default=False,
        blank=True,
    )

    master = models.BooleanField(
        default=False,
        blank=True,
    )

    def __unicode__(self):
        return u"%s[%s]" % (self.volume, self.carp)

    class Meta:
        db_table = 'system_failover'
        verbose_name = _("Failover")
        verbose_name_plural = _("Failovers")
        unique_together = (
            ('volume', 'carp'),
        )
