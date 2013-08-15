#+
# Copyright 2013 iXsystems, Inc.
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
import os
import stat
import logging

from django.utils.translation import ugettext_lazy as _

from dojango import forms

from freenasUI.common.forms import ModelForm
from freenasUI.common.sipcalc import sipcalc_type
from freenasUI.jails.models import (
    JailsConfiguration,
    Jails,
    NullMountPoint
)
from freenasUI.jails.utils import guess_adresses
from freenasUI.common.warden import (
    Warden,
    WardenJail,
    WARDEN_FLAGS_NONE,
    WARDEN_CREATE_FLAGS_32BIT,
    WARDEN_CREATE_FLAGS_SRC,
    WARDEN_CREATE_FLAGS_PORTS,
    WARDEN_CREATE_FLAGS_VANILLA,
    #WARDEN_CREATE_FLAGS_STARTAUTO,
    WARDEN_CREATE_FLAGS_PORTJAIL,
    WARDEN_CREATE_FLAGS_PLUGINJAIL,
    WARDEN_CREATE_FLAGS_LINUXJAIL,
    #WARDEN_CREATE_FLAGS_ARCHIVE,
    #WARDEN_CREATE_FLAGS_LINUXARCHIVE,
    WARDEN_CREATE_FLAGS_IPV4,
    WARDEN_CREATE_FLAGS_IPV6,
    WARDEN_CREATE_FLAGS_SYSLOG,
    WARDEN_CREATE_FLAGS_LOGFILE,
    WARDEN_SET_FLAGS_IPV4,
    WARDEN_SET_FLAGS_IPV6,
    WARDEN_SET_FLAGS_ALIAS_IPV4,
    WARDEN_SET_FLAGS_ALIAS_IPV6,
    WARDEN_SET_FLAGS_BRIDGE_IPV4,
    WARDEN_SET_FLAGS_BRIDGE_IPV6,
    WARDEN_SET_FLAGS_ALIAS_BRIDGE_IPV4,
    WARDEN_SET_FLAGS_ALIAS_BRIDGE_IPV6,
    WARDEN_SET_FLAGS_DEFAULTROUTER_IPV4,
    WARDEN_SET_FLAGS_DEFAULTROUTER_IPV6,
    WARDEN_SET_FLAGS_VNET_ENABLE,
    WARDEN_SET_FLAGS_VNET_DISABLE,
    WARDEN_SET_FLAGS_NAT_ENABLE,
    WARDEN_SET_FLAGS_NAT_DISABLE,
    WARDEN_SET_FLAGS_MAC,
    #WARDEN_SET_FLAGS_FLAGS,
    WARDEN_TYPE_STANDARD,
    WARDEN_TYPE_PLUGINJAIL,
    WARDEN_TYPE_PORTJAIL,
    WARDEN_TYPE_GENTOO_LINUX,
    WARDEN_TYPE_DEBIAN_LINUX,
    WARDEN_TYPE_CENTOS_LINUX,
    WARDEN_GENTOO_LINUXSCRIPT,
    WARDEN_DEBIAN_LINUXSCRIPT,
    WARDEN_CENTOS_LINUXSCRIPT,
    WARDEN_KEY_HOST,
    WARDEN_KEY_STATUS,
    WARDEN_STATUS_RUNNING
)
from freenasUI.middleware.notifier import notifier
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.system.forms import clean_path_execbit

log = logging.getLogger('jails.forms')

