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
import os
import re

from django.db.models import Q
from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI import choices
from freenasUI.common.forms import ModelForm
from freenasUI.freeadmin.forms import SelectMultipleWidget, SelectMultipleField
from freenasUI.middleware.connector import connection as dispatcher
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.common.pipesubr import pipeopen
from freenasUI.services.models import services
from freenasUI.sharing import models
from freenasUI.storage.models import Task
from freenasUI.storage.widgets import UnixPermissionField
from ipaddr import (
    IPAddress, IPNetwork, AddressValueError, NetmaskValueError
)

log = logging.getLogger('sharing.forms')


class CIFS_ShareForm(ModelForm):
    cifs_hostsallow = forms.CharField(
        label=_("Hosts Allow"),
        help_text=_("This option is a comma, space, or tab delimited set of hosts which are permitted to access this share. You can specify the hosts by name or IP number. Leave this field empty to use default settings."),
        required=False
    )

    cifs_hostsdeny = forms.CharField(
        label=_("Hosts Deny"),
        help_text=_("This option is a comma, space, or tab delimited set of host which are NOT permitted to access this share. Where the lists conflict, the allow list takes precedence. In the event that it is necessary to deny all by default, use the keyword ALL (or the netmask 0.0.0.0/0) and then explicitly specify to the hosts allow parameter those hosts that should be permitted access. Leave this field empty to use default settings."),
        required=False
    )
    cifs_vfsobjects = SelectMultipleField(
        label=_('VFS Objects'),
        choices=list(choices.CIFS_VFS_OBJECTS())
    )

    """
    def _get_storage_tasks(self, cifs_path=None, cifs_home=False):
        p = pipeopen("zfs list -H -o mountpoint,name")
        zfsout = p.communicate()[0].split('\n')
        if p.returncode != 0:
            zfsout = []

        task_list = []
        if cifs_path:
            for line in zfsout:
                try:
                    tasks = []
                    zfs_mp, zfs_ds = line.split()
                    if cifs_path == zfs_mp or cifs_path.startswith("%s/" % zfs_mp):
                        if cifs_path == zfs_mp:
                            tasks = Task.objects.filter(task_filesystem=zfs_ds)
                        else:
                            tasks = Task.objects.filter(Q(task_filesystem=zfs_ds) & Q(task_recursive=True))
                    for t in tasks:
                        task_list.append(t)

                except:
                    pass

        elif cifs_home:
            task_list = Task.objects.filter(Q(task_recursive=True))

        return task_list
    """

    def __init__(self, *args, **kwargs):
        super(CIFS_ShareForm, self).__init__(*args, **kwargs)
        self.fields['cifs_vfsobjects'].initial = ['aio_pthread', 'streams_xattr']
        self.fields['cifs_guestok'].widget.attrs['onChange'] = (
            'javascript:toggleGeneric("id_cifs_guestok", '
            '["id_cifs_guestonly"], true);')
        if self.data:
            if self.data.get('cifs_guestok') is False:
                self.fields['cifs_guestonly'].widget.attrs['disabled'] = \
                    'disabled'
        elif self.instance.cifs_guestok is False:
            self.fields['cifs_guestonly'].widget.attrs['disabled'] = 'disabled'
        self.fields['cifs_home'].widget.attrs['onChange'] = (
            "cifs_storage_task_toggle();"
        )

        """
        if self.instance:
            task_list = []
            if self.instance.cifs_path:
                task_list = self._get_storage_tasks(cifs_path=self.instance.cifs_path)

            elif self.instance.cifs_home:
                task_list = self._get_storage_tasks(cifs_home=self.instance.cifs_home)

            if task_list:
                choices = [('', '-----')]
                for task in task_list:
                    choices.append((task.id, task))
                self.fields['cifs_storage_task'].choices = choices

            else:
                self.fields['cifs_storage_task'].choices = (('', '-----'),)
        """

    class Meta:
        fields = '__all__'
        exclude = ['id']
        model = models.CIFS_Share

    def clean_cifs_home(self):
        home = self.cleaned_data.get('cifs_home')
        if home:
            qs = models.CIFS_Share.objects.filter(cifs_home=True)
            if self.instance.id:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                raise forms.ValidationError(_(
                    'Only one share is allowed to be a home share.'
                ))
        return home

    def clean_cifs_name(self):
        name = self.cleaned_data.get('cifs_name')
        path = self.cleaned_data.get('cifs_path')
        if path and not name:
            name = path.rsplit('/', 1)[-1]
        return name

    def clean_cifs_hostsallow(self):
        net = self.cleaned_data.get("cifs_hostsallow")
        net = re.sub(r'\s{2,}|\n', ' ', net).strip()
        return net

    def clean_cifs_hostsdeny(self):
        net = self.cleaned_data.get("cifs_hostsdeny")
        net = re.sub(r'\s{2,}|\n', ' ', net).strip()
        return net

    def clean(self):
        path = self.cleaned_data.get('cifs_path')
        home = self.cleaned_data.get('cifs_home')

        if not home and not path:
            self._errors['cifs_path'] = self.error_class([
                _('This field is required.')
            ])

        return self.cleaned_data

    def save(self):
        obj = super(CIFS_ShareForm, self).save(commit=False)
        path = self.cleaned_data.get('cifs_path').encode('utf8')
        if path and not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError, e:
                raise MiddlewareError(_(
                    'Failed to create %(path)s: %(error)s' % {
                        'path': path,
                        'error': e,
                    }
                ))

        home = self.cleaned_data.get('cifs_home')
        """
        task = self.cleaned_data.get('cifs_storage_task')
        if not task:
            task_list = []
            if path:
                task_list = self._get_storage_tasks(cifs_path=path)

            elif home:
                task_list = self._get_storage_tasks(cifs_home=home)

            if task_list:
                obj.cifs_storage_task = task_list[0]
        """

        obj.save()
        return obj

    def done(self, request, events):
        if not services.objects.get(srv_service='cifs').srv_enable:
            events.append('ask_service("cifs")')
        super(CIFS_ShareForm, self).done(request, events)
        if self.instance._original_cifs_default_permissions != \
            self.instance.cifs_default_permissions and \
            self.instance.cifs_default_permissions == True:
            notifier().winacl_reset(path=self.instance.cifs_path)


