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
    WARDEN_FLAGS_NONE, WARDEN_CREATE_FLAGS_32BIT, \
    WARDEN_CREATE_FLAGS_SRC, WARDEN_CREATE_FLAGS_PORTS, \
    WARDEN_CREATE_FLAGS_STARTAUTO, WARDEN_CREATE_FLAGS_PORTJAIL, \
    WARDEN_CREATE_FLAGS_PLUGINJAIL, WARDEN_CREATE_FLAGS_LINUXJAIL, \
    WARDEN_CREATE_FLAGS_ARCHIVE, WARDEN_CREATE_FLAGS_LINUXARCHIVE


log = logging.getLogger('jails.forms')

class JailCreateForm(ModelForm):
    jail_type = forms.ChoiceField(label=_("type"))
    jail_autostart = forms.BooleanField(label=_("autostart"), required=False)
    jail_32bit = forms.BooleanField(label=_("32 bit"), required=False)
    jail_source = forms.BooleanField(label=_("source"), required=False)
    jail_ports = forms.BooleanField(label=_("ports"), required=False)
    jail_archive = forms.BooleanField(label=_("archive"), required=False)
    #jail_script = forms.CharField(label=_("script"), required=False)

    advanced_fields = [
        'jail_autostart',
        'jail_32bit',
        'jail_source',
        'jail_ports',
        'jail_archive',
        'jail_ip',
    ]

    class Meta:
        model = models.Jails
        exclude = ('jail_status')

    def __init__(self, *args, **kwargs):
        super(JailCreateForm, self).__init__(*args, **kwargs)
        self.fields['jail_type'].choices = [(t, t) for t in Warden().types()]

        st_ipv4_network = None
        st_ipv6_network = None

        try:
            jc = models.JailsConfiguration.objects.order_by("-id")[0]
            st_ipv4_network = sipcalc_type(jc.jc_ipv4_network)
            st_ipv6_network = sipcalc_type(jc.jc_ipv6_network)

        except:
            pass

        high_ipv4 = None
        high_ipv6 = None

        wlist = Warden().list()
        for wj in wlist:
            wo = WardenJail(**wj)
            st = sipcalc_type(wo.ip)
            
            if st.is_ipv4() and st_ipv4_network is not None:
                if st_ipv4_network.in_network(st):
                    if st > high_ipv4:
                        high_ipv4 = st

            if st.is_ipv6() and st_ipv6_network is not None:
                if st_ipv6_network.in_network(st):
                    if st > high_ipv6:
                        high_ipv6 = st

        if high_ipv4 is None and st_ipv4_network is not None:
            high_ipv4 = sipcalc_type(st_ipv4_network.usable_range[0])

        elif high_ipv4 is not None and st_ipv4_network is not None:
            high_ipv4 += 1
            if not st_ipv4_network.in_network(high_ipv4):
                high_ipv4 = None 

        if high_ipv6 is None and st_ipv6_network is not None:
            high_ipv6 = sipcalc_type(st_ipv6_network .network_range[0])
            high_ipv6 += 1

        elif high_ipv6 is not None and st_ipv6_network is not None:
            high_ipv6 += 1
            if not st_ipv6_network.in_network(high_ipv6):
                high_ipv6 = None 

        if high_ipv6 is not None:
            self.fields['jail_ip'].initial = high_ipv6
        elif high_ipv4 is not None:
            self.fields['jail_ip'].initial = high_ipv4

    def save(self):
        jail_host = self.cleaned_data['jail_host']
        jail_ip = self.cleaned_data['jail_ip']
        jail_flags = WARDEN_FLAGS_NONE

        w = Warden() 

        if self.cleaned_data['jail_autostart']:
            jail_flags |= WARDEN_CREATE_FLAGS_STARTAUTO
        if self.cleaned_data['jail_32bit']:
            jail_flags |= WARDEN_CREATE_FLAGS_32BIT
        if self.cleaned_data['jail_source']:
            jail_flags |= WARDEN_CREATE_FLAGS_SRC
        if self.cleaned_data['jail_ports']:
            jail_flags |= WARDEN_CREATE_FLAGS_PORTS

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

        w.create(jail=jail_host, ip=jail_ip, flags=jail_flags)

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
