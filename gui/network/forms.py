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
import logging
import re
import socket

from django.db import transaction
from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI import choices
from freenasUI.common.forms import ModelForm
from freenasUI.middleware.notifier import notifier
from freenasUI.network import models
from ipaddr import (
    IPAddress, AddressValueError,
    IPNetwork,
)

log = logging.getLogger('network.forms')


class InterfacesForm(ModelForm):
    int_interface = forms.ChoiceField(label=_("NIC"))

    class Meta:
        model = models.Interfaces

    def __init__(self, *args, **kwargs):
        super(InterfacesForm, self).__init__(*args, **kwargs)
        self.fields['int_interface'].choices = choices.NICChoices()
        self.fields['int_dhcp'].widget.attrs['onChange'] = (
            'javascript:toggleGeneric("id_int_dhcp", ["id_int_ipv4address", '
            '"id_int_v4netmaskbit"]);')
        self.fields['int_ipv6auto'].widget.attrs['onChange'] = (
            'javascript:toggleGeneric("id_int_ipv6auto", '
            '["id_int_ipv6address", "id_int_v6netmaskbit"]);')
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
            self.fields['int_ipv4address'].widget.attrs['disabled'] = (
                'disabled')
            self.fields['int_v4netmaskbit'].widget.attrs['disabled'] = (
                'disabled')
        if ipv6auto:
            self.fields['int_ipv6address'].widget.attrs['disabled'] = (
                'disabled')
            self.fields['int_v6netmaskbit'].widget.attrs['disabled'] = (
                'disabled')

        if self.instance.id:
            self.fields['int_interface'] = \
                forms.CharField(
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

    def clean_int_ipv4address(self):
        ip = self.cleaned_data.get("int_ipv4address")
        if ip:
            qs = models.Interfaces.objects.filter(int_ipv4address=ip)
            qs2 = models.Alias.objects.filter(alias_v4address=ip)
            if self.instance.id:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists() or qs2.exists():
                raise forms.ValidationError(
                    _("You cannot configure multiple interfaces with the same "
                        "IP address (%s)") % ip)
        return ip

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

    def clean(self):
        cdata = self.cleaned_data

        ipv4addr = cdata.get("int_ipv4address")
        ipv4net = cdata.get("int_v4netmaskbit")
        ipv6addr = cdata.get("int_ipv6address")
        ipv6net = cdata.get("int_v6netmaskbit")
        ipv4 = True if ipv4addr and ipv4net else False
        ipv6 = True if ipv6addr and ipv6net else False

        # IF one field of ipv4 is entered, require the another
        if (ipv4addr or ipv4net) and not ipv4:
            if not ipv4addr and not self._errors.get('int_ipv4address'):
                self._errors['int_ipv4address'] = self.error_class([
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

        return cdata

    def done(self, *args, **kwargs):
        # TODO: new IP address should be added in a side-by-side manner
        # or the interface wouldn't appear once IP was changed.
        notifier().start("network")


class GlobalConfigurationForm(ModelForm):

    class Meta:
        model = models.GlobalConfiguration

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
        notifier().reload("networkgeneral")
        return retval


class VLANForm(ModelForm):
    vlan_pint = forms.ChoiceField(label=_("Parent Interface"))

    class Meta:
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
        if  tag > 4095:
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
        with transaction.commit_on_success():
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
        return lagg_interfacegroup


class LAGGInterfaceMemberForm(ModelForm):
    lagg_physnic = forms.ChoiceField(label=_("LAGG Physical NIC"))

    class Meta:
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
        model = models.Alias
        fields = (
            'alias_v4address',
            'alias_v4netmaskbit',
            'alias_v6address',
            'alias_v6netmaskbit',
        )

    def __init__(self, *args, **kwargs):
        super(AliasForm, self).__init__(*args, **kwargs)
        self.instance._original_alias_v4address = self.instance.alias_v4address
        self.instance._original_alias_v4netmaskbit = (
            self.instance.alias_v4netmaskbit)
        self.instance._original_alias_v6address = self.instance.alias_v6address
        self.instance._original_alias_v6netmaskbit = (
            self.instance.alias_v6netmaskbit)

    def clean_alias_v4address(self):
        ip = self.cleaned_data.get("alias_v4address")
        par_ip = self.parent.cleaned_data.get("int_ipv4address") \
            if hasattr(self, 'parent') and \
            hasattr(self.parent, 'cleaned_data') else None
        if ip:
            qs = models.Interfaces.objects.filter(int_ipv4address=ip)
            qs2 = models.Alias.objects.filter(alias_v4address=ip)
            if self.instance.id:
                qs2 = qs2.exclude(id=self.instance.id)
            if qs.exists() or qs2.exists() or par_ip == ip:
                raise forms.ValidationError(
                    _("You cannot configure multiple interfaces with the same "
                        "IP address (%s)") % ip)
        return ip

    def clean_alias_v4netmaskbit(self):
        ip = self.cleaned_data.get("alias_v4address")
        nw = self.cleaned_data.get("alias_v4netmaskbit")
        if not nw or not ip:
            return nw
        network = IPNetwork('%s/%s' % (ip, nw))
        used_networks = []
        qs = models.Interfaces.objects.all()
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
        if not ipv6 and not (ipv6addr or ipv6net) and not ipv4 and \
                not (ipv4addr or ipv4net):
            self._errors['__all__'] = self.error_class([
                _("You must specify either an valid IPv4 or IPv6 with maskbit "
                    "per alias"),
            ])

        return cdata

    def save(self, commit):
        m = super(AliasForm, self).save(commit)

        iface = models.Interfaces.objects.filter(
            id=self.instance.alias_interface_id
        )
        if not iface:
            return m

        change = False
        iface = str(iface[0].int_interface)
        kwargs = {'oldip': str(self.instance._original_alias_v4address)}
        if self.instance._original_alias_v4address != \
                self.instance.alias_v4address:
            kwargs['oldip'] = str(self.instance._original_alias_v4address)
            kwargs['newip'] = str(self.instance.alias_v4address)
            change = True

        if self.instance._original_alias_v4netmaskbit != \
                self.instance.alias_v4netmaskbit:
            kwargs['oldnetmask'] = str(
                self.instance._original_alias_v4netmaskbit
            )
            kwargs['newnetmask'] = str(self.instance.alias_v4netmaskbit)
            change = True

        if change:
            if not notifier().ifconfig_alias(iface, **kwargs):
                return m

        change = False
        kwargs = {'oldip': str(self.instance._original_alias_v6address)}
        if self.instance._original_alias_v6address != \
                self.instance.alias_v6address:
            kwargs['oldip'] = str(self.instance._original_alias_v6address)
            kwargs['newip'] = str(self.instance.alias_v6address)
            change = True

        if self.instance._original_alias_v6netmaskbit != \
                self.instance.alias_v6netmaskbit:
            kwargs['oldnetmask'] = str(
                self.instance._original_alias_v6netmaskbit
            )
            kwargs['newnetmask'] = str(self.instance.alias_v6netmaskbit)
            change = True

        if change:
            if not notifier().ifconfig_alias(iface, **kwargs):
                return m

        if commit:
            m.save()
        return m
