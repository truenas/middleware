#
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
import os
import re

from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI.common.forms import ModelForm
from freenasUI.freeadmin.forms import SelectMultipleWidget
from freenasUI.freeadmin.utils import key_order
from freenasUI.middleware.client import client
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.middleware.form import MiddlewareModelForm
from freenasUI.services.models import services, NFS
from freenasUI.sharing import models
from freenasUI.storage.widgets import UnixPermissionField
from ipaddr import (IPNetwork, AddressValueError, NetmaskValueError)

log = logging.getLogger('sharing.forms')


class CIFS_ShareForm(MiddlewareModelForm, ModelForm):

    cifs_default_permissions = forms.BooleanField(
        label=_('Apply Default Permissions'),
        help_text=_(
            'Recursively set appropriate default Windows permissions on share'
        ),
        required=False
    )
    middleware_attr_prefix = "cifs_"
    middleware_attr_schema = "cifs"
    middleware_plugin = "sharing.cifs"
    is_singletone = False

    def __init__(self, *args, **kwargs):
        super(CIFS_ShareForm, self).__init__(*args, **kwargs)
        if self.instance.id:
            self.fields['cifs_default_permissions'].initial = False
            self._original_cifs_vfsobjects = self.instance.cifs_vfsobjects
        else:
            self.fields['cifs_default_permissions'].initial = True
            self._original_cifs_vfsobjects = []

        key_order(self, 4, 'cifs_default_permissions', instance=True)

        self.fields['cifs_guestok'].widget.attrs['onChange'] = (
            'javascript:toggleGeneric("id_cifs_guestok", '
            '["id_cifs_guestonly"], true);')
        if self.data:
            if self.data.get('cifs_guestok') is False:
                self.fields['cifs_guestonly'].widget.attrs['disabled'] = \
                    'disabled'
        elif self.instance.cifs_guestok is False:
            self.fields['cifs_guestonly'].widget.attrs['disabled'] = 'disabled'
        self.fields['cifs_name'].required = False
        self.fields['cifs_home'].widget.attrs['onChange'] = (
            "cifs_storage_task_toggle();"
        )

        if self.instance:
            task_dict = {}
            if self.instance.cifs_path:
                with client as c:
                    task_dict = c.call('sharing.cifs.get_storage_tasks',
                                       self.instance.cifs_path)

            elif self.instance.cifs_home:
                with client as c:
                    task_dict = c.call('sharing.cifs.get_storage_tasks',
                                        None, self.instance.cifs_home)

            if task_dict:
                choices = [('', '-----')]
                for task_id, msg in task_dict.items():
                    choices.append((task_id, msg))
                self.fields['cifs_storage_task'].choices = choices

            else:
                self.fields['cifs_storage_task'].choices = (('', '-----'),)

    class Meta:
        fields = '__all__'
        model = models.CIFS_Share

    def middleware_clean(self, data):
        data['hostsallow'] = data['hostsallow'].split()
        data['hostsdeny'] = data['hostsdeny'].split()

        if not data['storage_task']:
            data.pop('storage_task')

        return data

    def done(self, request, events):
        if not services.objects.get(srv_service='cifs').srv_enable:
            events.append('ask_service("cifs")')
        super(CIFS_ShareForm, self).done(request, events)


class AFP_ShareForm(MiddlewareModelForm, ModelForm):
    middleware_attr_prefix = "afp_"
    middleware_attr_schema = "afp"
    middleware_plugin = "sharing.afp"
    is_singletone = False

    class Meta:
        fields = '__all__'
        model = models.AFP_Share

    def __init__(self, *args, **kwargs):
        super(AFP_ShareForm, self).__init__(*args, **kwargs)
        self.fields['afp_upriv'].widget.attrs['onChange'] = (
            'javascript:toggleGeneric("id_afp_upriv", ["id_afp_fperm", '
            '"id_afp_dperm", "id_afp_umask"], true);')
        self.fields['afp_fperm'] = UnixPermissionField(
            label=self.fields['afp_fperm'].label,
            initial=self.fields['afp_fperm'].initial,
            required=False,
        )
        self.fields['afp_dperm'] = UnixPermissionField(
            label=self.fields['afp_dperm'].label,
            initial=self.fields['afp_dperm'].initial,
            required=False,
        )
        if self.instance.id:
            if not self.instance.afp_upriv:
                self.fields['afp_fperm'].widget.attrs['disabled'] = 'true'
                self.fields['afp_dperm'].widget.attrs['disabled'] = 'true'
                self.fields['afp_umask'].widget.attrs['disabled'] = 'true'
            else:
                self.fields['afp_fperm'].widget.attrs['disabled'] = 'false'
                self.fields['afp_dperm'].widget.attrs['disabled'] = 'false'
                self.fields['afp_umask'].widget.attrs['disabled'] = 'false'
        self.fields['afp_name'].required = False

    def middleware_clean(self, data):
        data['allow'] = data['allow'].split()
        data['deny'] = data['deny'].split()
        data['ro'] = data['ro'].split()
        data['rw'] = data['rw'].split()
        data['hostsallow'] = data['hostsallow'].split()
        data['hostsdeny'] = data['hostsdeny'].split()

        return data

    def done(self, request, events):
        if not services.objects.get(srv_service='afp').srv_enable:
            events.append('ask_service("afp")')
        super(AFP_ShareForm, self).done(request, events)


