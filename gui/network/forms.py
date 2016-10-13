# Copyright 2010 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################
from struct import pack
import logging
import os
import re
import socket
import urllib2

from django.core.validators import RegexValidator
from django.db import transaction
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI import choices
from freenasUI.common.forms import Form, ModelForm
from freenasUI.common.system import get_sw_name
from freenasUI.contrib.IPAddressField import IP4AddressFormField
from freenasUI.freeadmin.sqlite3_ha.base import DBSync
from freenasUI.middleware.notifier import notifier
from freenasUI.network import models
from ipaddr import (
    IPAddress, AddressValueError,
    IPNetwork,
)

log = logging.getLogger('network.forms')
SW_NAME = get_sw_name()


class InterfacesForm(ModelForm):
    int_interface = forms.ChoiceField(label=_("NIC"))

    class Meta:
        fields = '__all__'
        model = models.Interfaces
        widgets = {
            'int_vhid': forms.widgets.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        super(InterfacesForm, self).__init__(*args, **kwargs)

        self._carp = False
        _n = notifier()
        if not _n.is_freenas() and _n.failover_licensed():
            from freenasUI.failover.utils import node_label_field
            self._carp = True
            node_label_field(
                _n.failover_node(),
                self.fields['int_ipv4address'],
                self.fields['int_ipv4address_b'],
            )

        if not self._carp:
            del self.fields['int_vip']
            del self.fields['int_vhid']
            del self.fields['int_critical']
            del self.fields['int_group']
            del self.fields['int_ipv4address_b']

        self.fields['int_interface'].choices = choices.NICChoices()
        self.fields['int_dhcp'].widget.attrs['onChange'] = (
            'javascript:toggleGeneric("id_int_dhcp", ["id_int_ipv4address", '
            '"id_int_ipv4address_b", "id_int_v4netmaskbit"]);')
        self.fields['int_ipv6auto'].widget.attrs['onChange'] = (
            'javascript:toggleGeneric("id_int_ipv6auto", '
            '["id_int_ipv6address", "id_int_v6netmaskbit"]);')
        if 'int_critical' in self.fields:
            self.fields['int_critical'].widget.attrs['onChange'] = (
                'javascript:toggleGeneric("id_int_critical", '
                '["id_int_group"], true);')
        dhcp = False
        ipv6auto = False
        if self.data:
            if self.data.get("int_dhcp"):
                dhcp = True
            if self.data.get("int_ipv6auto"):
                ipv6auto = True
        elif self.instance.id:
            if self.instance.int_dhcp:
                dhcp = True
            if self.instance.int_ipv6auto:
                ipv6auto = True
        if dhcp:
            if 'int_ipv4address' in self.fields:
                self.fields['int_ipv4address'].widget.attrs['disabled'] = (
                    'disabled')
            if 'int_ipv4address_b' in self.fields:
                self.fields['int_ipv4address_b'].widget.attrs['disabled'] = (
                    'disabled')
            self.fields['int_v4netmaskbit'].widget.attrs['disabled'] = (
                'disabled')
        if ipv6auto:
            self.fields['int_ipv6address'].widget.attrs['disabled'] = (
                'disabled')
            self.fields['int_v6netmaskbit'].widget.attrs['disabled'] = (
                'disabled')

        if self.instance.id:
            if 'int_group' in self.fields and not self.instance.int_critical:
                self.fields['int_group'].widget.attrs['disabled'] = (
                    'disabled'
                )
            self.fields['int_interface'] = forms.CharField(
                label=self.fields['int_interface'].label,
                initial=self.instance.int_interface,
                widget=forms.TextInput(
                    attrs={
                        'readonly': True,
                        'class': (
                            'dijitDisabled dijitTextBoxDisabled'
                            ' dijitValidationTextBoxDisabled'
                        ),
                    },
                )
            )

    def clean_int_interface(self):
        if self.instance.id:
            return self.instance.int_interface
        return self.cleaned_data.get('int_interface')

    def _common_clean_ipv4address(self, fname):
        ip = self.cleaned_data.get(fname)
        if ip:
            qs = models.Interfaces.objects.filter(**{fname: ip})
            qs2 = models.Alias.objects.filter(alias_v4address=ip)
            if self.instance.id:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists() or qs2.exists():
                raise forms.ValidationError(
                    _("You cannot configure multiple interfaces with the same "
                        "IP address (%s)") % ip)
        return ip

    def clean_int_ipv4address(self):
        return self._common_clean_ipv4address('int_ipv4address')

    def clean_int_ipv4address_b(self):
        return self._common_clean_ipv4address('int_ipv4address_b')

    def clean_int_dhcp(self):
        dhcp = self.cleaned_data.get("int_dhcp")
        if not dhcp:
            return dhcp
        qs = models.Interfaces.objects.filter(int_dhcp=True)
        if self.instance.id:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise forms.ValidationError(
                _("Only one interface can be used for DHCP")
            )
        return dhcp

    def clean_int_ipv6auto(self):
        ipv6auto = self.cleaned_data.get("int_ipv6auto")
        if not ipv6auto:
            return ipv6auto
        qs = models.Interfaces.objects.filter(int_ipv6auto=True)
        if self.instance.id:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise forms.ValidationError(
                _("Only one interface can have IPv6 autoconfiguration enabled")
            )
        return ipv6auto

    def clean_int_v4netmaskbit(self):
        ip = self.cleaned_data.get("int_ipv4address")
        nw = self.cleaned_data.get("int_v4netmaskbit")
        if not nw or not ip:
            return nw
        network = IPNetwork('%s/%s' % (ip, nw))
        used_networks = []
        qs = models.Interfaces.objects.all()
        if self.instance.id:
            qs = qs.exclude(id=self.instance.id)
        for iface in qs:
            if iface.int_v4netmaskbit:
                used_networks.append(
                    IPNetwork('%s/%s' % (
                        iface.int_ipv4address,
                        iface.int_v4netmaskbit,
                    ))
                )
            for alias in iface.alias_set.all():
                if alias.alias_v4netmaskbit:
                    used_networks.append(
                        IPNetwork('%s/%s' % (
                            alias.alias_v4address,
                            alias.alias_v4netmaskbit,
                        ))
                    )

        for unet in used_networks:
            if unet.overlaps(network):
                raise forms.ValidationError(
                    _("The network %s is already in use by another NIC.") % (
                        network.masked(),
                    )
                )
        return nw

    def clean_int_ipv6address(self):
        ip = self.cleaned_data.get("int_ipv6address")
        if ip:
            qs = models.Interfaces.objects.filter(int_ipv6address=ip)
            qs2 = models.Alias.objects.filter(alias_v6address=ip)
            if self.instance.id:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists() or qs2.exists():
                raise forms.ValidationError(
                    _("You cannot configure multiple interfaces with the same "
                        "IP address (%s)") % ip)
        return ip

    def clean_int_vhid(self):
        from freenasUI.tools.vhid import scan_for_vrrp
        vip = self.cleaned_data.get('int_vip')
        vhid = self.cleaned_data.get('int_vhid')
        iface = self.cleaned_data.get('int_interface')
        if vip and not vhid:
            raise forms.ValidationError(_('This field is required'))
        if not self.instance.id and iface:
            used_vhids = scan_for_vrrp(iface, count=None, timeout=5)
            if vhid in used_vhids:
                raise forms.ValidationError(
                    _("The following VHIDs are already in use: %s") % (
                        ', '.join([str(i) for i in used_vhids]),
                    )
                )
        return vhid

    def clean_int_group(self):
        vip = self.cleaned_data.get('int_vip')
        crit = self.cleaned_data.get('int_critical')
        group = self.cleaned_data.get('int_group')
        if vip and crit is True and not group:
            raise forms.ValidationError(_('This field is required.'))
        return group

    def clean_int_critical(self):
        CRIT = False
        qs = models.Interfaces.objects.all()
        if self.instance.id:
            qs = qs.exclude(id=self.instance.id)
        for interface in qs:
            if interface.int_critical:
                CRIT = True
        crit = self.cleaned_data.get('int_critical')
        vip = self.cleaned_data.get('int_vip')
        if crit and not vip:
            raise forms.ValidationError(_(
                'Virtual IP is required to set it as Critical for Failover'
            ))
        if crit:
            CRIT = True
        if not CRIT:
            raise forms.ValidationError(_('One interface must be marked critical for failover.'))
        return crit

    def clean(self):
        cdata = self.cleaned_data

        _n = notifier()
        if not _n.is_freenas() and _n.failover_licensed() and _n.failover_status() != 'SINGLE':
            from freenasUI.failover.models import Failover
            try:
                if Failover.objects.all()[0].disabled is False:
                    self._errors['__all__'] = self.error_class([_(
                        'Failover needs to be disabled to perform network '
                        'changes.'
                    )])
            except:
                log.warn('Failed to verify failover status', exc_info=True)

        ipv4key = 'int_ipv4address'
        ipv4addr = cdata.get(ipv4key)
        ipv4addr_b = cdata.get('int_ipv4address_b')
        ipv4net = cdata.get("int_v4netmaskbit")

        if ipv4addr and ipv4addr_b and ipv4net:
            network = IPNetwork('%s/%s' % (ipv4addr, ipv4net))
            if not network.overlaps(
                IPNetwork('%s/%s' % (ipv4addr_b, ipv4net))
            ):
                self._errors['int_ipv4address_b'] = self.error_class([
                    _('The IP must be within the same network')
                ])

        ipv6addr = cdata.get("int_ipv6address")
        ipv6net = cdata.get("int_v6netmaskbit")
        ipv4 = True if ipv4addr and ipv4net else False
        ipv6 = True if ipv6addr and ipv6net else False

        # IF one field of ipv4 is entered, require the another
        if (ipv4addr or ipv4net) and not ipv4:
            if not (ipv4addr or ipv4addr_b) and not self._errors.get(ipv4key):
                self._errors[ipv4key] = self.error_class([
                    _("You have to specify IPv4 address as well"),
                ])
            if not ipv4net and 'int_v4netmaskbit' not in self._errors:
                self._errors['int_v4netmaskbit'] = self.error_class([
                    _("You have to choose IPv4 netmask as well"),
                ])

        # IF one field of ipv6 is entered, require the another
        if (ipv6addr or ipv6net) and not ipv6:
            if not ipv6addr and not self._errors.get('int_ipv6address'):
                self._errors['int_ipv6address'] = self.error_class([
                    _("You have to specify IPv6 address as well"),
                ])
            if not ipv6net:
                self._errors['int_v6netmaskbit'] = self.error_class([
                    _("You have to choose IPv6 netmask as well"),
                ])

        if ipv6 and ipv4:
            self._errors['__all__'] = self.error_class([
                _("You have to choose between IPv4 or IPv6"),
            ])

        vip = cdata.get("int_vip")
        dhcp = cdata.get("int_dhcp")
        if not dhcp:
            if vip and not ipv4addr_b:
                self._errors['int_ipv4address_b'] = self.error_class([
                    _("This field is required for failover")
                ])
            if vip and not ipv4addr:
                self._errors['int_ipv4address'] = self.error_class([
                    _("This field is required for failover")
                ])

        return cdata

    def save(self, *args, **kwargs):
        with DBSync():
            obj = super(InterfacesForm, self).save(*args, **kwargs)
        notifier().start("network")
        return obj

    def delete(self, *args, **kwargs):
        with DBSync():
            return super(InterfacesForm, self).delete(*args, **kwargs)


class InterfacesDeleteForm(forms.Form):

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)
        super(InterfacesDeleteForm, self).__init__(*args, **kwargs)

    def clean(self):
        _n = notifier()
        if not _n.is_freenas() and _n.failover_status() == 'MASTER':
            from freenasUI.failover.models import Failover
            if not Failover.objects.all()[0].disabled:
                self._errors['__all__'] = self.error_class([
                    _("You are not allowed to delete interfaces while failover is enabled.")
                ])
        return self.cleaned_data


