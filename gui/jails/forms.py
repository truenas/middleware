# +
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
import platform
import re
import logging
import random
import shutil

from django.utils.translation import ugettext_lazy as _

from dojango import forms

from freenasUI import choices
from freenasUI.common.forms import ModelForm
from freenasUI.common.sipcalc import sipcalc_type
from freenasUI.jails.models import (
    JailsConfiguration,
    Jails,
    JailTemplate,
    JailMountPoint
)
from freenasUI.jails.utils import (
    guess_ipv4_addresses,
    guess_ipv6_addresses,
    jail_path_configured,
    jail_auto_configure,
    add_media_user_and_group
)
from freenasUI.common.warden import (
    Warden,
    WARDEN_FLAGS_NONE,
    WARDEN_TEMPLATE_FLAGS_CREATE,
    WARDEN_TEMPLATE_FLAGS_LIST,
    WARDEN_TEMPLATE_CREATE_FLAGS_TAR,
    WARDEN_TEMPLATE_CREATE_FLAGS_NICK,
    # WARDEN_TEMPLATE_CREATE_FLAGS_LINUX,
    WARDEN_TEMPLATE_CREATE_FLAGS_MTREE,
    WARDEN_CREATE_FLAGS_TEMPLATE,
    WARDEN_CREATE_FLAGS_32BIT,
    WARDEN_CREATE_FLAGS_VANILLA,
    # WARDEN_CREATE_FLAGS_STARTAUTO,
    WARDEN_CREATE_FLAGS_LINUXJAIL,
    # WARDEN_CREATE_FLAGS_ARCHIVE,
    # WARDEN_CREATE_FLAGS_LINUXARCHIVE,
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
    WARDEN_SET_FLAGS_IFACE,
    WARDEN_SET_FLAGS_FLAGS,
    WARDEN_KEY_HOST,
)
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.storage.models import Volume
from freenasUI.system.forms import clean_path_execbit
from freenasUI.sharing.models import (
    CIFS_Share,
    AFP_Share,
    NFS_Share_Path,
    WebDAV_Share,
)
from freenasUI.services.models import iSCSITargetExtent

log = logging.getLogger('jails.forms')


