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
import sys
import stat
import logging

from django.utils.translation import ugettext_lazy as _

from dojango import forms

from freenasUI import choices
from freenasUI.common.forms import ModelForm, Form
from freenasUI.common.sipcalc import sipcalc_type
from freenasUI.common.warden import WardenJail, Warden
from freenasUI.freeadmin.models import Model
from freenasUI.jails.models import (
    JailsConfiguration,
    Jails,
    NullMountPoint,
    Mkdir
)
from freenasUI.common.warden import (
    Warden,
    WARDEN_FLAGS_NONE,
    WARDEN_CREATE_FLAGS_32BIT,
    WARDEN_CREATE_FLAGS_SRC,
    WARDEN_CREATE_FLAGS_PORTS,
    WARDEN_CREATE_FLAGS_VANILLA,
    WARDEN_CREATE_FLAGS_STARTAUTO,
    WARDEN_CREATE_FLAGS_PORTJAIL,
    WARDEN_CREATE_FLAGS_PLUGINJAIL,
    WARDEN_CREATE_FLAGS_LINUXJAIL,
    WARDEN_CREATE_FLAGS_ARCHIVE,
    WARDEN_CREATE_FLAGS_LINUXARCHIVE,
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
    WARDEN_SET_FLAGS_FLAGS,
    WARDEN_TYPE_STANDARD,
    WARDEN_TYPE_PLUGINJAIL, 
    WARDEN_TYPE_PORTJAIL,
    WARDEN_TYPE_LINUXJAIL,
    WARDEN_KEY_HOST,
    WARDEN_KEY_STATUS,
    WARDEN_STATUS_RUNNING
)

from freenasUI.system.forms import (
    clean_path_execbit, clean_path_locked, FileWizard
)


LINUXSCRIPT = "/usr/local/share/warden/linux-installs/gentoo-stage3-i486"

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
        label=_("type")
    )

    jail_autostart = forms.BooleanField(
        label=_("autostart"),
        required=False,
        initial=True
    )

#    jail_32bit = forms.BooleanField(
#        label=_("32 bit"),
#        required=False,
#        initial=False
#    )

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

    jail_vnet = forms.BooleanField(
        label=_("vnet"),
        required=False,
        initial=True
    )

#    jail_script = forms.CharField(
#        label=_("script"),
#        required=False
#    )

    advanced_fields = [
        'jail_type',
        'jail_autostart',
        'jail_source',
        'jail_ports',
        'jail_vanilla',
        'jail_archive',
        'jail_ipv4',
        'jail_bridge_ipv4',
        'jail_ipv6',
        'jail_bridge_ipv6',
        'jail_script',
        'jail_vnet'
    ]

    class Meta:
        model = Jails
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
        self.fields['jail_type'].choices = (
            (WARDEN_TYPE_PLUGINJAIL, WARDEN_TYPE_PLUGINJAIL),
            (WARDEN_TYPE_STANDARD, WARDEN_TYPE_STANDARD),
            (WARDEN_TYPE_PORTJAIL, WARDEN_TYPE_PORTJAIL),
#            (WARDEN_TYPE_LINUXJAIL, WARDEN_TYPE_LINUXJAIL)
        )

        high_ipv4 = None
        high_ipv6 = None

        st_ipv4_network = None
        st_ipv6_network = None

        try:
            jc = JailsConfiguration.objects.order_by("-id")[0]
            st_ipv4_network = sipcalc_type(jc.jc_ipv4_network)
            st_ipv6_network = sipcalc_type(jc.jc_ipv6_network)

        except:
            pass

        logfile = "%s/warden.log" % jc.jc_path
        if os.path.exists(logfile):
            os.unlink(logfile)

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

        try:
            wlist = Warden().list()
        except:
            wlist = []

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
        try:
            jc = JailsConfiguration.objects.order_by("-id")[0]
        except Exception as e:
            self.errors['__all__'] = self.error_class([_(e.message)])
            return

        if not jc.jc_path:
           self.errors['__all__'] = self.error_class(["No jail root configured."])
           return

        jail_host = self.cleaned_data.get('jail_host')
        jail_ipv4 = self.cleaned_data.get('jail_ipv4')
        jail_ipv6 = self.cleaned_data.get('jail_ipv6')

        jail_flags = WARDEN_FLAGS_NONE
        jail_create_args = { }
        jail_create_args['jail'] = jail_host

        w = Warden() 