class IPMIForm(Form):
    # Max password length via IPMI v2.0 is 20 chars. We only support IPMI
    # v2.0+ compliant boards thus far.
    ipmi_password1 = forms.CharField(
        label=_("Password"),
        max_length=20,
        widget=forms.PasswordInput,
        required=False
    )
    ipmi_password2 = forms.CharField(
        label=_("Password confirmation"),
        max_length=20,
        widget=forms.PasswordInput,
        help_text=_("Enter the same password as above, for verification."),
        required=False
    )
    dhcp = forms.BooleanField(
        label=_("DHCP"),
        required=False,
    )
    ipv4address = IP4AddressFormField(
        initial='',
        required=False,
        label=_("IPv4 Address"),
    )
    ipv4netmaskbit = forms.ChoiceField(
        choices=choices.v4NetmaskBitList,
        required=False,
        label=_("IPv4 Netmask"),
    )
    ipv4gw = IP4AddressFormField(
        initial='',
        required=False,
        label=_("IPv4 Default Gateway"),
    )
    vlanid = forms.IntegerField(
        label=_("VLAN ID"),
        required=False,
        widget=forms.widgets.TextInput(),
    )

    def __init__(self, *args, **kwargs):
        super(IPMIForm, self).__init__(*args, **kwargs)
        self.fields['dhcp'].widget.attrs['onChange'] = (
            'javascript:toggleGeneric('
            '"id_dhcp", ["id_ipv4address", "id_ipv4netmaskbit"]);'
        )

        channels = []
        _n = notifier()
        for i in range(1, 17):
            try:
                data = _n.ipmi_get_lan(channel=i)
            except:
                continue

            if not data:
                continue

            channels.append((i, i))

        self.fields['channel'] = forms.ChoiceField(
            choices=channels,
            label=_('Channel'),
        )
        self.fields.keyOrder.remove('channel')
        self.fields.keyOrder.insert(0, 'channel')

    def clean_ipmi_password2(self):
        ipmi_password1 = self.cleaned_data.get("ipmi_password1", "")
        ipmi_password2 = self.cleaned_data["ipmi_password2"]
        if ipmi_password1 != ipmi_password2:
            raise forms.ValidationError(
                _("The two password fields didn't match.")
            )
        return ipmi_password2

    def clean_ipv4netmaskbit(self):
        try:
            cidr = int(self.cleaned_data.get("ipv4netmaskbit"))
        except ValueError:
            return None
        bits = 0xffffffff ^ (1 << 32 - cidr) - 1
        return socket.inet_ntoa(pack('>I', bits))

    def clean_ipv4address(self):
        ipv4 = self.cleaned_data.get('ipv4address')
        if ipv4:
            ipv4 = str(ipv4)
        return ipv4

    def clean_ipv4gw(self):
        ipv4 = self.cleaned_data.get('ipv4gw')
        if ipv4:
            ipv4 = str(ipv4)
        return ipv4


class GlobalConfigurationForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.GlobalConfiguration

    def __init__(self, *args, **kwargs):
        super(GlobalConfigurationForm, self).__init__(*args, **kwargs)
        if hasattr(notifier, 'failover_licensed'):
            if not notifier().failover_licensed():
                del self.fields['gc_hostname_b']

            else:
                from freenasUI.failover.utils import node_label_field
                node_label_field(
                    notifier().failover_node(),
                    self.fields['gc_hostname'],
                    self.fields['gc_hostname_b'],
                )
        else:
            del self.fields['gc_hostname_b']

    def _clean_nameserver(self, value):
        if value:
            if value.is_loopback:
                raise forms.ValidationError(
                    _("Loopback is not a valid nameserver"))
            elif value.is_unspecified:
                raise forms.ValidationError(
                    _("Unspecified addresses are not valid as nameservers"))
            elif value.version == 4:
                if str(value) == '255.255.255.255':
                    raise forms.ValidationError(
                        _("This is not a valid nameserver address"))
                elif str(value).startswith('169.254'):
                    raise forms.ValidationError(
                        _("169.254/16 subnet is not valid for nameserver"))

    def clean_gc_nameserver1(self):
        val = self.cleaned_data.get("gc_nameserver1")
        self._clean_nameserver(val)
        return val

    def clean_gc_nameserver2(self):
        val = self.cleaned_data.get("gc_nameserver2")
        self._clean_nameserver(val)
        return val

    def clean_gc_nameserver3(self):
        val = self.cleaned_data.get("gc_nameserver3")
        self._clean_nameserver(val)
        return val

    def clean_gc_netwait_ip(self):
        iplist = self.cleaned_data.get("gc_netwait_ip").strip()
        if not iplist:
            return ''
        for ip in iplist.split(' '):
            try:
                IPAddress(ip)
            except (AddressValueError, ValueError):
                raise forms.ValidationError(
                    _("The IP \"%s\" is not valid") % ip
                )
        return iplist

    def clean(self):
        cleaned_data = self.cleaned_data
        nameserver1 = cleaned_data.get("gc_nameserver1")
        nameserver2 = cleaned_data.get("gc_nameserver2")
        nameserver3 = cleaned_data.get("gc_nameserver3")
        if nameserver3:
            if nameserver2 == "":
                msg = _(u"Must fill out nameserver 2 before "
                        "filling out nameserver 3")
                self._errors["gc_nameserver3"] = self.error_class([msg])
                msg = _(u"Required when using nameserver 3")
                self._errors["gc_nameserver2"] = self.error_class([msg])
                del cleaned_data["gc_nameserver2"]
            if nameserver1 == "":
                msg = _(u"Must fill out nameserver 1 before "
                        "filling out nameserver 3")
                self._errors["gc_nameserver3"] = self.error_class([msg])
                msg = _(u"Required when using nameserver 3")
                self._errors["gc_nameserver1"] = self.error_class([msg])
                del cleaned_data["gc_nameserver1"]
            if nameserver1 == "" or nameserver2 == "":
                del cleaned_data["gc_nameserver3"]
        elif nameserver2:
            if nameserver1 == "":
                del cleaned_data["gc_nameserver2"]
                msg = _(u"Must fill out nameserver 1 before "
                        "filling out nameserver 2")
                self._errors["gc_nameserver2"] = self.error_class([msg])
                msg = _(u"Required when using nameserver 3")
                self._errors["gc_nameserver1"] = self.error_class([msg])
                del cleaned_data["gc_nameserver1"]
        return cleaned_data

    def save(self):
        # TODO: new IP address should be added in a side-by-side manner
        # or the interface wouldn't appear once IP was changed.
        retval = super(GlobalConfigurationForm, self).save()

        whattoreload = "hostname"
        if (
            self.instance._orig_gc_domain != self.cleaned_data.get('gc_domain') or
            self.instance._orig_gc_nameserver1 != self.cleaned_data.get('gc_nameserver1') or
            self.instance._orig_gc_nameserver2 != self.cleaned_data.get('gc_nameserver2') or
            self.instance._orig_gc_nameserver3 != self.cleaned_data.get('gc_nameserver3')
        ):
            # Note notifier's _reload_resolvconf has reloading hostname folded in it
            whattoreload = "resolvconf"
        if (
            self.instance._orig_gc_ipv4gateway != self.cleaned_data.get('gc_ipv4gateway') or
            self.instance._orig_gc_ipv6gateway != self.cleaned_data.get('gc_ipv6gateway')
        ):
            # this supersedes all since it has hostname and resolvconf reloads folded in it
            whattoreload = "networkgeneral"

        notifier().reload(whattoreload)

        http_proxy = self.cleaned_data.get('gc_httpproxy')
        if http_proxy:
            os.environ['http_proxy'] = http_proxy
            os.environ['https_proxy'] = http_proxy
        elif not http_proxy:
            if 'http_proxy' in os.environ:
                del os.environ['http_proxy']
            if 'https_proxy' in os.environ:
                del os.environ['https_proxy']

        # Reset global opener so ProxyHandler can be recalculated
        urllib2.install_opener(None)

        return retval