def setflags(keys):
    flags = WARDEN_FLAGS_NONE
    for k in keys:
        if k == 'jail_ipv4':
            flags |= WARDEN_SET_FLAGS_IPV4
        elif k == 'jail_ipv6':
            flags |= WARDEN_SET_FLAGS_IPV6
        elif k == 'jail_alias_ipv4':
            flags |= WARDEN_SET_FLAGS_ALIAS_IPV4
        elif k == 'jail_alias_ipv6':
            flags |= WARDEN_SET_FLAGS_ALIAS_IPV6
        elif k == 'jail_bridge_ipv4':
            flags |= WARDEN_SET_FLAGS_BRIDGE_IPV4
        elif k == 'jail_bridge_ipv6':
            flags |= WARDEN_SET_FLAGS_BRIDGE_IPV6
        elif k == 'jail_alias_bridge_ipv4':
            flags |= WARDEN_SET_FLAGS_ALIAS_BRIDGE_IPV4
        elif k == 'jail_alias_bridge_ipv6':
            flags |= WARDEN_SET_FLAGS_ALIAS_BRIDGE_IPV6
        elif k == 'jail_defaultrouter_ipv4':
            flags |= WARDEN_SET_FLAGS_DEFAULTROUTER_IPV4
        elif k == 'jail_defaultrouter_ipv6':
            flags |= WARDEN_SET_FLAGS_DEFAULTROUTER_IPV6
    return flags


class JailCreateForm(ModelForm):
    jail_type = forms.ChoiceField(
        label=_("type"),
        choices=(
            (WARDEN_TYPE_STANDARD, WARDEN_TYPE_STANDARD),
            (WARDEN_TYPE_PLUGINJAIL, WARDEN_TYPE_PLUGINJAIL),
            (WARDEN_TYPE_PORTJAIL, WARDEN_TYPE_PORTJAIL),
            (WARDEN_TYPE_GENTOO_LINUX, WARDEN_TYPE_GENTOO_LINUX),
            (WARDEN_TYPE_DEBIAN_LINUX, WARDEN_TYPE_DEBIAN_LINUX),
            (WARDEN_TYPE_CENTOS_LINUX, WARDEN_TYPE_CENTOS_LINUX)
        ),
        initial=WARDEN_TYPE_STANDARD,
    )

    jail_autostart = forms.BooleanField(
        label=_("autostart"),
        required=False,
        initial=True
    )

    jail_32bit = forms.BooleanField(
        label=_("32 bit"),
        required=False,
        initial=False
    )

#    jail_source = forms.BooleanField(
#        label=_("source"),
#        required=False,
#        initial=False
#    )
#
#    jail_ports = forms.BooleanField(
#        label=_("ports"),
#        required=False,
#        initial=False
#    )

    jail_vanilla = forms.BooleanField(
        label=_("vanilla"),
        required=False,
        initial=True
    )

#    jail_archive = forms.BooleanField(
#        label=_("archive"),
#        required=False,
#        initial=False
#    )

    jail_vnet = forms.BooleanField(
        label=_("VIMAGE"),
        required=False,
        initial=True
    )

    jail_nat = forms.BooleanField(
        label=_("NAT"),
        required=False,
        initial=False
    )

#    jail_script = forms.CharField(
#        label=_("script"),
#        required=False
#    )