class NFS_ShareForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.NFS_Share
        widgets = {
            'nfs_security': SelectMultipleWidget(sorter=True),
        }

    def __init__(self, *args, **kwargs):
        super(NFS_ShareForm, self).__init__(*args, **kwargs)
        try:
            nfs = NFS.objects.order_by('-id')[0]
        except IndexError:
            nfs = NFS.objects.create()
        if not nfs.nfs_srv_v4:
            del self.fields['nfs_security']

    def clean_nfs_network(self):
        net = self.cleaned_data['nfs_network']
        net = re.sub(r'\s{2,}|\n', ' ', net).strip()
        if not net:
            return net
        seen_networks = []
        for n in net.split(' '):
            try:
                netobj = IPNetwork(n)
                if n.find("/") == -1:
                    raise ValueError(n)
                for i in seen_networks:
                    if netobj.overlaps(i):
                        raise forms.ValidationError(
                            _('The following networks overlap: %(net1)s - %(net2)s') % {
                                'net1': netobj,
                                'net2': i,
                            }
                        )
                seen_networks.append(netobj)
            except (AddressValueError, NetmaskValueError, ValueError):
                raise forms.ValidationError(
                    _("This is not a valid network: %s") % n
                )
        return net

    def clean_nfs_hosts(self):
        net = self.cleaned_data['nfs_hosts']
        net = re.sub(r'\s{2,}|\n', ' ', net).strip()
        return net
        if not net:
            return net
        # only one address = CIDR or IP
        # if net.find(" ") == -1:
        #    try:
        #    except NetmaskValueError:
        #        IPAddress(net.encode('utf-8'))
        #    except (AddressValueError, ValueError):
        #        raise forms.ValidationError(
        #            )

    def clean(self):
        cdata = self.cleaned_data
        for field in (
            'nfs_maproot_user', 'nfs_maproot_group',
            'nfs_mapall_user', 'nfs_mapall_group'
        ):
            if cdata.get(field, None) in ('', '-----'):
                cdata[field] = None

        if (
            cdata.get('nfs_maproot_group', None) is not None
            and
            cdata.get('nfs_maproot_user', None) is None
        ):
            self._errors['nfs_maproot_group'] = self.error_class([
                _("Maproot group requires Maproot user"),
            ])
        if (
            cdata.get('nfs_mapall_group', None) is not None
            and
            cdata.get('nfs_mapall_user', None) is None
        ):
            self._errors['nfs_mapall_group'] = self.error_class([
                _("Mapall group requires Mapall user"),
            ])
        if (
            cdata.get('nfs_maproot_user', None) is not None
            or
            cdata.get('nfs_maproot_group', None) is not None
        ):
            if cdata.get('nfs_mapall_user', None) is not None:
                self._errors['nfs_mapall_user'] = self.error_class([
                    _("Maproot user/group disqualifies Mapall"),
                ])
                del cdata['nfs_mapall_user']
            if cdata.get('nfs_mapall_group', None) is not None:
                self._errors['nfs_mapall_group'] = self.error_class([
                    _("Maproot user/group disqualifies Mapall"),
                ])
                del cdata['nfs_mapall_group']

        return cdata

    def cleanformset_nfs_share_path(self, formset, forms):
        dev = None
        valid = True
        ismp = False
        for form in forms:
            if not hasattr(form, "cleaned_data"):
                continue
            path = form.cleaned_data.get("path")
            if not path:
                continue
            parent = os.path.join(path, "..")
            try:
                stat = os.stat(path.encode("utf8"))
                if dev is None:
                    dev = stat.st_dev
                elif dev != stat.st_dev:
                    self._fserrors = self.error_class([
                        _("Paths for a NFS share must reside within the same "
                            "filesystem")
                    ])
                    valid = False
                    break
                if os.stat(parent.encode("utf8")).st_dev != stat.st_dev:
                    ismp = True
                if ismp and len(forms) > 1:
                    self._fserrors = self.error_class([
                        _("You cannot share a mount point and subdirectories "
                            "all at once")
                    ])
                    valid = False
                    break

            except OSError:
                pass

        if not ismp and self.cleaned_data.get('nfs_alldirs'):
            self._errors['nfs_alldirs'] = self.error_class([_(
                "This option can only be used for datasets."
            )])
            valid = False

        networks = self.cleaned_data.get("nfs_network", "")
        if not networks:
            networks = ['0.0.0.0/0']
        else:
            networks = networks.split(" ")

        qs = models.NFS_Share.objects.all()
        if self.instance.id:
            qs = qs.exclude(id=self.instance.id)

        used_networks = []
        for share in qs:
            try:
                stdev = os.stat(share.paths.all()[0].path.encode("utf8")).st_dev
            except:
                continue
            if share.nfs_network:
                used_networks.extend(
                    [(y, stdev) for y in share.nfs_network.split(" ")]
                )
            else:
                used_networks.append(('0.0.0.0/0', stdev))
            if (self.cleaned_data.get("nfs_alldirs") and share.nfs_alldirs
                    and stdev == dev):
                self._errors['nfs_alldirs'] = self.error_class([
                    _("This option is only available once per mountpoint")
                ])
                valid = False
                break

        for network in networks:
            networkobj = IPNetwork(network)
            for unetwork, ustdev in used_networks:
                try:
                    unetworkobj = IPNetwork(unetwork)
                except Exception:
                    # If for some reason other values in db are not valid networks
                    unetworkobj = IPNetwork('0.0.0.0/0')
                if networkobj.overlaps(unetworkobj) and dev == ustdev:
                    self._errors['nfs_network'] = self.error_class([
                        _("The network %s is already being shared and cannot "
                            "be used twice for the same filesystem") % (
                                network,
                            )
                    ])
                    valid = False
                    break

        return valid

    def is_valid(self, formsets):
        paths = formsets.get("formset_nfs_share_path")['instance']
        valid = False
        for form in paths:
            if (
                form.cleaned_data.get("path")
                and
                not form.cleaned_data.get("DELETE")
            ):
                valid = True
                break
        if not valid:
            paths._non_form_errors = self.error_class([
                _("You need at least one path for the share"),
            ])
            return valid
        return super(NFS_ShareForm, self).is_valid(formsets)

    def done(self, request, events):
        notifier().reload("nfs")
        if not services.objects.get(srv_service='nfs').srv_enable:
            events.append('ask_service("nfs")')
        super(NFS_ShareForm, self).done(request, events)