class AFP_ShareForm(ModelForm):

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

    def clean_afp_hostsallow(self):
        res = self.cleaned_data['afp_hostsallow']
        res = re.sub(r'\s{2,}|\n', ' ', res).strip()
        if not res:
            return res
        for n in res.split(' '):
            err_n = False
            err_a = False
            try:
                IPNetwork(n.encode('utf-8'))
                if n.find("/") == -1:
                    raise ValueError(n)
            except (AddressValueError, NetmaskValueError, ValueError):
                err_n = True
            try:
                IPAddress(n.encode('utf-8'))
            except (AddressValueError, ValueError):
                err_a = True
            if (err_n and err_a) or (not err_n and not err_a):
                raise forms.ValidationError(
                    _("Invalid IP or Network.")
                )
        return res

    def clean_afp_hostsdeny(self):
        res = self.cleaned_data['afp_hostsdeny']
        res = re.sub(r'\s{2,}|\n', ' ', res).strip()
        if not res:
            return res
        for n in res.split(' '):
            err_n = False
            err_a = False
            try:
                IPNetwork(n.encode('utf-8'))
                if n.find("/") == -1:
                    raise ValueError(n)
            except (AddressValueError, NetmaskValueError, ValueError):
                err_n = True
            try:
                IPAddress(n.encode('utf-8'))
            except (AddressValueError, ValueError):
                err_a = True
            if (err_n and err_a) or (not err_n and not err_a):
                raise forms.ValidationError(
                    _("Invalid IP or Network.")
                )
        return res

    def clean_afp_name(self):
        name = self.cleaned_data.get('afp_name')
        path = self.cleaned_data.get('afp_path')
        if path and not name:
            name = path.rsplit('/', 1)[-1]
        qs = models.AFP_Share.objects.filter(afp_name=name)
        if self.instance.id:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise forms.ValidationError(_(
                'A share with this name already exists.'
            ))
        return name

    def clean_afp_umask(self):
        umask = self.cleaned_data.get("afp_umask")
        if umask in (None, ''):
            return umask
        try:
            int(umask)
        except:
            raise forms.ValidationError(
                _("The umask must be between 000 and 777.")
            )
        for i in xrange(len(umask)):
            if int(umask[i]) > 7 or int(umask[i]) < 0:
                raise forms.ValidationError(
                    _("The umask must be between 000 and 777.")
                )
        return umask

    def save(self):
        obj = super(AFP_ShareForm, self).save(commit=False)
        path = self.cleaned_data.get('afp_path').encode('utf8')
        if path and not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError, e:
                raise MiddlewareError(_(
                    'Failed to create %(path)s: %(error)s' % {
                        'path': path,
                        'error': e,
                    }
                ))
        obj.save()
        return obj

    def done(self, request, events):
        dispatcher.call_sync('etcd.generation.generate_group', 'afp')
        dispatcher.call_sync('services.reload', 'afp')
        config = dispatcher.call_sync('service.afp.get_config')
        if not config['enable']:
            events.append('ask_service("afp")')
        super(AFP_ShareForm, self).done(request, events)


class NFS_ShareForm(ModelForm):

    class Meta:
        fields = '__all__'
        exclude = ['id']
        model = models.NFS_Share
        widgets = {
            'nfs_security': SelectMultipleWidget(sorter=True),
        }

    def clean_nfs_network(self):
        net = self.cleaned_data['nfs_network']
        net = re.sub(r'\s{2,}|\n', ' ', net).strip()
        if not net:
            return net
        for n in net.split(' '):
            try:
                IPNetwork(n.encode('utf-8'))
                if n.find("/") == -1:
                    raise ValueError(n)
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
        #only one address = CIDR or IP
        #if net.find(" ") == -1:
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
                stdev = os.stat(share.paths.all()[0].path).st_dev
            except:
                continue
            if share.nfs_network:
                used_networks.extend(
                    map(lambda y: (y, stdev), share.nfs_network.split(" "))
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
            for unetwork, ustdev in used_networks:
                if network == unetwork and dev == ustdev:
                    self._errors['nfs_network'] = self.error_class([
                        _("The network %s is already being shared and cannot "
                            "be used twice for the same filesystem") % (
                                network,
                            )
                    ])
                    valid = False
                    break

        return valid

    def save(self, *args, **kwargs):
        super(NFS_ShareForm, self).save(*args, **kwargs)

    def done(self, request, events):
        notifier().reload("nfs")
        if not services.objects.get(srv_service='nfs').srv_enable:
            events.append('ask_service("nfs")')
        super(NFS_ShareForm, self).done(request, events)


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