class JailCreateForm(ModelForm):
    jail_type = forms.ChoiceField(
        label=_("Template"),
        required=False
    )
    jail_ipv4_dhcp = forms.BooleanField(
        label=_("IPv4 DHCP"),
        required=False
    )
    jail_ipv6_autoconf = forms.BooleanField(
        label=_("IPv6 Autoconfigure"),
        required=False
    )

    class Meta:
        model = Jails
        fields = [
            'jail_host',
            'jail_type',
            'jail_ipv4_dhcp',
            'jail_ipv4',
            'jail_ipv4_netmask',
            'jail_bridge_ipv4',
            'jail_bridge_ipv4_netmask',
            'jail_defaultrouter_ipv4',
            'jail_ipv6_autoconf',
            'jail_ipv6',
            'jail_ipv6_prefix',
            'jail_bridge_ipv6',
            'jail_bridge_ipv6_prefix',
            'jail_defaultrouter_ipv6',
            'jail_mac',
            'jail_iface',
            'jail_flags',
            'jail_autostart',
            'jail_vnet',
            'jail_nat'
        ]

        # FIXME: translate in dojango
        widgets = {
            'jail_defaultrouter_ipv4': forms.widgets.TextInput(),
            'jail_defaultrouter_ipv6': forms.widgets.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        super(JailCreateForm, self).__init__(*args, **kwargs)

        if not jail_path_configured():
            jail_auto_configure()

        try:
            self.jc = JailsConfiguration.objects.order_by("-id")[0]
        except Exception as e:
            raise MiddlewareError(e)

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

        arch = platform.architecture()
        if arch[0] == '64bit':
            arch = 'x64'
        else:
            arch = 'x86'
        self.arch = arch

        os.environ['EXTRACT_TARBALL_STATUSFILE'] = self.statusfile
        self.fields['jail_type'].choices = choices.JAIL_TEMPLATE_CHOICES()
        self.fields['jail_type'].widget.attrs['onChange'] = (
            "jail_type_toggle();"
        )
        self.fields['jail_vnet'].widget.attrs['onChange'] = (
            "jail_vnet_toggle();"
        )
        self.fields['jail_nat'].widget.attrs['onChange'] = (
            "jail_nat_toggle();"
        )
        self.fields['jail_ipv4_dhcp'].widget.attrs['onChange'] = (
            "jail_ipv4_dhcp_toggle();"
        )
        self.fields['jail_ipv6_autoconf'].widget.attrs['onChange'] = (
            "jail_ipv6_autoconf_toggle();"
        )

        if not self.jc.jc_ipv4_dhcp:
            ipv4_addrs = guess_ipv4_addresses()
            if ipv4_addrs['high_ipv4']:
                parts = str(ipv4_addrs['high_ipv4']).split('/')
                self.fields['jail_ipv4'].initial = parts[0]
                if len(parts) > 1:
                    self.fields['jail_ipv4_netmask'].initial = parts[1]

            if ipv4_addrs['bridge_ipv4']:
                parts = str(ipv4_addrs['bridge_ipv4']).split('/')
                self.fields['jail_bridge_ipv4'].initial = parts[0]
                if len(parts) > 1:
                    self.fields['jail_bridge_ipv4_netmask'].initial = parts[1]
        else:
            self.fields['jail_ipv4_dhcp'].initial = True

        if not self.jc.jc_ipv6_autoconf:
            ipv6_addrs = guess_ipv6_addresses()
            if ipv6_addrs['high_ipv6']:
                parts = str(ipv6_addrs['high_ipv6']).split('/')
                self.fields['jail_ipv6'].initial = parts[0]
                if len(parts) > 1:
                    self.fields['jail_ipv6_prefix'].initial = parts[1]

            if ipv6_addrs['bridge_ipv6']:
                parts = str(ipv6_addrs['bridge_ipv6']).split('/')
                self.fields['jail_bridge_ipv6'].initial = parts[0]
                if len(parts) > 1:
                    self.fields['jail_bridge_ipv6_prefix'].initial = parts[1]
        else:
            self.fields['jail_ipv6_autoconf'].initial = True

    #
    # Allow dashes in the name
    #
    # https://bugs.freenas.org/issues/16009
    #
    def clean_jail_host(self):
        jail_host = self.cleaned_data.get('jail_host')
        if not re.search(r'^[A-Za-z0-9_-]+$', jail_host):
            raise forms.ValidationError(_(
                "Valid characters for jail names are letters, numbers, dashes,"
                " or underscores."
            ))
        return jail_host

    def clean_jail_mac(self):
        jail_mac = self.cleaned_data.get('jail_mac')
        if is_jail_mac_duplicate(jail_mac):
            raise forms.ValidationError(_(
                "You have entered an existing MAC Address."
                "Please enter a new one."
            ))
        return jail_mac

    def clean(self):
        jail_ipv4_dhcp = self.cleaned_data.get('jail_ipv4_dhcp')
        jail_ipv4 = self.cleaned_data.get('jail_ipv4')

        if jail_ipv4_dhcp and not jail_ipv4.startswith('DHCP'):
            self._errors["jail_ipv4_dhcp"] = self.error_class(
                [_("You can either enter dhcp or static ip but not both")]
            )
        return self.cleaned_data

    def save(self):
        jc = self.jc

        if not jc.jc_path:
            raise MiddlewareError(_("No jail root configured."))

        jc_ipv4_netmask = 24
        if jc.jc_ipv4_network:
            parts = jc.jc_ipv4_network.split('/')
            if len(parts) > 1:
                jc_ipv4_netmask = parts[1]

        jc_ipv6_prefix = 64
        if jc.jc_ipv6_network:
            parts = jc.jc_ipv6_network.split('/')
            if len(parts) > 1:
                jc_ipv6_prefix = parts[1]

        jail_host = self.cleaned_data.get('jail_host')
        jail_ipv4_dhcp = self.cleaned_data.get('jail_ipv4_dhcp')
        jail_ipv4 = self.cleaned_data.get('jail_ipv4')
        jail_ipv4_netmask = self.cleaned_data.get('jail_ipv4_netmask',
                                                  jc_ipv4_netmask)

        jail_ipv6_autoconf = self.cleaned_data.get('jail_ipv6_autoconf')
        jail_ipv6 = self.cleaned_data.get('jail_ipv6')
        jail_ipv6_prefix = self.cleaned_data.get('jail_ipv6_prefix',
                                                 jc_ipv6_prefix)

        jail_flags = WARDEN_FLAGS_NONE
        jail_flags |= WARDEN_CREATE_FLAGS_VANILLA

        jail_create_args = {}
        jail_create_args['jail'] = jail_host

        w = Warden()

        template_create_args = {}
        jail_type = self.cleaned_data['jail_type']
        if not jail_type:
            jail_type = 'standard'
        template = JailTemplate.objects.get(jt_name=jail_type)
        template_create_args['nick'] = template.jt_name
        template_create_args['tar'] = template.jt_url
        template_create_args['flags'] = WARDEN_TEMPLATE_FLAGS_CREATE | \
            WARDEN_TEMPLATE_CREATE_FLAGS_NICK | \
            WARDEN_TEMPLATE_CREATE_FLAGS_TAR
        if template.jt_mtree:
            template_create_args['mtree'] = template.jt_mtree
            template_create_args['flags'] = template_create_args['flags'] | \
                WARDEN_TEMPLATE_CREATE_FLAGS_MTREE

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

            # If for some reason warden does not list the template but the path
            # exists, we shall try to nuke it
            template_path = '{}/.warden-template-{}'.format(self.jc.jc_path, jail_type)
            if os.path.exists(template_path):
                try:
                    notifier().destroy_zfs_dataset(template_path.replace('/mnt/', ''))
                except:
                    pass
                try:
                    shutil.rmtree(template_path)
                except OSError:
                    pass

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
        if template['arch'] == 'i386' and self.arch == 'x64':
            jail_flags |= WARDEN_CREATE_FLAGS_32BIT

        jail_flags |= WARDEN_CREATE_FLAGS_TEMPLATE
        jail_create_args['template'] = template_create_args['nick']

        if jail_ipv4_dhcp:
            jail_ipv4 = "DHCP"

        if jail_ipv4:
            if jail_ipv4 != "DHCP":
                jail_ipv4 = "%s/%s" % (jail_ipv4, jail_ipv4_netmask)

            jail_flags |= WARDEN_CREATE_FLAGS_IPV4
            jail_create_args['ipv4'] = jail_ipv4

        if jail_ipv6_autoconf:
            jail_ipv6 = "AUTOCONF"

        if jail_ipv6:
            if jail_ipv6 != "AUTOCONF":
                jail_ipv6 = "%s/%s" % (jail_ipv6, jail_ipv6_prefix)

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

        for key in ('jail_bridge_ipv4', 'jail_bridge_ipv6',
                    'jail_defaultrouter_ipv4', 'jail_defaultrouter_ipv6',
                    'jail_mac', 'jail_iface', 'jail_flags'):
            jail_set_args = {}
            jail_set_args['jail'] = jail_host
            jail_flags = WARDEN_FLAGS_NONE
            val = self.cleaned_data.get(key, None)
            if val:
                if key == 'jail_bridge_ipv4':
                    mask = self.cleaned_data.get('jail_bridge_ipv4_netmask',
                                                 jc_ipv4_netmask)
                    jail_flags |= WARDEN_SET_FLAGS_BRIDGE_IPV4
                    jail_set_args['bridge-ipv4'] = "%s/%s" % (val, mask)

                elif key == 'jail_bridge_ipv6':
                    prefix = self.cleaned_data.get('jail_bridge_ipv6_prefix',
                                                   jc_ipv6_prefix)
                    jail_flags |= WARDEN_SET_FLAGS_BRIDGE_IPV6
                    jail_set_args['bridge-ipv6'] = "%s/%s" % (val, prefix)

                elif key == 'jail_defaultrouter_ipv4':
                    jail_flags |= WARDEN_SET_FLAGS_DEFAULTROUTER_IPV4
                    jail_set_args['defaultrouter-ipv4'] = val

                elif key == 'jail_defaultrouter_ipv6':
                    jail_flags |= WARDEN_SET_FLAGS_DEFAULTROUTER_IPV6
                    jail_set_args['defaultrouter-ipv6'] = val

                elif key == 'jail_mac':
                    jail_flags |= WARDEN_SET_FLAGS_MAC
                    jail_set_args['mac'] = val

                elif key == 'jail_iface':
                    jail_flags |= WARDEN_SET_FLAGS_IFACE
                    jail_set_args['iface'] = val

                elif key == 'jail_flags':
                    jail_flags |= WARDEN_SET_FLAGS_FLAGS
                    jail_set_args['jflags'] = val

            elif key == 'jail_mac':
                jail_mac_list = [jail.jail_mac for jail in Jails.objects.all()]
                mac_address = generate_randomMAC()
                while mac_address in jail_mac_list:
                    mac_address = generate_randomMAC()

                jail_flags |= WARDEN_SET_FLAGS_MAC
                jail_set_args['mac'] = mac_address

            jail_set_args['flags'] = jail_flags
            try:
                w.set(**jail_set_args)
            except Exception as e:
                self.errors['__all__'] = self.error_class([_(e.message)])
                return

        jail_nat = self.cleaned_data.get('jail_nat', None)
        jail_vnet = self.cleaned_data.get('jail_vnet', None)
        if jc.jc_ipv4_dhcp or jc.jc_ipv6_autoconf:
            jail_vnet = True

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
            if (saved_template.jt_arch != 'x86' and
                    saved_template.jt_os != 'Linux'):
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

        # Requery instance so we have everything up-to-date after save
        # See #14686
        self.instance = Jails.objects.get(jail_host=jail_host)
        if self.instance:
            add_media_user_and_group(self.instance.jail_path)


def is_jail_root_shared(jail_root):
    paths = [c.cifs_path for c in CIFS_Share.objects.all()]
    paths.extend([a.afp_path for a in AFP_Share.objects.all()])
    paths.extend([n.path for n in NFS_Share_Path.objects.all()])
    paths.extend([w.webdav_path for w in WebDAV_Share.objects.all()])
    extents = iSCSITargetExtent.objects.filter(iscsi_target_extent_type='File')
    for e in extents:
        if os.path.realpath(jail_root) in os.path.realpath(e.iscsi_target_extent_path.rpartition('/')[0]):
            paths.append(jail_root)

    for path in paths:
        if jail_root.startswith(path):
            return True
    return False


def is_jail_mac_duplicate(mac):
    jail_macs = [jail.jail_mac for jail in Jails.objects.all()]
    return mac in jail_macs


def generate_randomMAC():
    local_list = [0x02, 0x06, 0x0a, 0x0e]
    first_byte = random.randint(0x00, 0x0f)
    first = first_byte << 4
    first = first | random.choice(local_list)
    val = [first, random.randint(0x00, 0xff), random.randint(0x00, 0xff), random.randint(0x00, 0xff), random.randint(0x00, 0xff), random.randint(0x00, 0xff)]
    mac_address = ':'.join(map(lambda x: "%02x" % x, val))
    return mac_address


class JailsConfigurationForm(ModelForm):

    advanced_fields = [
        'jc_ipv4_network',
        'jc_ipv4_network_start',
        'jc_ipv4_network_end',
        'jc_ipv6_network',
        'jc_ipv6_network_start',
        'jc_ipv6_network_end',
        'jc_collectionurl'
    ]

    class Meta:
        fields = '__all__'
        model = JailsConfiguration
        widgets = {
            'jc_path': forms.widgets.TextInput(attrs={
                'data-dojo-type': 'freeadmin.form.PathSelector',
            }),
        }

    def __init__(self, *args, **kwargs):
        super(JailsConfigurationForm, self).__init__(*args, **kwargs)

        self.fields['jc_ipv4_dhcp'].widget.attrs['onChange'] = (
            "jc_ipv4_dhcp_toggle();"
        )
        self.fields['jc_ipv6_autoconf'].widget.attrs['onChange'] = (
            "jc_ipv6_autoconf_toggle();"
        )

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

    def clean_jc_path(self):
        jc_path = self.cleaned_data.get('jc_path').rstrip('/')

        if is_jail_root_shared(jc_path):
            raise forms.ValidationError(
                _("Jail dataset created on a share")
            )

        jc_fpath = jc_path
        if not jc_fpath.endswith('/'):
            jc_fpath = jc_fpath + '/'

        in_volume = False
        for v in Volume.objects.all():
            fp = '/mnt/%s/' % v.vol_name
            if jc_fpath.startswith(fp):
                in_volume = True
                break

        if not in_volume:
            raise forms.ValidationError(
                _("Jail root must be on a volume or dataset!")
            )

        if not os.path.exists(jc_path):
            raise forms.ValidationError(
                _("Jail root does not exist!")
            )

        return jc_path


class JailsEditForm(ModelForm):
    jail_autostart = forms.BooleanField(
        label=_("autostart"),
        required=False
    )
    jail_vnet = forms.BooleanField(
        label=_("VIMAGE"),
        required=False
    )
    jail_nat = forms.BooleanField(
        label=_("NAT"),
        required=False
    )
    jail_ipv4_dhcp = forms.BooleanField(
        label=_("IPv4 DHCP"),
        required=False
    )
    jail_ipv6_autoconf = forms.BooleanField(
        label=_("IPv6 Autoconfigure"),
        required=False
    )

    advanced_fields = [
        'jail_type',
        'jail_ipv4_dhcp',
        'jail_ipv4_netmask',
        'jail_alias_ipv4',
        'jail_bridge_ipv4',
        'jail_bridge_ipv4_netmask',
        'jail_alias_bridge_ipv4',
        'jail_defaultrouter_ipv4',
        'jail_ipv6_autoconf',
        'jail_ipv6_prefix',
        'jail_alias_ipv6',
        'jail_bridge_ipv6',
        'jail_bridge_ipv6_prefix',
        'jail_alias_bridge_ipv6',
        'jail_defaultrouter_ipv6',
        'jail_mac',
        'jail_iface',
        'jail_flags',
        'jail_autostart',
        'jail_status',
        'jail_vnet',
        'jail_nat'
    ]

    class Meta:
        model = Jails
        fields = [
            'jail_host',
            'jail_type',
            'jail_ipv4_dhcp',
            'jail_ipv4',
            'jail_ipv4_netmask',
            'jail_alias_ipv4',
            'jail_bridge_ipv4',
            'jail_bridge_ipv4_netmask',
            'jail_alias_bridge_ipv4',
            'jail_defaultrouter_ipv4',
            'jail_ipv6_autoconf',
            'jail_ipv6',
            'jail_ipv6_prefix',
            'jail_alias_ipv6',
            'jail_bridge_ipv6',
            'jail_bridge_ipv6_prefix',
            'jail_alias_bridge_ipv6',
            'jail_defaultrouter_ipv6',
            'jail_mac',
            'jail_iface',
            'jail_flags',
            'jail_autostart',
            'jail_status',
            'jail_vnet',
            'jail_nat'
        ]
        exclude = ['jail_status']
        # FIXME: translate in dojango
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
            'jail_ipv4_netmask',
            'jail_alias_ipv4',
            'jail_bridge_ipv4',
            'jail_bridge_ipv4_netmask',
            'jail_alias_bridge_ipv4',
            'jail_defaultrouter_ipv4',
            'jail_ipv6',
            'jail_ipv6_prefix',
            'jail_alias_ipv6',
            'jail_bridge_ipv6',
            'jail_bridge_ipv6_prefix',
            'jail_alias_bridge_ipv6',
            'jail_defaultrouter_ipv6',
            'jail_mac',
            'jail_iface',
            'jail_vnet',
            'jail_nat',
            'jail_flags',
        ]
        try:
            self.jc = JailsConfiguration.objects.order_by("-id")[0]
        except Exception as e:
            raise MiddlewareError(e.message)

        jail_ipv4_dhcp = False
        jail_ipv6_autoconf = False

        if self.jc.jc_ipv4_dhcp:
            jail_ipv4_dhcp = True
        if self.jc.jc_ipv6_autoconf:
            jail_ipv6_autoconf = True

        if self.instance:
            if (self.instance.jail_ipv4 and
                    self.instance.jail_ipv4.startswith("DHCP")):
                jail_ipv4_dhcp = True
            if (self.instance.jail_ipv6 and
                    self.instance.jail_ipv6.startswith("AUTOCONF")):
                jail_ipv6_autoconf = True

        self.fields['jail_ipv4_dhcp'].initial = jail_ipv4_dhcp
        self.fields['jail_ipv6_autoconf'].initial = jail_ipv6_autoconf

        if self._api and self.instance and self.instance.id:
            self.instance = Jails.objects.get(id=self.instance.id)
        instance = getattr(self, 'instance', None)
        self.__instance_save(instance, self.__myfields)

        self.fields['jail_vnet'].widget.attrs['onChange'] = (
            "jail_vnet_toggle();"
        )
        self.fields['jail_nat'].widget.attrs['onChange'] = (
            "jail_nat_toggle();"
        )
        self.fields['jail_ipv4_dhcp'].widget.attrs['onChange'] = (
            "jail_ipv4_dhcp_toggle();"
        )
        self.fields['jail_ipv6_autoconf'].widget.attrs['onChange'] = (
            "jail_ipv6_autoconf_toggle();"
        )

        self.__set_ro(instance, 'jail_host')
        self.__set_ro(instance, 'jail_type')

    def clean_jail_mac(self):
        jail_mac = self.cleaned_data.get('jail_mac')
        curr_host = self.cleaned_data.get('jail_host')
        jail = Jails.objects.get(jail_host=curr_host)
        if jail_mac != jail.jail_mac:
            if is_jail_mac_duplicate(jail_mac):
                raise forms.ValidationError(_(
                    "You have entered an existing MAC Address."
                    "Please enter a new one."
                ))
        return jail_mac

    def save(self):
        jail_host = self.cleaned_data.get('jail_host')

        instance = getattr(self, 'instance', None)
        if self.__instance_diff(instance, self.__myfields):
            self.__instance_changed_fields(instance, self.__myfields)

        changed_fields = self.__instance_changed_fields(
            instance, self.__myfields
        )

        try:
            jc = JailsConfiguration.objects.order_by("-id")[0]
        except Exception as e:
            raise MiddlewareError(e.message)

        if not jc.jc_path:
            raise MiddlewareError(_("No jail root configured."))

        jc_ipv4_netmask = 24
        if jc.jc_ipv4_network:
            parts = jc.jc_ipv4_network.split('/')
            if len(parts) > 1:
                jc_ipv4_netmask = parts[1]

        jc_ipv6_prefix = 64
        if jc.jc_ipv6_network:
            parts = jc.jc_ipv6_network.split('/')
            if len(parts) > 1:
                jc_ipv6_prefix = parts[1]

        jail_ipv4_dhcp = self.cleaned_data.get('jail_ipv4_dhcp', False)
        jail_ipv6_autoconf = self.cleaned_data.get('jail_ipv6_autoconf', False)

        for cf in changed_fields:
            if cf == 'jail_autostart':
                Warden().auto(jail=jail_host)
            else:
                args = {}
                flags = WARDEN_FLAGS_NONE

                if cf == 'jail_ipv4' or cf == 'jail_ipv4_netmask':
                    ipv4 = self.cleaned_data.get('jail_ipv4')
                    mask = self.cleaned_data.get('jail_ipv4_netmask',
                                                 jc_ipv4_netmask)
                    if jail_ipv4_dhcp:
                        jail_ipv4 = ipv4
                    else:
                        jail_ipv4 = "%s/%s" % (ipv4, mask)

                    flags |= WARDEN_SET_FLAGS_IPV4
                    args['ipv4'] = jail_ipv4

                elif cf == 'jail_ipv6' or cf == 'jail_ipv6_prefix':
                    ipv6 = self.cleaned_data.get('jail_ipv6')
                    prefix = self.cleaned_data.get('jail_ipv6_prefix',
                                                   jc_ipv6_prefix)
                    if jail_ipv6_autoconf:
                        jail_ipv6 = ipv6
                    else:
                        jail_ipv6 = "%s/%s" % (ipv6, prefix)

                    flags |= WARDEN_SET_FLAGS_IPV6
                    args['ipv6'] = jail_ipv6

                elif cf == 'jail_alias_ipv4':
                    flags |= WARDEN_SET_FLAGS_ALIAS_IPV4
                    args['alias-ipv4'] = self.cleaned_data.get(cf)

                elif cf == 'jail_alias_ipv6':
                    flags |= WARDEN_SET_FLAGS_ALIAS_IPV6
                    args['alias-ipv6'] = self.cleaned_data.get(cf)

                elif (cf == 'jail_bridge_ipv4' or
                      cf == 'jail_bridge_ipv4_netmask'):
                    bridge_ipv4 = self.cleaned_data.get('jail_bridge_ipv4')
                    mask = self.cleaned_data.get('jail_bridge_ipv4_netmask',
                                                 jc_ipv4_netmask)
                    jail_bridge_ipv4 = "%s/%s" % (bridge_ipv4, mask)

                    flags |= WARDEN_SET_FLAGS_BRIDGE_IPV4
                    args['bridge-ipv4'] = jail_bridge_ipv4

                elif (cf == 'jail_bridge_ipv6' or
                      cf == 'jail_bridge_ipv6_prefix'):
                    bridge_ipv6 = self.cleaned_data.get('jail_bridge_ipv6')
                    prefix = self.cleaned_data.get('jail_bridge_ipv6_prefix',
                                                   jc_ipv6_prefix)
                    jail_bridge_ipv6 = "%s/%s" % (bridge_ipv6, prefix)

                    flags |= WARDEN_SET_FLAGS_BRIDGE_IPV6
                    args['bridge-ipv6'] = jail_bridge_ipv6

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

                elif cf == 'jail_iface':
                    flags |= WARDEN_SET_FLAGS_IFACE
                    args['iface'] = self.cleaned_data.get(cf)

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

                elif cf == 'jail_flags':
                    flags |= WARDEN_SET_FLAGS_FLAGS
                    args['jflags'] = self.cleaned_data.get(cf)

                args['jail'] = jail_host
                args['flags'] = flags

                Warden().set(**args)


