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
import logging

from django.utils.translation import ugettext_lazy as _

from dojango import forms

from freenasUI.common.forms import ModelForm
from freenasUI.common.sipcalc import sipcalc_type
from freenasUI.jails.models import (
    JailsConfiguration,
    Jails,
    JailTemplate,
    NullMountPoint
)
from freenasUI.jails.utils import guess_addresses
from freenasUI.common.warden import (
    Warden,
    WARDEN_FLAGS_NONE,
    WARDEN_TEMPLATE_FLAGS_CREATE,
    WARDEN_TEMPLATE_FLAGS_LIST,
    WARDEN_TEMPLATE_CREATE_FLAGS_TAR,
    WARDEN_TEMPLATE_CREATE_FLAGS_NICK,
    #WARDEN_TEMPLATE_CREATE_FLAGS_LINUX,
    WARDEN_CREATE_FLAGS_TEMPLATE,
    WARDEN_CREATE_FLAGS_32BIT,
    WARDEN_CREATE_FLAGS_VANILLA,
    #WARDEN_CREATE_FLAGS_STARTAUTO,
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
    WARDEN_KEY_HOST,
)
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.system.forms import clean_path_execbit

log = logging.getLogger('jails.forms')


class JailCreateForm(ModelForm):
    jail_type = forms.ChoiceField(
        label=_("type"),
    )

    jail_vanilla = forms.BooleanField(
        label=_("vanilla"),
        required=False,
        initial=True
    )

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
        #FIXME: translate in dojango
        widgets = {
            'jail_defaultrouter_ipv4': forms.widgets.TextInput(),
            'jail_defaultrouter_ipv6': forms.widgets.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        super(JailCreateForm, self).__init__(*args, **kwargs)
        self.logfile = "/var/tmp/warden.log"
        self.statusfile = "/var/tmp/status"
        try:
            os.unlink(self.logfile)
        except:
            pass
        try:
            os.unlink(self.statusfile)
        except:
            pass

        os.environ['EXTRACT_TARBALL_STATUSFILE'] = self.statusfile
        types = ((jt.jt_name, jt.jt_name) for jt in JailTemplate.objects.all())

        self.fields['jail_type'].choices = types
        self.fields['jail_type'].widget.attrs['onChange'] = (
            "jail_type_toggle();"
        )
        self.fields['jail_vnet'].widget.attrs['onChange'] = (
            "jail_vnet_toggle();"
        )
        self.fields['jail_nat'].widget.attrs['onChange'] = (
            "jail_nat_toggle();"
        )

        addrs = guess_addresses()

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
            raise MiddlewareError(e.message)

        if not jc.jc_path:
            raise MiddlewareError(_("No jail root configured."))

        jail_host = self.cleaned_data.get('jail_host')
        jail_ipv4 = self.cleaned_data.get('jail_ipv4')
        jail_ipv6 = self.cleaned_data.get('jail_ipv6')

        jail_flags = WARDEN_FLAGS_NONE
        jail_create_args = {}
        jail_create_args['jail'] = jail_host

        w = Warden()

#        if self.cleaned_data['jail_source']:
#            jail_flags |= WARDEN_CREATE_FLAGS_SRC
#        if self.cleaned_data['jail_ports']:
#            jail_flags |= WARDEN_CREATE_FLAGS_PORTS
        if self.cleaned_data['jail_vanilla']:
            jail_flags |= WARDEN_CREATE_FLAGS_VANILLA

        template_create_args = {}

        jail_type = self.cleaned_data['jail_type']
        template = JailTemplate.objects.get(jt_name=jail_type)
        template_create_args['nick'] = template.jt_name
        template_create_args['tar'] = template.jt_url
        template_create_args['flags'] = WARDEN_TEMPLATE_FLAGS_CREATE | \
            WARDEN_TEMPLATE_CREATE_FLAGS_NICK | \
            WARDEN_TEMPLATE_CREATE_FLAGS_TAR

        saved_template = template
        template = None
        template_list_flags = {}
        template_list_flags['flags'] = WARDEN_TEMPLATE_FLAGS_LIST
        templates = w.template(**template_list_flags)
        for t in templates:
            if t['nick'] == template_create_args['nick']:
                template = t
                break

        createfile = "/var/tmp/.templatecreate"
        if not template:
            try:
                cf = open(createfile, "a+")
                cf.close()
                w.template(**template_create_args)

            except Exception as e:
                self.errors['__all__'] = self.error_class([_(e.message)])
                if os.path.exists(createfile):
                    os.unlink(createfile)
                return

            template_list_flags = {}
            template_list_flags['flags'] = WARDEN_TEMPLATE_FLAGS_LIST
            templates = w.template(**template_list_flags)
            for t in templates:
                if t['nick'] == template_create_args['nick']:
                    template = t
                    break

        if not template:
            self.errors['__all__'] = self.error_class([
                _('Unable to find template!')
            ])
            return

        if template['type'] == 'Linux':
            jail_flags |= WARDEN_CREATE_FLAGS_LINUXJAIL
        if template['arch'] == 'i386':
            jail_flags |= WARDEN_CREATE_FLAGS_32BIT

        jail_flags |= WARDEN_CREATE_FLAGS_TEMPLATE
        jail_create_args['template'] = template_create_args['nick']

        if jail_ipv4:
            jail_flags |= WARDEN_CREATE_FLAGS_IPV4
            jail_create_args['ipv4'] = jail_ipv4

        if jail_ipv6:
            jail_flags |= WARDEN_CREATE_FLAGS_IPV6
            jail_create_args['ipv6'] = jail_ipv6

        jail_flags |= WARDEN_CREATE_FLAGS_LOGFILE
        jail_flags |= WARDEN_CREATE_FLAGS_SYSLOG

        jail_create_args['logfile'] = self.logfile
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

        for key in (
            'jail_bridge_ipv4', 'jail_bridge_ipv6', 'jail_defaultrouter_ipv4',
            'jail_defaultrouter_ipv6', 'jail_mac'
        ):
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
            # XXXX if NOT LINUX XXXX (revisit this)
            if  (saved_template.jt_arch != 'x86' and saved_template.jt_os != 'Linux'):
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
        'jc_ipv6_network_end',
        'jc_collectionurl'
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
                ipv4_start = "%s/%d" % (
                    ipv4_start,
                    st_ipv4_network.network_mask_bits
                )
                if st_ipv4_network.in_network(ipv4_start):
                    cdata['jc_ipv4_network_start'] = ipv4_start

        ipv4_end = cdata.get('jc_ipv4_network_end', None)
        if ipv4_end:
            parts = ipv4_end.split('/')
            ipv4_end = parts[0]
            if st_ipv4_network:
                ipv4_end = "%s/%d" % (
                    ipv4_end,
                    st_ipv4_network.network_mask_bits
                )
                if st_ipv4_network.in_network(ipv4_end):
                    cdata['jc_ipv4_network_end'] = ipv4_end

        ipv6_start = cdata.get('jc_ipv6_network_start', None)
        if ipv6_start:
            parts = ipv6_start.split('/')
            ipv6_start = parts[0]
            if st_ipv6_network:
                ipv6_start = "%s/%d" % (
                    ipv6_start,
                    st_ipv6_network.prefix_length,
                )
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

    def clean_jc_collectionurl(self):
        jc_collectionurl = self.cleaned_data.get("jc_collectionurl")
        if (
            jc_collectionurl and
            not jc_collectionurl.lower().startswith("http") and
            not jc_collectionurl.lower().startswith("ftp")
        ):
            if not os.path.exists(jc_collectionurl):
                raise forms.ValidationError(
                    _("Path does not exist!")
                )

        return jc_collectionurl


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
        #FIXME: translate in dojango
        widgets = {
            'jail_defaultrouter_ipv4': forms.widgets.TextInput(),
            'jail_defaultrouter_ipv6': forms.widgets.TextInput(),
        }

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
                if (
                    not instance.__dict__[okey] and
                    not self.cleaned_data.get(key)
                ):
                    continue
                res = True
                break

        return res

    def __instance_changed_fields(self, instance, keys):
        changed_keys = []

        for key in keys:
            okey = "__original_%s" % key
            if instance.__dict__[okey] != self.cleaned_data.get(key):
                if (
                    not instance.__dict__[okey] and
                    not self.cleaned_data.get(key)
                ):
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

        changed_fields = self.__instance_changed_fields(
            instance, self.__myfields
        )
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


class JailTemplateCreateForm(ModelForm):
    class Meta:
        model = JailTemplate


class JailTemplateEditForm(ModelForm):
    class Meta:
        model = JailTemplate

    def __init__(self, *args, **kwargs):
        super(JailTemplateEditForm, self).__init__(*args, **kwargs)

        obj = self.save(commit=False)
        ninstances = int(obj.jt_instances)
        if ninstances > 0:
            self.fields['jt_name'].widget.attrs['readonly'] = True
            self.fields['jt_arch'].widget.attrs['readonly'] = True
            self.fields['jt_os'].widget.attrs['readonly'] = True
            self.fields['jt_name'].widget.attrs['class'] = (
                'dijitDisabled dijitTextBoxDisabled '
                'dijitValidationTextBoxDisabled'
            )


class NullMountPointForm(ModelForm):

    create = forms.BooleanField(
        label=('Create directory'),
        required=False,
        initial=True,
        help_text=_('Create destination directory if it does not exist'),
    )

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
        create = self.cleaned_data.get("create")
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

        if not os.path.exists(full):
            os.makedirs(full)

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
            self.fields['jail'].widget.attrs['readonly'] = True

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
                raise MiddlewareError(
                    _("The path could not be mounted %(source)s: %(error)s") % {
                        'source': obj.source,
                        'error': e,
                    }
                )
        elif obj.umount():
            #FIXME better error handling, show the user why
            raise MiddlewareError(_("The path could not be umounted %s") % (
                obj.source,
            ))

        return obj