class HostnameForm(Form):

    hostname = forms.CharField(
        max_length=200,
        validators=[RegexValidator(
            regex=r'^[a-zA-Z\.\-\_0-9]+$',
        )],
    )

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance')
        super(HostnameForm, self).__init__(*args, **kwargs)

    def clean_hostname(self):
        hostname = self.cleaned_data.get('hostname')
        if '.' not in hostname:
            raise forms.ValidationError(_(
                'You need a domain, e.g. hostname.domain'
            ))
        host, domain = hostname.split('.', 1)
        return host, domain

    def save(self):
        host, domain = self.cleaned_data.get('hostname')
        self.instance.gc_hostname = host
        orig_gc_domain = self.instance.gc_domain
        self.instance.gc_domain = domain
        self.instance.save()
        if orig_gc_domain != self.instance.gc_domain:
            notifier().reload("resolvconf")
        else:
            notifier().reload("hostname")


class VLANForm(ModelForm):
    vlan_pint = forms.ChoiceField(label=_("Parent Interface"))

    class Meta:
        fields = '__all__'
        model = models.VLAN

    def __init__(self, *args, **kwargs):
        super(VLANForm, self).__init__(*args, **kwargs)
        self.fields['vlan_pint'].choices = list(
            choices.NICChoices(novlan=True, exclude_configured=False)
        )

    def clean_vlan_vint(self):
        name = self.cleaned_data['vlan_vint']
        reg = re.search(r'^vlan(?P<num>\d+)$', name)
        if not reg:
            raise forms.ValidationError(
                _("The name must be vlanX where X is a number. Example: vlan0")
            )
        return "vlan%d" % (int(reg.group("num")), )

    def clean_vlan_tag(self):
        tag = self.cleaned_data['vlan_tag']
        if tag > 4095 or tag < 1:
            raise forms.ValidationError(_("VLAN Tags are 1 - 4095 inclusive"))
        return tag

    def save(self):
        vlan_pint = self.cleaned_data['vlan_pint']
        with DBSync():
            if len(models.Interfaces.objects.filter(int_interface=vlan_pint)) == 0:
                vlan_interface = models.Interfaces(
                    int_interface=vlan_pint,
                    int_name=vlan_pint,
                    int_dhcp=False,
                    int_ipv6auto=False,
                    int_options='up',
                )
                vlan_interface.save()
            retval = super(VLANForm, self).save()
        notifier().start("network")
        return retval

    def delete(self, *args, **kwargs):
        with DBSync():
            return super(VLANForm, self).delete(*args, **kwargs)
        notifier().start("network")