#    advanced_fields = [
#        'jail_type',
#        'jail_autostart',
#        'jail_32bit',
#        'jail_source',
#        'jail_ports',
#        'jail_vanilla',
#        'jail_archive',
#        'jail_ipv4',
#        'jail_bridge_ipv4',
#        'jail_defaultrouter_ipv4',
#        'jail_ipv6',
#        'jail_bridge_ipv6',
#        'jail_defaultrouter_ipv6',
#        'jail_mac',
#        'jail_script',
#        'jail_vnet',
#        'jail_nat'
#    ]

    class Meta:
        model = Jails
        exclude = (
            'jail_id',
            'jail_status',
            'jail_alias_ipv4',
            'jail_alias_bridge_ipv4',
            'jail_alias_ipv6',
            'jail_alias_bridge_ipv6'
        )

    def __init__(self, *args, **kwargs):
        super(JailCreateForm, self).__init__(*args, **kwargs)

        self.fields['jail_type'].widget.attrs['onChange'] = (
            "jail_type_toggle();"
        )
        self.fields['jail_32bit'].widget.attrs['onChange'] = (
            "jail_32bit_toggle();"
        )
        self.fields['jail_vnet'].widget.attrs['onChange'] = (
            "jail_vnet_toggle();"
        )
        self.fields['jail_nat'].widget.attrs['onChange'] = (
            "jail_nat_toggle();"
        )

        addrs = guess_adresses()

        if addrs['high_ipv6']:
            self.fields['jail_ipv6'].initial = addrs['high_ipv6']

        if addrs['high_ipv4']:
            self.fields['jail_ipv4'].initial = addrs['high_ipv4']

        if addrs['bridge_ipv4']:
            self.fields['jail_bridge_ipv4'].initial = addrs['bridge_ipv4']

        if addrs['bridge_ipv6']:
            self.fields['jail_bridge_ipv6'].initial = addrs['bridge_ipv6']

    def save(self):
        try:
            jc = JailsConfiguration.objects.order_by("-id")[0]
        except Exception as e:
            self.errors['__all__'] = self.error_class([_(e.message)])
            return

        if not jc.jc_path:
            self.errors['__all__'] = self.error_class(
                ["No jail root configured."]
            )
            return

        jail_host = self.cleaned_data.get('jail_host')
        jail_ipv4 = self.cleaned_data.get('jail_ipv4')
        jail_ipv6 = self.cleaned_data.get('jail_ipv6')

        jail_flags = WARDEN_FLAGS_NONE
        jail_create_args = {}
        jail_create_args['jail'] = jail_host

        w = Warden()

        if self.cleaned_data['jail_32bit']:
            jail_flags |= WARDEN_CREATE_FLAGS_32BIT
#        if self.cleaned_data['jail_source']:
#            jail_flags |= WARDEN_CREATE_FLAGS_SRC
#        if self.cleaned_data['jail_ports']:
#            jail_flags |= WARDEN_CREATE_FLAGS_PORTS
        if self.cleaned_data['jail_vanilla']:
            jail_flags |= WARDEN_CREATE_FLAGS_VANILLA

        if self.cleaned_data['jail_type'] == WARDEN_TYPE_PORTJAIL:
            jail_flags |= WARDEN_CREATE_FLAGS_PORTJAIL
        elif self.cleaned_data['jail_type'] == WARDEN_TYPE_PLUGINJAIL:
            jail_flags |= WARDEN_CREATE_FLAGS_PLUGINJAIL
        elif self.cleaned_data['jail_type'] == WARDEN_TYPE_GENTOO_LINUX:
            jail_flags |= WARDEN_CREATE_FLAGS_GENTOO_LINUX
            jail_create_args['script'] = WARDEN_GENTOO_LINUXSCRIPT
        elif self.cleaned_data['jail_type'] == WARDEN_TYPE_DEBIAN_LINUX:
            jail_flags |= WARDEN_CREATE_FLAGS_DEBIAN_LINUX
            jail_create_args['script'] = WARDEN_DEBIAN_LINUXSCRIPT
        elif self.cleaned_data['jail_type'] == WARDEN_TYPE_CENTOS_LINUX:
            jail_flags |= WARDEN_CREATE_FLAGS_CENTOS_LINUX
            jail_create_args['script'] = WARDEN_CENTOS_LINUXSCRIPT

