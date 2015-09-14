#+
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
from django.core.urlresolvers import reverse
from django.db import transaction
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from dojango.forms.formsets import formset_factory

from dojango import forms
from freenasUI import choices
from freenasUI.common.forms import Form, ModelForm
from freenasUI.common.system import get_sw_name
from freenasUI.contrib.IPAddressField import IP4AddressFormField, IPAddressFormField
from freenasUI.middleware.notifier import notifier
from freenasUI.network import models
from ipaddr import (
    IPAddress, AddressValueError,
    IPNetwork,
)

log = logging.getLogger('network.forms')
SW_NAME = get_sw_name()


class InterfacesForm(ModelForm):
    class Meta:
        fields = ['id', 'int_name', 'int_dhcp', 'int_ipv6auto', 'int_disableipv6', 'int_mtu']
        model = models.Interfaces
        widgets = {'int_mtu': forms.widgets.TextInput()}


class IPMIForm(Form):
    # Max password length via IPMI v2.0 is 20 chars. We only support IPMI
    # v2.0+ compliant boards thus far.
    password = forms.CharField(
        label=_("Password"),
        max_length=20,
        widget=forms.PasswordInput,
        required=False
    )
    password2 = forms.CharField(
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
    address = IP4AddressFormField(
        initial='',
        required=False,
        label=_("IPv4 Address"),
    )
    netmask = forms.ChoiceField(
        choices=choices.v4NetmaskBitList,
        required=False,
        label=_("IPv4 Netmask"),
    )
    gateway = IP4AddressFormField(
        initial='',
        required=False,
        label=_("IPv4 Default Gateway"),
    )
    vlan_id = forms.IntegerField(
        label=_("VLAN ID"),
        required=False,
        widget=forms.widgets.TextInput(),
    )

    def __init__(self, *args, **kwargs):
        super(IPMIForm, self).__init__(*args, **kwargs)
        self.fields['dhcp'] .widget.attrs['onChange'] = (
            'javascript:toggleGeneric('
            '"id_dhcp", ["id_address", "id_netmask"]);'
        )

        from freenasUI.middleware.connector import connection as dispatcher
        channels = []
        try:
            channels = map(lambda c: (str(c), str(c)), dispatcher.call_sync('ipmi.channels'))
        except:
            pass

        self.fields['channel'] = forms.ChoiceField(
            choices=channels,
            label=_('Channel')
        )
        self.fields['channel'].widget.attrs['onChange'] = 'javascript:load_into("tab_IPMI", "%s?channel=" + this.value)' % reverse('network_ipmi')
        self.fields.keyOrder.remove('channel')
        self.fields.keyOrder.insert(0, 'channel')

    def clean_ipmi_password2(self):
        ipmi_password1 = self.cleaned_data.get("password", "")
        ipmi_password2 = self.cleaned_data["password2"]
        if ipmi_password1 != ipmi_password2:
            raise forms.ValidationError(
                _("The two password fields didn't match.")
            )
        return ipmi_password2

    def clean_ipv4netmaskbit(self):
        try:
            cidr = int(self.cleaned_data.get("netmask"))
        except ValueError:
            return None
        bits = 0xffffffff ^ (1 << 32 - cidr) - 1
        return socket.inet_ntoa(pack('>I', bits))

    def clean_ipv4address(self):
        ipv4 = self.cleaned_data.get('address')
        if ipv4:
            ipv4 = str(ipv4)
        return ipv4

    def clean_ipv4gw(self):
        ipv4 = self.cleaned_data.get('gateway')
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
        if self.instance._orig_gc_ipv4gateway != self.cleaned_data.get('gc_ipv4gateway'):
            whattoreload = "networkgeneral"
        if self.instance._orig_gc_ipv6gateway != self.cleaned_data.get('gc_ipv6gateway'):
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

    def save(self):
        from freenasUI.middleware.connector import connection as dispatcher
        hostname = self.cleaned_data.get('hostname')
        dispatcher.call_task_sync('system.general.configure', {
            'hostname': hostname
        })


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
        if tag > 4095:
            raise forms.ValidationError(_("VLAN Tags are 1 - 4095 inclusive"))
        return tag

    def save(self):
        vlan_pint = self.cleaned_data['vlan_pint']
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


class StaticRouteForm(ModelForm):
    class Meta:
        fields = ['sr_name', 'sr_type', 'sr_destination', 'sr_netmask', 'sr_gateway']
        model = models.StaticRoute


class HostForm(ModelForm):
    class Meta:
        fields = ['name', 'address']
        model = models.Host


class AliasForm(Form):
    type = forms.ChoiceField(
        choices=choices.AddressFamily,
        label=_("Address family")
    )

    address = IPAddressFormField(
        label=_("Address")
    )

    netmask = forms.IntegerField(
        label=_("Prefix length"),
    )


AliasFormSet = formset_factory(AliasForm, extra=0)