class LAGGInterfaceForm(ModelForm):
    lagg_interfaces = forms.MultipleChoiceField(
        widget=forms.SelectMultiple(),
        label=_('Physical NICs in the LAGG'),
    )

    class Meta:
        model = models.LAGGInterface
        exclude = ('lagg_interface', )
        widgets = {
            'lagg_protocol': forms.RadioSelect(),
        }

    def __init__(self, *args, **kwargs):
        super(LAGGInterfaceForm, self).__init__(*args, **kwargs)
        self.fields['lagg_interfaces'].choices = list(
            choices.NICChoices(nolagg=True)
        )
        # Remove empty option (e.g. -------)
        self.fields['lagg_protocol'].choices = (
            self.fields['lagg_protocol'].choices[1:]
        )

    def save(self, *args, **kwargs):

        # Search for a available slot for laggX interface
        interface_names = [
            v[0]
            for v in models.Interfaces.objects.all()
            .values_list('int_interface')
        ]
        candidate_index = 0
        while ("lagg%d" % (candidate_index)) in interface_names:
            candidate_index += 1
        lagg_name = "lagg%d" % candidate_index
        lagg_protocol = self.cleaned_data['lagg_protocol']
        lagg_member_list = self.cleaned_data['lagg_interfaces']
        with DBSync():
            with transaction.atomic():
                # Step 1: Create an entry in interface table that
                # represents the lagg interface
                lagg_interface = models.Interfaces(
                    int_interface=lagg_name,
                    int_name=lagg_name,
                    int_dhcp=False,
                    int_ipv6auto=False
                )
                lagg_interface.save()
                # Step 2: Write associated lagg attributes
                lagg_interfacegroup = models.LAGGInterface(
                    lagg_interface=lagg_interface,
                    lagg_protocol=lagg_protocol
                )
                lagg_interfacegroup.save()
                # Step 3: Write lagg's members in the right order
                order = 0
                for interface in lagg_member_list:
                    lagg_member_entry = models.LAGGInterfaceMembers(
                        lagg_interfacegroup=lagg_interfacegroup,
                        lagg_ordernum=order,
                        lagg_physnic=interface,
                        lagg_deviceoptions='up'
                    )
                    lagg_member_entry.save()
                    order = order + 1
        self.instance = lagg_interfacegroup
        notifier().start("network")
        return lagg_interfacegroup

    def delete(self, *args, **kwargs):
        with DBSync():
            return super(LAGGInterfaceForm, self).delete(*args, **kwargs)
        notifier().start("network")