class JailTemplateCreateForm(ModelForm):

    class Meta:
        fields = '__all__'
        exclude = ['jt_system']
        model = JailTemplate

    def clean_jt_name(self):
        jt_name = self.cleaned_data.get('jt_name')
        if not jt_name:
            return jt_name
        qs = JailTemplate.objects.filter(jt_name=jt_name)
        if qs.exists():
            raise forms.ValidationError(_('This name is already in use.'))
        return jt_name


class JailTemplateEditForm(ModelForm):

    class Meta:
        fields = '__all__'
        exclude = ['jt_system', 'jt_readonly']
        model = JailTemplate

    def __ro(self, field):
        self.fields[field].widget.attrs['readOnly'] = True
        self.fields[field].widget.attrs['class'] = (
            'dijitDisabled dijitTextBoxDisabled '
            'dijitValidationTextBoxDisabled'
        )

    def __init__(self, *args, **kwargs):
        super(JailTemplateEditForm, self).__init__(*args, **kwargs)

        if not self.instance.id:
            self.fields['jt_os'].widget.attrs['onChange'] = (
                'jailtemplate_os(this);'
            )
        else:
            ninstances = int(self.instance.jt_instances)
            if ninstances > 0:
                self.__ro('jt_name')
                self.__ro('jt_arch')
                self.__ro('jt_os')

            else:
                self.fields['jt_os'].widget.attrs['onChange'] = (
                    'jailtemplate_os(this);'
                )
            if self.instance.jt_os == 'Linux':
                self.__ro('jt_arch')

            if self.instance.jt_readonly is True:
                self.__ro('jt_name')
                self.__ro('jt_arch')
                self.__ro('jt_os')
                self.__ro('jt_url')
                self.__ro('jt_mtree')