#        if self.cleaned_data['jail_32bit']:
#            jail_flags |= WARDEN_CREATE_FLAGS_32BIT
        if self.cleaned_data['jail_source']:
            jail_flags |= WARDEN_CREATE_FLAGS_SRC
        if self.cleaned_data['jail_ports']:
            jail_flags |= WARDEN_CREATE_FLAGS_PORTS
        if self.cleaned_data['jail_vanilla']:
            jail_flags |= WARDEN_CREATE_FLAGS_VANILLA

        if self.cleaned_data['jail_type'] == WARDEN_TYPE_PORTJAIL:
            jail_flags |= WARDEN_CREATE_FLAGS_PORTJAIL
        elif self.cleaned_data['jail_type'] == WARDEN_TYPE_PLUGINJAIL:
            jail_flags |= WARDEN_CREATE_FLAGS_PLUGINJAIL
        elif self.cleaned_data['jail_type'] == WARDEN_TYPE_LINUXJAIL:
            jail_flags |= WARDEN_CREATE_FLAGS_LINUXJAIL
            jail_create_args['script'] = LINUXSCRIPT

        if self.cleaned_data['jail_archive']:
            if jail_flags & WARDEN_CREATE_FLAGS_LINUXJAIL:
                jail_flags |= WARDEN_CREATE_FLAGS_LINUXARCHIVE
            else:
                jail_flags |= WARDEN_CREATE_FLAGS_ARCHIVE

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

        jail_bridge_ipv4 = self.cleaned_data.get('jail_bridge_ipv4')
        jail_bridge_ipv6 = self.cleaned_data.get('jail_bridge_ipv6')
        jail_vnet = self.cleaned_data.get('jail_vnet')

        jail_set_args = { }
        jail_set_args['jail'] = jail_host
        jail_flags = WARDEN_FLAGS_NONE
        if jail_bridge_ipv4:
            jail_flags |= WARDEN_SET_FLAGS_BRIDGE_IPV4
            jail_set_args['bridge-ipv4'] = jail_bridge_ipv4
            jail_set_args['flags'] = jail_flags
            try:
                w.set(**jail_set_args)
            except Exception as e:
                self.errors['__all__'] = self.error_class([_(e.message)])
                return

        jail_set_args = { }
        jail_set_args['jail'] = jail_host
        jail_flags = WARDEN_FLAGS_NONE
        if jail_bridge_ipv6:
            jail_flags |= WARDEN_SET_FLAGS_BRIDGE_IPV6
            jail_set_args['bridge-ipv6'] = jail_bridge_ipv6
            jail_set_args['flags'] = jail_flags
            try:
                w.set(**jail_set_args)
            except Exception as e:
                self.errors['__all__'] = self.error_class([_(e.message)])
                return

        jail_set_args = { }
        jail_set_args['jail'] = jail_host
        jail_flags = WARDEN_FLAGS_NONE
        if jail_vnet:
            jail_flags |= WARDEN_SET_FLAGS_VNET_ENABLE
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

    class Meta:
        model = JailsConfiguration
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
        model = Jails

class JailsEditForm(ModelForm):

    jail_autostart = forms.BooleanField(label=_("autostart"), required=False)
    jail_vnet = forms.BooleanField(label=_("vnet"), required=False)

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
                                'dijitValidationTextBoxDisabled'
                            ),
                        },
                    )
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
            'jail_vnet' 
        ]

        instance = getattr(self, 'instance', None)
        self.__instance_save(instance, self.__myfields)

        self.__set_ro(instance, 'jail_host')
        self.__set_ro(instance, 'jail_status')
        self.__set_ro(instance, 'jail_type')

    def save(self):
        jail_host = self.cleaned_data.get('jail_host')

        instance = getattr(self, 'instance', None)
        if self.__instance_diff(instance, self.__myfields):
            keys = self.__instance_changed_fields(instance, self.__myfields)

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

                elif cf == 'jail_vnet':
                    if self.cleaned_data.get(cf): 
                        flags |= WARDEN_SET_FLAGS_VNET_ENABLE
                    else: 
                        flags |= WARDEN_SET_FLAGS_VNET_DISABLE
                    args['vnet-enable'] = self.cleaned_data.get(cf)

                args['jail'] = jail_host
                args['flags'] = flags

                Warden().set(**args)

    class Meta:
        model = Jails