class NFS_SharePathForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.NFS_Share_Path

    def clean_path(self):
        path = self.cleaned_data.get('path')
        if path and ' ' in path:
            raise forms.ValidationError(_(
                'Whitespace is not a valid character for NFS shares.'
            ))
        return path

    def save(self, *args, **kwargs):
        path = self.cleaned_data.get('path').encode('utf8')
        if path and not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError as e:
                raise MiddlewareError(_(
                    'Failed to create %(path)s: %(error)s' % {
                        'path': path,
                        'error': e,
                    }
                ))
        return super(NFS_SharePathForm, self).save(*args, **kwargs)


class WebDAV_ShareForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.WebDAV_Share

    def clean(self):
        cdata = self.cleaned_data
        if not cdata.get("webdav_name"):
            cdata['webdav_name'] = self.instance.webdav_name
        davname = self.cleaned_data.get("webdav_name")
        if not davname.isalnum():
            raise forms.ValidationError(_(
                'Only AlphaNumeric characters are allowed.'
            ))
        return cdata

    def save(self):
        ret = super(WebDAV_ShareForm, self).save()
        notifier().reload("webdav")
        return ret

    def done(self, request, events):
        if not services.objects.get(srv_service='webdav').srv_enable:
            events.append('ask_service("webdav")')
        super(WebDAV_ShareForm, self).done(request, events)