class JailMountPointForm(ModelForm):

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
        fields = '__all__'
        model = JailMountPoint
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
        if not re.search(r'^/[a-zA-Z0-9][a-zA-Z0-9_/\-:. ]*$', dest):
            raise forms.ValidationError(_(
                "Destination must begin with an "
                "alphanumeric character and may only contain "
                "\"-\", \"_\", \":\", \" \" and \".\"."))

        if not self.jail:
            jail = self.cleaned_data.get("jail")
            if jail:
                self.jail = Jails.objects.get(jail_host=jail)

        if not self.jail:
            raise forms.ValidationError(
                _("This shouldn't happen, but the jail could not be found")
            )

        self._full = "%s/%s%s" % (self.jc.jc_path, self.jail.jail_host, dest)

        if len(self._full) > 88:
            raise forms.ValidationError(
                _("The full path cannot exceed 88 characters")
            )

        return dest

    def __init__(self, *args, **kwargs):
        self.jail = None
        if kwargs and 'jail' in kwargs:
            self.jail = kwargs.pop('jail')

        super(JailMountPointForm, self).__init__(*args, **kwargs)

        self._full = None

        if kwargs and 'instance' in kwargs:
            self.instance = kwargs.pop('instance')
            if not self.jail and self.instance.id:
                try:
                    self.jail = Jails.objects.filter(
                        jail_host=self.instance.jail
                    )[0]
                except:
                    pass

        self.jc = JailsConfiguration.objects.order_by("-id")[0]
        self.fields['jail'] = forms.ChoiceField(
            label=_("Jail"),
            choices=(),
            widget=forms.Select(attrs={'class': 'required'}),
        )
        if self.jail:
            self.fields['jail'].initial = self.jail.jail_host
            self.fields['jail'].widget.attrs['readonly'] = True
            jail_path = "%s/%s" % (self.jc.jc_path, self.jail.jail_host)
            self.fields['destination'].widget.attrs['root'] = jail_path

        try:
            clean_path_execbit(self.jc.jc_path)
        except forms.ValidationError, e:
            self.errors['__all__'] = self.error_class(e.messages)

        pjlist = []
        try:
            wlist = Warden().cached_list()
        except:
            wlist = []

        for wj in wlist:
            pjlist.append(wj[WARDEN_KEY_HOST])

        self.fields['jail'].choices = [('', '')] + [(pj, pj) for pj in pjlist]
        self.fields['jail'].widget.attrs['onChange'] = (
            'addStorageJailChange(this);'
        )

        self.fields['mpjc_path'].widget = forms.widgets.HiddenInput()
        self.fields['mpjc_path'].initial = self.jc.jc_path

        if self.instance.id:
            self.fields['mounted'].initial = self.instance.mounted
        else:
            self.fields['mounted'].widget = forms.widgets.HiddenInput()

    def delete(self, events=None):
        super(JailMountPointForm, self).delete(events)

        p = os.popen(". /etc/rc.freenas; jail_update_fstab '%s';" %
                     self.instance.jail)
        p.close()

    def save(self, *args, **kwargs):
        obj = super(JailMountPointForm, self).save(*args, **kwargs)
        create = self.cleaned_data.get('create')
        if self._full and not os.path.exists(self._full) and create:
            os.makedirs(self._full)

        p = os.popen(". /etc/rc.freenas; jail_update_fstab '%s';" %
                     self.cleaned_data.get('jail'))
        p.close()

        mounted = self.cleaned_data.get("mounted")
        if mounted == obj.mounted:
            return obj
        if mounted:
            try:
                obj.mount()
            except ValueError, e:
                raise MiddlewareError(
                    _("The path could not be mounted %(source)s: %(error)s") %
                    {
                        'source': obj.source,
                        'error': e,
                    }
                )
        else:
            try:
                obj.umount()
            except ValueError, e:
                raise MiddlewareError(_(
                    "The path could not be umounted %(source)s: %(error)s" % {
                        'source': obj.source,
                        'error': e,
                    }
                ))

        return obj
