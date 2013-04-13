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
import logging

from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI import choices
from freenasUI.common.forms import ModelForm
from freenasUI.common.sipcalc import sipcalc_type
from freenasUI.common.warden import WardenJail

from freenasUI.jails import models
from freenasUI.common.warden import Warden, \
    WARDEN_FLAGS_NONE, \
    WARDEN_CREATE_FLAGS_32BIT, \
    WARDEN_CREATE_FLAGS_SRC, \
    WARDEN_CREATE_FLAGS_PORTS, \
    WARDEN_CREATE_FLAGS_VANILLA, \
    WARDEN_CREATE_FLAGS_STARTAUTO, \
    WARDEN_CREATE_FLAGS_PORTJAIL, \
    WARDEN_CREATE_FLAGS_PLUGINJAIL, \
    WARDEN_CREATE_FLAGS_LINUXJAIL, \
    WARDEN_CREATE_FLAGS_ARCHIVE, \
    WARDEN_CREATE_FLAGS_LINUXARCHIVE, \
    WARDEN_CREATE_FLAGS_IPV4, \
    WARDEN_CREATE_FLAGS_IPV6, \
    WARDEN_SET_FLAGS_BRIDGE_IPV4, \
    WARDEN_SET_FLAGS_BRIDGE_IPV6

log = logging.getLogger('jails.forms')