#        if self.cleaned_data['jail_archive']:
#            if jail_flags & WARDEN_CREATE_FLAGS_LINUXJAIL:
#                jail_flags |= WARDEN_CREATE_FLAGS_LINUXARCHIVE
#            else:
#                jail_flags |= WARDEN_CREATE_FLAGS_ARCHIVE

        if jail_ipv4:
            jail_flags |= WARDEN_CREATE_FLAGS_IPV4
            jail_create_args['ipv4'] = jail_ipv4

        if jail_ipv6:
            jail_flags |= WARDEN_CREATE_FLAGS_IPV6
            jail_create_args['ipv6'] = jail_ipv6

        jail_flags |= WARDEN_CREATE_FLAGS_LOGFILE
        jail_flags |= WARDEN_CREATE_FLAGS_SYSLOG

        logfile = "%s/warden.log" % jc.jc_path
        jail_create_args['logfile'] = logfile

        jail_create_args['flags'] = jail_flags

        createfile = "/var/tmp/.jailcreate"
        try:
            cf = open(createfile, "a+")
            cf.close()
            w.create(**jail_create_args)

        except Exception as e:
            self.errors['__all__'] = self.error_class([_(e.message)])
            if os.path.exists(createfile):
                os.unlink(createfile)
            return

        if os.path.exists(createfile):
            os.unlink(createfile)


        for key in ('jail_bridge_ipv4', 'jail_bridge_ipv6', \
            'jail_defaultrouter_ipv4', 'jail_defaultrouter_ipv6', 'jail_mac'):
            jail_set_args = {}
            jail_set_args['jail'] = jail_host
            jail_flags = WARDEN_FLAGS_NONE
            val = self.cleaned_data.get(key, None)
            if val:
                if key == 'jail_bridge_ipv4':
                    jail_flags |= WARDEN_SET_FLAGS_BRIDGE_IPV4
                    jail_set_args['bridge-ipv4'] = val

                elif key == 'jail_bridge_ipv6':
                    jail_flags |= WARDEN_SET_FLAGS_BRIDGE_IPV6
                    jail_set_args['bridge-ipv6'] = val

                elif key == 'jail_defaultrouter_ipv4':
                    jail_flags |= WARDEN_SET_FLAGS_DEFAULTROUTER_IPV4
                    jail_set_args['defaultrouter-ipv4'] = val

                elif key == 'jail_defaultrouter_ipv6':
                    jail_flags |= WARDEN_SET_FLAGS_DEFAULTROUTER_IPV6
                    jail_set_args['defaultrouter-ipv6'] = val

                elif key == 'jail_mac':
                    jail_flags |= WARDEN_SET_FLAGS_MAC
                    jail_set_args['mac'] = val

                jail_set_args['flags'] = jail_flags
                try:
                    w.set(**jail_set_args)
                except Exception as e:
                    self.errors['__all__'] = self.error_class([_(e.message)])
                    return

        jail_nat = self.cleaned_data.get('jail_nat', None)
        jail_vnet = self.cleaned_data.get('jail_vnet', None)

        jail_set_args = {}
        jail_set_args['jail'] = jail_host
        jail_flags = WARDEN_FLAGS_NONE
        if jail_nat:
            jail_flags |= WARDEN_SET_FLAGS_NAT_ENABLE
        else:
            jail_flags |= WARDEN_SET_FLAGS_NAT_DISABLE

        jail_set_args['flags'] = jail_flags
        try:
            w.set(**jail_set_args)
        except Exception as e:
            self.errors['__all__'] = self.error_class([_(e.message)])
            return

        jail_set_args = {}
        jail_set_args['jail'] = jail_host
        jail_flags = WARDEN_FLAGS_NONE
        if jail_vnet:
            if (
                self.cleaned_data['jail_type'] != WARDEN_TYPE_GENTOO_LINUX
                and
                self.cleaned_data['jail_type'] != WARDEN_TYPE_DEBIAN_LINUX
                and
                self.cleaned_data['jail_type'] != WARDEN_TYPE_CENTOS_LINUX
                and
                not self.cleaned_data['jail_32bit']
            ):
                jail_flags |= WARDEN_SET_FLAGS_VNET_ENABLE
            else:
                jail_flags |= WARDEN_SET_FLAGS_VNET_DISABLE

            jail_set_args['flags'] = jail_flags
            try:
                w.set(**jail_set_args)
            except Exception as e:
                self.errors['__all__'] = self.error_class([_(e.message)])
                return

        if self.cleaned_data['jail_autostart']:
            try:
                w.auto(jail=jail_host)
            except Exception as e:
                self.errors['__all__'] = self.error_class([_(e.message)])
                return

        try:
            w.start(jail=jail_host)
        except Exception as e:
            self.errors['__all__'] = self.error_class([_(e.message)])
            return


