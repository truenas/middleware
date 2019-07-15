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

from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI.common.forms import ModelForm
from freenasUI.freeadmin.forms import SelectMultipleWidget
from freenasUI.freeadmin.utils import key_order
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.form import MiddlewareModelForm
from freenasUI.services.models import services, NFS
from freenasUI.sharing import models
from freenasUI.storage.widgets import UnixPermissionField

log = logging.getLogger('sharing.forms')


class CIFS_ShareForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "cifs_"
    middleware_attr_schema = "sharingsmb"
    middleware_plugin = "sharing.smb"
    is_singletone = False

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
        self.fields['cifs_name'].required = False

    class Meta:
        fields = '__all__'
        model = models.CIFS_Share

    def middleware_clean(self, data):
        data['hostsallow'] = data['hostsallow'].split()
        data['hostsdeny'] = data['hostsdeny'].split()

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


class NFS_ShareForm(MiddlewareModelForm, ModelForm):
    middleware_attr_prefix = "nfs_"
    middleware_attr_schema = "sharingnfs"
    middleware_plugin = "sharing.nfs"
    is_singletone = False
    middleware_attr_map = {
        "networks": "nfs_network",
    }

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

    def middleware_clean(self, data):
        data["paths"] = [
            self.data[f"path_set-{i}-path"]
            for i in range(int(self.data["path_set-TOTAL_FORMS"][0]))
            if self.data[f"path_set-{i}-path"] and not self.data.get(f"path_set-{i}-DELETE")
        ]
        data["networks"] = data.pop("network").split()
        data["hosts"] = data["hosts"].split()
        data["security"] = [s.upper() for s in data.get("security", [])]

        return data

    def done(self, request, events):
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


class WebDAV_ShareForm(MiddlewareModelForm, ModelForm):

    middleware_attr_schema = 'webdav_share'
    middleware_attr_prefix = 'webdav_'
    middleware_plugin = 'sharing.webdav'
    is_singletone = False

    class Meta:
        fields = '__all__'
        model = models.WebDAV_Share

    def done(self, request, events):
        if not services.objects.get(srv_service='webdav').srv_enable:
            events.append('ask_service("webdav")')
        super(WebDAV_ShareForm, self).done(request, events)