class NullMountPointForm(ModelForm):

    mounted = forms.BooleanField(
        label=_("Mounted?"),
        required=False,
        initial=True,
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

        full = "%s/%s%s" % (self.jc.jc_path, self.jail.jail_host, dest)

        if len(full) > 88:
            raise forms.ValidationError(
                _("The full path cannot exceed 88 characters")
                )
        return dest

    def __init__(self, *args, **kwargs):
        self.jail = None
        if kwargs and kwargs.has_key('jail'):
            self.jail = kwargs.pop('jail') 

        super(NullMountPointForm, self).__init__(*args, **kwargs)

        if kwargs and kwargs.has_key('instance'):
            self.instance = kwargs.pop('instance') 

        if self.jail:
            self.fields['jail'].initial = self.jail.jail_host
            self.fields['jail'].widget.attrs = {
                'readonly': True,
                'class': (
                    'dijitDisabled dijitTextBoxDisabled'
                    'dijitValidationTextBoxDisabled' 
                ),
            }

            self.jc = JailsConfiguration.objects.order_by("-id")[0]
            jail_path = "%s/%s" % (self.jc.jc_path, self.jail.jail_host)

            self.fields['destination'].widget.attrs['root'] = (jail_path)

        else:
            self.fields['jail'] = forms.ChoiceField(
                label=_("Jail"),
                choices=(),
                widget=forms.Select(attrs={'class': 'required'}),
            )

            jc = JailsConfiguration.objects.order_by("-id")[0]
            try:
                clean_path_execbit(jc.jc_path)
            except forms.ValidationError, e:
                self.errors['__all__'] = self.error_class(e.messages)

            pjlist = []
            try:
                wlist = Warden().list()
            except:
                wlist = []

            for wj in wlist:
                if wj[WARDEN_KEY_STATUS] == WARDEN_STATUS_RUNNING:
                    pjlist.append(wj[WARDEN_KEY_HOST])

            self.fields['jail'].choices = [(pj, pj) for pj in pjlist ]

        if self.instance.id:
            self.fields['mounted'].initial = self.instance.mounted
        else:
            self.fields['mounted'].widget = forms.widgets.HiddenInput()



    def save(self, *args, **kwargs):
        obj = super(NullMountPointForm, self).save(*args, **kwargs)
        mounted = self.cleaned_data.get("mounted")
        if mounted == obj.mounted:
            return obj
        if mounted and not obj.mount():
            #FIXME better error handling, show the user why
            raise MiddlewareError(_("The path could not be mounted %s") % (
                obj.source,
                ))
        if not mounted and not obj.umount():
            #FIXME better error handling, show the user why
            raise MiddlewareError(_("The path could not be umounted %s") % (
                obj.source,
                ))

        return obj


class MkdirForm(ModelForm):

    class Meta:
       model = Mkdir
       widgets = {
            'path': forms.widgets.TextInput(attrs={
                'data-dojo-type': 'freeadmin.form.PathSelector',
                }),
            'directory': forms.widgets.TextInput(attrs={
                'data-dojo-type': 'freeadmin.form.PathSelector',
                }),
        }

    def __init__(self, *args, **kwargs):
        self.jail = None
        if kwargs and kwargs.has_key('jail'):
            self.jail = kwargs.pop('jail') 

        super(MkdirForm, self).__init__(*args, **kwargs)

        if self.jail:
            self.jc = JailsConfiguration.objects.order_by("-id")[0]
            jail_path = "%s/%s" % (self.jc.jc_path, self.jail.jail_host)

            self.fields['path'].widget.attrs['root'] = (jail_path)
            self.fields['jail'].initial = self.jail.jail_host
            self.fields['jail'].widget.attrs = {
                'readonly': True,
                'class': (
                    'dijitDisabled dijitTextBoxDisabled'
                    'dijitValidationTextBoxDisabled' 
                ),
            }

        else:
            self.fields['jail'] = forms.ChoiceField(
                label=_("Jail"),
                choices=(),
                widget=forms.Select(attrs={'class': 'required'}),
            )

            pjlist = []
            try:
                wlist = Warden().list()
            except:
                wlist = []

            for wj in wlist:
                if wj[WARDEN_KEY_STATUS] == WARDEN_STATUS_RUNNING:
                    pjlist.append(wj[WARDEN_KEY_HOST])

            self.fields['jail'].choices = [(pj, pj) for pj in pjlist ]

    def clean_jail(self):
        jail = self.cleaned_data.get('jail')

        if not jail:
            raise forms.ValidationError(_("Jail not specified."))

        return jail

    def clean_path(self):
        path = self.cleaned_data.get('path')
        jail = self.cleaned_data.get('jail')

        self.jc = JailsConfiguration.objects.order_by("-id")[0]
        jail_path = "%s/%s" % (self.jc.jc_path, jail)

        if not path:
            raise forms.ValidationError(_("Path not specified."))
        if not path.startswith(jail_path):
            raise forms.ValidationError(_("Path must be a jail path."))
        if not os.access(path, 0):
            raise forms.ValidationError(_("Path does not exist."))
        st = os.stat(path)
        if not stat.S_ISDIR(st.st_mode):
            raise forms.ValidationError(_("Path is not a directory."))

        path = os.path.abspath(path.strip().replace("..", ""))

        return path

    def clean_directory(self):
        directory = self.cleaned_data.get('directory')

        if not directory:
            raise forms.ValidationError(_("Directory not specified."))

        return directory

    def save(self):
        path = self.cleaned_data.get('path')
        directory = self.cleaned_data.get('directory')

        newdir = "%s/%s" % (path, directory)
        ret = True

        try:
            os.makedirs(newdir, mode=0755)

        except Exception, e:
            self._errors['__all__'] = self.error_class([_(e)])
            ret = False

        return ret