class JailsConfigurationForm(ModelForm):

    advanced_fields = [
        'jc_ipv6_network',
        'jc_ipv6_network_start',
        'jc_ipv6_network_end'
    ]

    class Meta:
        model = JailsConfiguration
        widgets = {
            'jc_path': forms.widgets.TextInput(attrs={
                'data-dojo-type': 'freeadmin.form.PathSelector',
            }),
        }

    #
    # Make sure the proper netmask/prefix length get saved
    #
    def clean(self):
        cdata = self.cleaned_data

        st_ipv4_network = None
        network = cdata.get('jc_ipv4_network', None)
        if network:
            st_ipv4_network = sipcalc_type(network)

        st_ipv6_network = None
        network = cdata.get('jc_ipv6_network', None)
        if network:
            st_ipv6_network = sipcalc_type(network)
 
        ipv4_start = cdata.get('jc_ipv4_network_start', None)
        if ipv4_start:
            parts = ipv4_start.split('/')
            ipv4_start = parts[0]
            if st_ipv4_network: 
                ipv4_start = "%s/%d" % (ipv4_start, st_ipv4_network.network_mask_bits)
                if st_ipv4_network.in_network(ipv4_start):
                    cdata['jc_ipv4_network_start'] = ipv4_start

        ipv4_end = cdata.get('jc_ipv4_network_end', None)
        if ipv4_end:
            parts = ipv4_end.split('/')
            ipv4_end = parts[0]
            if st_ipv4_network: 
                ipv4_end = "%s/%d" % (ipv4_end, st_ipv4_network.network_mask_bits)
                if st_ipv4_network.in_network(ipv4_end):
                    cdata['jc_ipv4_network_end'] = ipv4_end

        ipv6_start = cdata.get('jc_ipv6_network_start', None)
        if ipv6_start:
            parts = ipv6_start.split('/')
            ipv6_start = parts[0]
            if st_ipv6_network: 
                ipv6_start = "%s/%d" % (ipv6_start, st_ipv6_network.prefix_length)
                if st_ipv6_network.in_network(ipv6_start):
                    cdata['jc_ipv6_network_start'] = ipv6_start

        ipv6_end = cdata.get('jc_ipv6_network_end', None)
        if ipv6_end:
            parts = ipv6_end.split('/')
            ipv6_end = parts[0]
            if st_ipv6_network: 
                ipv6_end = "%s/%d" % (ipv6_end, st_ipv6_network.prefix_length)
                if st_ipv6_network.in_network(ipv6_end):
                    cdata['jc_ipv6_network_end'] = ipv6_end

        return cdata


