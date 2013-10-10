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

from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI.sharing import models
from freenasUI.middleware.notifier import notifier
from freenasUI.common.forms import ModelForm
from freenasUI.services.models import services
from freenasUI.storage.widgets import UnixPermissionField
from ipaddr import (
    IPNetwork, AddressValueError, NetmaskValueError
)

log = logging.getLogger('sharing.forms')


class CIFS_ShareForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super(CIFS_ShareForm, self).__init__(*args, **kwargs)
        self.fields['cifs_guestok'].widget.attrs['onChange'] = (
            'javascript:toggleGeneric("id_cifs_guestok", '
            '["id_cifs_guestonly"], true);')
        if self.data:
            if self.data.get('cifs_guestok') is False:
                self.fields['cifs_guestonly'].widget.attrs['disabled'] = \
                    'disabled'
        elif self.instance.cifs_guestok is False:
            self.fields['cifs_guestonly'].widget.attrs['disabled'] = 'disabled'

    class Meta:
        model = models.CIFS_Share

    def clean_cifs_hostsallow(self):
        net = self.cleaned_data.get("cifs_hostsallow")
        net = re.sub(r'\s{2,}|\n', ' ', net).strip()
        return net

    def clean_cifs_hostsdeny(self):
        net = self.cleaned_data.get("cifs_hostsdeny")
        net = re.sub(r'\s{2,}|\n', ' ', net).strip()
        return net

    def save(self):
        ret = super(CIFS_ShareForm, self).save()
        notifier().reload("cifs")
        return ret

    def done(self, request, events):
        if not services.objects.get(srv_service='cifs').srv_enable:
            events.append('ask_service("cifs")')
        super(CIFS_ShareForm, self).done(request, events)


class AFP_ShareForm(ModelForm):

    afp_sharepw2 = forms.CharField(
        max_length=50,
        label=_("Confirm Share Password"),
        widget=forms.widgets.PasswordInput(render_value=False),
        required=False,
    )

    class Meta:
        model = models.AFP_Share
        widgets = {
            'afp_sharepw': forms.widgets.PasswordInput(render_value=False),
        }

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
            self.fields['afp_sharepw2'].initial = self.instance.afp_sharepw
            if self.instance.afp_sharepw:
                self.fields['afp_deletepw'] = forms.BooleanField(
                    label=_("Delete password"),
                    initial=False,
                    required=False,
                )
                self.fields.keyOrder.remove('afp_deletepw')
                self.fields.keyOrder.insert(5, 'afp_deletepw')
            if not self.instance.afp_upriv:
                self.fields['afp_fperm'].widget.attrs['disabled'] = 'true'
                self.fields['afp_dperm'].widget.attrs['disabled'] = 'true'
                self.fields['afp_umask'].widget.attrs['disabled'] = 'true'
            else:
                self.fields['afp_fperm'].widget.attrs['disabled'] = 'false'
                self.fields['afp_dperm'].widget.attrs['disabled'] = 'false'
                self.fields['afp_umask'].widget.attrs['disabled'] = 'false'

    def clean_afp_sharepw2(self):
        password1 = self.cleaned_data.get("afp_sharepw")
        password2 = self.cleaned_data.get("afp_sharepw2")
        if password1 != password2:
            raise forms.ValidationError(
                _("The two password fields didn't match.")
            )
        return password2

    def clean_afp_umask(self):
        umask = self.cleaned_data.get("afp_umask")
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


    def clean(self):
        cdata = self.cleaned_data
        if not cdata.get("afp_sharepw") and not cdata.get("afp_deletepw"):
            cdata['afp_sharepw'] = self.instance.afp_sharepw
        return cdata

    def save(self):
        ret = super(AFP_ShareForm, self).save()
        notifier().reload("afp")
        return ret

    def done(self, request, events):
        if not services.objects.get(srv_service='afp').srv_enable:
            events.append('ask_service("afp")')
        super(AFP_ShareForm, self).done(request, events)

AFP_ShareForm.base_fields.keyOrder.remove('afp_sharepw2')
AFP_ShareForm.base_fields.keyOrder.insert(4, 'afp_sharepw2')


class NFS_ShareForm(ModelForm):

    class Meta:
        model = models.NFS_Share

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
                stat = os.stat(path)
                if dev is None:
                    dev = stat.st_dev
                elif dev != stat.st_dev:
                    self._fserrors = self.error_class([
                        _("Paths for a NFS share must reside within the same "
                            "filesystem")
                    ])
                    valid = False
                    break
                if ismp:
                    self._fserrors = self.error_class([
                        _("You cannot share a mount point and subdirectories "
                            "all at once")
                    ])
                    valid = False
                    break
                if os.stat(parent).st_dev != stat.st_dev:
                    ismp = True
            except OSError:
                pass

        networks = self.cleaned_data.get("nfs_network", "").split(" ")
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
        paths = formsets.get("formset_nfs_share_path")
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

    def save(self, *args, **kwargs):
        super(NFS_ShareForm, self).save(*args, **kwargs)

    def done(self, request, events):
        notifier().reload("nfs")
        if not services.objects.get(srv_service='nfs').srv_enable:
            events.append('ask_service("nfs")')
        super(NFS_ShareForm, self).done(request, events)


class NFS_SharePathForm(ModelForm):

    class Meta:
        model = models.NFS_Share_Path

    def clean_path(self):
        path = self.cleaned_data.get("path")
        if not os.path.exists(path):
            raise forms.ValidationError(_("The path %s does not exist") % (
                path,
            ))
        return path
