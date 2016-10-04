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
from freenasUI.common.forms import ModelForm
from freenasUI.freeadmin.forms import SelectMultipleWidget
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.common.pipesubr import pipeopen
from freenasUI.services.models import services, NFS
from freenasUI.sharing import models
from freenasUI.storage.models import Task
from freenasUI.storage.widgets import UnixPermissionField
from ipaddr import (
    IPAddress, IPNetwork, AddressValueError, NetmaskValueError
)

log = logging.getLogger('sharing.forms')


class CIFS_ShareForm(ModelForm):

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

    def __init__(self, *args, **kwargs):
        super(CIFS_ShareForm, self).__init__(*args, **kwargs)
        if self.instance.id:
            self._original_cifs_vfsobjects = self.instance.cifs_vfsobjects
        else:
            self._original_cifs_vfsobjects = []

        self.fields['cifs_guestok'].widget.attrs['onChange'] = (
            'javascript:toggleGeneric("id_cifs_guestok", '
            '["id_cifs_guestonly"], true);')
        if self.data:
            if self.data.get('cifs_guestok') is False:
                self.fields['cifs_guestonly'].widget.attrs['disabled'] = \
                    'disabled'
        elif self.instance.cifs_guestok is False:
            self.fields['cifs_guestonly'].widget.attrs['disabled'] = 'disabled'
        self.instance._original_cifs_default_permissions = \
            self.instance.cifs_default_permissions
        self.fields['cifs_name'].required = False
        self.fields['cifs_home'].widget.attrs['onChange'] = (
            "cifs_storage_task_toggle();"
        )

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

    class Meta:
        fields = '__all__'
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
        task = self.cleaned_data.get('cifs_storage_task')
        if not task:
            task_list = []
            if path:
                task_list = self._get_storage_tasks(cifs_path=path)

            elif home:
                task_list = self._get_storage_tasks(cifs_home=home)

            if task_list:
                obj.cifs_storage_task = task_list[0]

        obj.save()
        notifier().reload("cifs")
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
        notifier().reload("afp")
        return obj

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
            except OSError, e:
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