class JailsEditForm(ModelForm):

    jail_autostart = forms.BooleanField(label=_("autostart"), required=False)
    jail_vnet = forms.BooleanField(label=_("VIMAGE"), required=False)
    jail_nat = forms.BooleanField(label=_("NAT"), required=False)

    class Meta:
        model = Jails
        exclude = (
            'jail_status',
            'jail_type',
        )

    def __set_ro(self, instance, key):
        self.fields[key].widget.attrs['readonly'] = True
        self.fields[key].widget.attrs['class'] = (
            'dijitDisabled dijitTextBoxDisabled dijitValidationTextBoxDisabled'
        )

    def __instance_save(self, instance, keys):
        for key in keys:
            okey = "__original_%s" % key
            instance.__dict__[okey] = instance.__dict__[key]

    def __instance_diff(self, instance, keys):
        res = False

        for key in keys:
            okey = "__original_%s" % key
            if instance.__dict__[okey] != self.cleaned_data.get(key):
                if not instance.__dict__[okey] and not self.cleaned_data.get(key):
                    continue
                res = True
                break

        return res

    def __instance_changed_fields(self, instance, keys):
        changed_keys = []

        for key in keys:
            okey = "__original_%s" % key
            if instance.__dict__[okey] != self.cleaned_data.get(key):
                if not instance.__dict__[okey] and not self.cleaned_data.get(key):
                    continue
                changed_keys.append(key)

        return changed_keys

    def __init__(self, *args, **kwargs):
        super(JailsEditForm, self).__init__(*args, **kwargs)
        self.__myfields = [
            'jail_autostart',
            'jail_ipv4',
            'jail_alias_ipv4',
            'jail_bridge_ipv4',
            'jail_alias_bridge_ipv4',
            'jail_defaultrouter_ipv4',
            'jail_ipv6',
            'jail_alias_ipv6',
            'jail_bridge_ipv6',
            'jail_alias_bridge_ipv6',
            'jail_defaultrouter_ipv6',
            'jail_mac',
            'jail_vnet',
            'jail_nat',
        ]

        instance = getattr(self, 'instance', None)
        self.__instance_save(instance, self.__myfields)

        self.__set_ro(instance, 'jail_host')

    def save(self):
        jail_host = self.cleaned_data.get('jail_host')

        instance = getattr(self, 'instance', None)
        if self.__instance_diff(instance, self.__myfields):
            self.__instance_changed_fields(instance, self.__myfields)

        changed_fields = self.__instance_changed_fields(instance, self.__myfields)
        for cf in changed_fields:
            if cf == 'jail_autostart':
                Warden().auto(jail=jail_host)
            else:
                args = {}
                flags = WARDEN_FLAGS_NONE

                if cf == 'jail_ipv4':
                    flags |= WARDEN_SET_FLAGS_IPV4
                    args['ipv4'] = self.cleaned_data.get(cf)

                elif cf == 'jail_ipv6':
                    flags |= WARDEN_SET_FLAGS_IPV6
                    args['ipv6'] = self.cleaned_data.get(cf)

                elif cf == 'jail_alias_ipv4':
                    flags |= WARDEN_SET_FLAGS_ALIAS_IPV4
                    args['alias-ipv4'] = self.cleaned_data.get(cf)

                elif cf == 'jail_alias_ipv6':
                    flags |= WARDEN_SET_FLAGS_ALIAS_IPV6
                    args['alias-ipv6'] = self.cleaned_data.get(cf)

                elif cf == 'jail_bridge_ipv4':
                    flags |= WARDEN_SET_FLAGS_BRIDGE_IPV4
                    args['bridge-ipv4'] = self.cleaned_data.get(cf)

                elif cf == 'jail_bridge_ipv6':
                    flags |= WARDEN_SET_FLAGS_BRIDGE_IPV6
                    args['bridge-ipv6'] = self.cleaned_data.get(cf)

                elif cf == 'jail_alias_bridge_ipv4':
                    flags |= WARDEN_SET_FLAGS_ALIAS_BRIDGE_IPV4
                    args['alias-bridge-ipv4'] = self.cleaned_data.get(cf)

                elif cf == 'jail_alias_bridge_ipv6':
                    flags |= WARDEN_SET_FLAGS_ALIAS_BRIDGE_IPV6
                    args['alias-bridge-ipv6'] = self.cleaned_data.get(cf)

                elif cf == 'jail_defaultrouter_ipv4':
                    flags |= WARDEN_SET_FLAGS_DEFAULTROUTER_IPV4
                    args['defaultrouter-ipv4'] = self.cleaned_data.get(cf)

                elif cf == 'jail_defaultrouter_ipv6':
                    flags |= WARDEN_SET_FLAGS_DEFAULTROUTER_IPV6
                    args['defaultrouter-ipv6'] = self.cleaned_data.get(cf)

                elif cf == 'jail_mac':
                    flags |= WARDEN_SET_FLAGS_MAC
                    args['mac'] = self.cleaned_data.get(cf)

                elif cf == 'jail_vnet':
                    if (self.cleaned_data.get(cf)):
                            flags |= WARDEN_SET_FLAGS_VNET_ENABLE
                            args['vnet-enable'] = self.cleaned_data.get(cf)
                    else:
                        flags |= WARDEN_SET_FLAGS_VNET_DISABLE
                        args['vnet-disable'] = self.cleaned_data.get(cf)

                elif cf == 'jail_nat':
                    if self.cleaned_data.get(cf):
                        flags |= WARDEN_SET_FLAGS_NAT_ENABLE
                        args['nat-enable'] = self.cleaned_data.get(cf)
                    else:
                        flags |= WARDEN_SET_FLAGS_NAT_DISABLE
                        args['nat-disable'] = self.cleaned_data.get(cf)

                args['jail'] = jail_host
                args['flags'] = flags

                Warden().set(**args)