class LAGGInterfaceMemberForm(ModelForm):
    lagg_physnic = forms.ChoiceField(label=_("LAGG Physical NIC"))

    class Meta:
        fields = '__all__'
        model = models.LAGGInterfaceMembers

    def __init__(self, *args, **kwargs):
        super(LAGGInterfaceMemberForm, self).__init__(*args, **kwargs)
        if self.instance.id:
            self.fields['lagg_interfacegroup'].widget.attrs['readonly'] = True
            self.fields['lagg_interfacegroup'].widget.attrs['class'] = (
                'dijitDisabled dijitSelectDisabled')
            self.fields['lagg_physnic'].widget.attrs['readonly'] = True
            self.fields['lagg_physnic'].widget.attrs['class'] = (
                'dijitDisabled dijitSelectDisabled')
            self.fields['lagg_physnic'].choices = (
                (self.instance.lagg_physnic, self.instance.lagg_physnic),
            )
        else:
            self.fields['lagg_physnic'].choices = list(
                choices.NICChoices(nolagg=True, novlan=True)
            )

    def save(self, *args, **kwargs):
        with DBSync():
            obj = super(LAGGInterfaceMemberForm, self).save(*args, **kwargs)
        notifier().start("network")
        return obj


class StaticRouteForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.StaticRoute

    def save(self):
        retval = super(StaticRouteForm, self).save()
        notifier().start("routing")
        return retval

    def clean_sr_destination(self):
        sr = self.cleaned_data['sr_destination']
        sr = re.sub(r'\s{2,}', ' ', sr).strip()
        try:
            if sr.find("/") != -1:
                socket.inet_aton(sr.split("/")[0])
                if int(sr.split("/")[1]) > 32 or int(sr.split("/")[1]) < 0:
                    raise
            else:
                raise
        except:
            raise forms.ValidationError(
                _("The network '%s' is not valid, CIDR expected.") % sr)
        return sr


class AliasForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.Alias

    def __init__(self, *args, **kwargs):
        super(AliasForm, self).__init__(*args, **kwargs)
        self.instance._original_alias_v4address = self.instance.alias_v4address
        self.instance._original_alias_v4netmaskbit = (
            self.instance.alias_v4netmaskbit)
        self.instance._original_alias_v6address = self.instance.alias_v6address
        self.instance._original_alias_v6netmaskbit = (
            self.instance.alias_v6netmaskbit)

        _n = notifier()
        if not _n.is_freenas() and _n.failover_licensed():
            from freenasUI.failover.utils import node_label_field
            node_label_field(
                _n.failover_node(),
                self.fields['alias_v4address'],
                self.fields['alias_v4address_b'],
            )
            node_label_field(
                _n.failover_node(),
                self.fields['alias_v6address'],
                self.fields['alias_v6address_b'],
            )
        else:
            del self.fields['alias_vip']
            del self.fields['alias_v4address_b']
            del self.fields['alias_v6address_b']

    def _common_alias(self, field):
        ip = self.cleaned_data.get(field)
        par_ip = self.parent.cleaned_data.get("int_ipv4address") \
            if hasattr(self, 'parent') and \
            hasattr(self.parent, 'cleaned_data') else None
        if ip:
            qs = models.Interfaces.objects.filter(
                Q(int_ipv4address=ip) | Q(int_ipv4address_b=ip)
            )
            qs2 = models.Alias.objects.filter(
                Q(alias_v4address=ip) | Q(alias_v4address_b=ip)
            )
            if self.instance.id:
                qs2 = qs2.exclude(id=self.instance.id)
            if qs.exists() or qs2.exists() or par_ip == ip:
                raise forms.ValidationError(
                    _("You cannot configure multiple interfaces with the same "
                        "IP address (%s)") % ip)
        return ip

    def clean_alias_v4address(self):
        return self._common_alias('alias_v4address')

    def clean_alias_v4address_b(self):
        return self._common_alias('alias_v4address_b')

    def clean_alias_v4netmaskbit(self):
        vip = self.cleaned_data.get("alias_vip")
        ip = self.cleaned_data.get("alias_v4address")
        nw = self.cleaned_data.get("alias_v4netmaskbit")
        if not nw or not ip:
            return nw
        network = IPNetwork('%s/%s' % (ip, nw))

        if vip:
            if not network.overlaps(IPNetwork('%s/%s' % (vip, nw))):
                raise forms.ValidationError(_(
                    'Virtual IP is not in the same network'
                ))

        if (
            self.instance.id and
            self.instance.alias_interface.int_interface.startswith('carp')
        ):
            return nw
        used_networks = []
        qs = models.Interfaces.objects.all().exclude(
            int_interface__startswith='carp'
        )
        if self.instance.id:
            qs = qs.exclude(id=self.instance.alias_interface.id)
        elif self.parent.instance.id:
            qs = qs.exclude(id=self.parent.instance.id)
        for iface in qs:
            if iface.int_v4netmaskbit:
                used_networks.append(
                    IPNetwork('%s/%s' % (
                        iface.int_ipv4address,
                        iface.int_v4netmaskbit,
                    ))
                )
            for alias in iface.alias_set.all():
                if alias.alias_v4netmaskbit:
                    used_networks.append(
                        IPNetwork('%s/%s' % (
                            alias.alias_v4address,
                            alias.alias_v4netmaskbit,
                        ))
                    )

        for unet in used_networks:
            if unet.overlaps(network):
                raise forms.ValidationError(
                    _("The network %s is already in use by another NIC.") % (
                        network.masked(),
                    )
                )
        return nw

    def clean_alias_v6address(self):
        ip = self.cleaned_data.get("alias_v6address")
        par_ip = self.parent.cleaned_data.get("int_ipv6address") \
            if hasattr(self, 'parent') and \
            hasattr(self.parent, 'cleaned_data') else None
        if ip:
            qs = models.Interfaces.objects.filter(int_ipv6address=ip)
            qs2 = models.Alias.objects.filter(alias_v6address=ip)
            if self.instance.id:
                qs2 = qs2.exclude(id=self.instance.id)
            if qs.exists() or qs2.exists() or par_ip == ip:
                raise forms.ValidationError(
                    _("You cannot configure multiple interfaces with the same "
                        "IP address (%s)") % ip)
        return ip

    def clean(self):
        cdata = self.cleaned_data

        ipv4vip = cdata.get("alias_vip")
        ipv4addr = cdata.get("alias_v4address")
        ipv4net = cdata.get("alias_v4netmaskbit")
        ipv6addr = cdata.get("alias_v6address")
        ipv6net = cdata.get("alias_v6netmaskbit")
        ipv4 = True if ipv4addr and ipv4net else False
        ipv6 = True if ipv6addr and ipv6net else False

        # IF one field of ipv4 is entered, require the another
        if (ipv4addr or ipv4net) and not ipv4:
            if not ipv4addr and not self._errors.get('alias_v4address'):
                self._errors['alias_v4address'] = self.error_class([
                    _("You have to specify IPv4 address as well per alias"),
                ])
            if not ipv4net and 'alias_v4netmaskbit' not in self._errors:
                self._errors['alias_v4netmaskbit'] = self.error_class([
                    _("You have to choose IPv4 netmask as well per alias"),
                ])

        # IF one field of ipv6 is entered, require the another
        if (ipv6addr or ipv6net) and not ipv6:
            if not ipv6addr and not self._errors.get('alias_v6address'):
                self._errors['alias_v6address'] = self.error_class([
                    _("You have to specify IPv6 address as well per alias"),
                ])
            if not ipv6net:
                self._errors['alias_v6netmaskbit'] = self.error_class([
                    _("You have to choose IPv6 netmask as well per alias"),
                ])

        if ipv6 and ipv4:
            self._errors['__all__'] = self.error_class([
                _("You have to choose between IPv4 or IPv6 per alias"),
            ])

        configured_vip = False
        if ipv4vip and hasattr(self, 'parent'):
            iface = self.parent.instance
            ip = IPNetwork('%s/32' % ipv4vip)
            network = IPNetwork('%s/%s' % (
                iface.int_ipv4address,
                iface.int_v4netmaskbit,
            ))
            if ip.overlaps(network):
                configured_vip = True

        if (
            not configured_vip and not ipv6 and not (ipv6addr or ipv6net) and
            not ipv4 and not (ipv4addr or ipv4net)
        ):
            self._errors['__all__'] = self.error_class([
                _("You must specify either an valid IPv4 or IPv6 with maskbit "
                    "per alias"),
            ])

        return cdata