class JailCreateForm(ModelForm):
    jail_type = forms.ChoiceField(
        label=_("type")
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

    jail_source = forms.BooleanField(
        label=_("source"),
        required=False,
        initial=False
    )

    jail_ports = forms.BooleanField(
        label=_("ports"),
        required=False,
        initial=False
    )

    jail_vanilla = forms.BooleanField(
        label=_("vanilla"),
        required=False,
        initial=True
    )

    jail_archive = forms.BooleanField(
        label=_("archive"),
        required=False,
        initial=False
    )

#    jail_script = forms.CharField(
#        label=_("script"),
#        required=False
#    )

    advanced_fields = [
        'jail_autostart',
        'jail_32bit',
        'jail_source',
        'jail_ports',
        'jail_vanilla',
        'jail_archive',
        'jail_ipv4',
        'jail_bridge_ipv4',
        'jail_ipv6',
        'jail_bridge_ipv6',
    ]

    class Meta:
        model = models.Jails
        exclude = (
            'jail_id',
            'jail_status',
            'jail_alias_ipv4',
            'jail_alias_bridge_ipv4',
            'jail_defaultrouter_ipv4',
            'jail_alias_ipv6',
            'jail_alias_bridge_ipv6',
            'jail_defaultrouter_ipv6'
        )

    def __init__(self, *args, **kwargs):
        super(JailCreateForm, self).__init__(*args, **kwargs)
        self.fields['jail_type'].choices = [(t, t) for t in Warden().types()]

        high_ipv4 = None
        high_ipv6 = None

        st_ipv4_network = None
        st_ipv6_network = None

        try:
            jc = models.JailsConfiguration.objects.order_by("-id")[0]
            st_ipv4_network = sipcalc_type(jc.jc_ipv4_network)
            st_ipv6_network = sipcalc_type(jc.jc_ipv6_network)

        except:
            pass

        #
        # Reserve the first 25 addresses
        #
        if st_ipv4_network is not None: 
            high_ipv4 = sipcalc_type("%s/%d" % (st_ipv4_network.usable_range[0],
                st_ipv4_network.network_mask_bits))
            high_ipv4 += 25 

        if st_ipv6_network is not None: 
            high_ipv6 = sipcalc_type("%s/%d" % (st_ipv6_network .network_range[0],
                st_ipv6_network.prefix_length))
            high_ipv6 += 25 

        wlist = Warden().list()
        for wj in wlist:
            wo = WardenJail(**wj)

            st_ipv4 = None
            st_ipv6 = None

            if wo.ipv4:
                st_ipv4 = sipcalc_type(wo.ipv4)
            if wo.ipv6:
                st_ipv6 = sipcalc_type(wo.ipv6)
            
            if st_ipv4 and st_ipv4_network is not None:
                if st_ipv4_network.in_network(st_ipv4):
                    if st_ipv4 > high_ipv4:
                        high_ipv4 = st_ipv4

            if st_ipv6 and st_ipv6_network is not None:
                if st_ipv6_network.in_network(st_ipv6):
                    if st_ipv6 > high_ipv6:
                        high_ipv6 = st_ipv6

        if high_ipv4 is None and st_ipv4_network is not None:
            high_ipv4 = sipcalc_type("%s/%d" % (st_ipv4_network.usable_range[0],
                st_ipv4_network.network_mask_bits))

        elif high_ipv4 is not None and st_ipv4_network is not None:
            high_ipv4 += 1
            if not st_ipv4_network.in_network(high_ipv4):
                high_ipv4 = None 

        if high_ipv6 is None and st_ipv6_network is not None:
            high_ipv6 = sipcalc_type("%s/%d" % (st_ipv6_network.network_range[0],
                st_ipv6_network.prefix_length))

        elif high_ipv6 is not None and st_ipv6_network is not None:
            high_ipv6 += 1
            if not st_ipv6_network.in_network(high_ipv6):
                high_ipv6 = None 

        if high_ipv6 is not None:
            self.fields['jail_ipv6'].initial = high_ipv6
        elif high_ipv4 is not None:
            self.fields['jail_ipv4'].initial = high_ipv4

        if st_ipv4_network is not None:
            bridge_ipv4 = sipcalc_type("%s/%d" % (st_ipv4_network.usable_range[0],
                st_ipv4_network.network_mask_bits))
            self.fields['jail_bridge_ipv4'].initial = bridge_ipv4

        if st_ipv6_network is not None:
            bridge_ipv6 = sipcalc_type("%s/%d" % (st_ipv6_network.network_range[0],
                st_ipv6_network.prefix_length))
            self.fields['jail_bridge_ipv6'].initial = bridge_ipv6

    def save(self):
        jail_host = self.cleaned_data.get('jail_host')
        jail_ipv4 = self.cleaned_data.get('jail_ipv4')
        jail_ipv6 = self.cleaned_data.get('jail_ipv6')
        jail_flags = WARDEN_FLAGS_NONE

        w = Warden() 

        if self.cleaned_data['jail_32bit']:
            jail_flags |= WARDEN_CREATE_FLAGS_32BIT
        if self.cleaned_data['jail_source']:
            jail_flags |= WARDEN_CREATE_FLAGS_SRC
        if self.cleaned_data['jail_ports']:
            jail_flags |= WARDEN_CREATE_FLAGS_PORTS
        if self.cleaned_data['jail_vanilla']:
            jail_flags |= WARDEN_CREATE_FLAGS_VANILLA

        if self.cleaned_data['jail_type'] == 'portjail':
            jail_flags |= WARDEN_CREATE_FLAGS_PORTJAIL
        elif self.cleaned_data['jail_type'] == 'pluginjail':
            jail_flags |= WARDEN_CREATE_FLAGS_PLUGINJAIL
        elif self.cleaned_data['jail_type'] == 'linuxjail':
            jail_flags |= WARDEN_CREATE_FLAGS_LINUXJAIL

        if self.cleaned_data['jail_archive']:
            if jail_flags & WARDEN_CREATE_FLAGS_LINUXJAIL:
                jail_flags |= WARDEN_CREATE_FLAGS_LINUXARCHIVE
            else:
                jail_flags |= WARDEN_CREATE_FLAGS_ARCHIVE

        jail_create_args = { }
        jail_create_args['jail'] = jail_host

        if jail_ipv4:
            jail_flags |= WARDEN_CREATE_FLAGS_IPV4
            jail_create_args['ipv4'] = jail_ipv4

        if jail_ipv6:
            jail_flags |= WARDEN_CREATE_FLAGS_IPV6
            jail_create_args['ipv6'] = jail_ipv6

        jail_create_args['flags'] = jail_flags
        w.create(**jail_create_args)

        jail_set_args = { }
        jail_set_args['jail'] = jail_host
        jail_flags = WARDEN_FLAGS_NONE

        jail_bridge_ipv4 = self.cleaned_data.get('jail_bridge_ipv4')
        jail_bridge_ipv6 = self.cleaned_data.get('jail_bridge_ipv6')

        if jail_bridge_ipv4:
            jail_flags |= WARDEN_SET_FLAGS_BRIDGE_IPV4
            jail_set_args['bridge-ipv4'] = jail_bridge_ipv4

        if jail_bridge_ipv6:
            jail_flags |= WARDEN_SET_FLAGS_BRIDGE_IPV6
            jail_set_args['bridge-ipv6'] = jail_bridge_ipv6

        jail_set_args['flags'] = jail_flags
        w.set(**jail_set_args)

        if self.cleaned_data['jail_autostart']:
            w.auto(jail=jail_host)

        #w.start(jail=jail_host)

class JailsConfigurationForm(ModelForm):

    class Meta:
        model = models.JailsConfiguration
        widgets = {
            'jc_path': forms.widgets.TextInput(attrs={
                'data-dojo-type': 'freeadmin.form.PathSelector',
                }),
        }

class JailConfigureForm(ModelForm):

    jail_autostart = forms.BooleanField(label=_("autostart"), required=False)
    jail_source = forms.BooleanField(label=_("source"), required=False)
    jail_ports = forms.BooleanField(label=_("ports"), required=False)

    class Meta:
        model = models.Jails

class JailsEditForm(ModelForm):

    jail_autostart = forms.BooleanField(label=_("autostart"), required=False)
#    jail_source = forms.BooleanField(label=_("source"), required=False)
#    jail_ports = forms.BooleanField(label=_("ports"), required=False)

    def __set_ro(self, instance, key):
        if instance and instance.id:
            self.fields[key] = \
                forms.CharField(
                    label=self.fields[key].label,
                    initial=instance.__dict__[key],
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


    def __init__(self, *args, **kwargs):
        super(JailsEditForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        self.__set_ro(instance, 'jail_host')
        self.__set_ro(instance, 'jail_status')
        self.__set_ro(instance, 'jail_type')

    class Meta:
        model = models.Jails