class NullMountPointForm(ModelForm):

    mounted = forms.BooleanField(
        label=_("Mounted?"),
        required=False,
        initial=True,
    )

    # Do not remove: used in javascript side
    mpjc_path = forms.CharField(
        required=False
    )

    class Meta:
        model = NullMountPoint
        widgets = {
            'source': forms.widgets.TextInput(attrs={
                'data-dojo-type': 'freeadmin.form.PathSelector',
            }),
            'destination': forms.widgets.TextInput(attrs={
                'data-dojo-type': 'freeadmin.form.PathSelector',
            }),
        }

    def clean_source(self):
        src = self.cleaned_data.get("source")
        src = os.path.abspath(src.strip().replace("..", ""))
        return src

    def clean_destination(self):
        dest = self.cleaned_data.get("destination")
        dest = os.path.abspath(dest.strip().replace("..", ""))

        if not self.jail:
            jail = self.cleaned_data.get("jail")
            if jail:
                self.jail = Jails.objects.get(jail_host=jail)

        if not self.jail:
            raise forms.ValidationError(
                _("This shouldn't happen, but the jail could not be found")
            )

        full = "%s/%s%s" % (self.jc.jc_path, self.jail.jail_host, dest)

        if len(full) > 88:
            raise forms.ValidationError(
                _("The full path cannot exceed 88 characters")
            )
        return dest

    def __init__(self, *args, **kwargs):
        self.jail = None
        if kwargs and 'jail' in kwargs:
            self.jail = kwargs.pop('jail')

        super(NullMountPointForm, self).__init__(*args, **kwargs)

        if kwargs and 'instance' in kwargs:
            self.instance = kwargs.pop('instance')
            if not self.jail:
                self.jail = Jails.objects.filter(
                    jail_host=self.instance.jail
                )[0]

        self.jc = JailsConfiguration.objects.order_by("-id")[0]
        self.fields['jail'] = forms.ChoiceField(
            label=_("Jail"),
            choices=(),
            widget=forms.Select(attrs={'class': 'required'}),
        )
        if self.jail:
            self.fields['jail'].initial = self.jail.jail_host

        try:
            clean_path_execbit(self.jc.jc_path)
        except forms.ValidationError, e:
            self.errors['__all__'] = self.error_class(e.messages)

        pjlist = []
        try:
            wlist = Warden().list()
        except:
            wlist = []

        for wj in wlist:
            pjlist.append(wj[WARDEN_KEY_HOST])

        self.fields['jail'].choices = [(pj, pj) for pj in pjlist]
        self.fields['jail'].widget.attrs['onChange'] = (
            'addStorageJailChange(this);'
        )
        jail_path = "%s/%s" % (self.jc.jc_path, self.jail.jail_host)
        self.fields['destination'].widget.attrs['root'] = jail_path

        self.fields['mpjc_path'].widget = forms.widgets.HiddenInput()
        self.fields['mpjc_path'].initial = self.jc.jc_path

        if self.instance.id:
            self.fields['mounted'].initial = self.instance.mounted
        else:
            self.fields['mounted'].widget = forms.widgets.HiddenInput()

    def save(self, *args, **kwargs):
        obj = super(NullMountPointForm, self).save(*args, **kwargs)
        mounted = self.cleaned_data.get("mounted")
        if mounted == obj.mounted:
            return obj
        if mounted:
            try:
                obj.mount()
            except ValueError, e:
                raise MiddlewareError(_(
                    "The path could not be mounted %s: %s") % (
                        obj.source,
                        e,
                    )
                )
        elif obj.umount():
            #FIXME better error handling, show the user why
            raise MiddlewareError(_("The path could not be umounted %s") % (
                obj.source,
            ))

        return obj
