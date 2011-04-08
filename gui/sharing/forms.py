#+
# Copyright 2010 iXsystems
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
# $FreeBSD$
#####################################################################

from django.utils.translation import ugettext as _

from dojango import forms
from dojango.forms import fields, widgets 
from dojango.forms.fields import BooleanField 
from freenasUI.sharing.models import *                         
from freenasUI.middleware.notifier import notifier
from freenasUI.common.forms import ModelForm
from freenasUI.common.forms import Form
from freenasUI.common.freenasldap import FreeNAS_Users

attrs_dict = { 'class': 'required', 'maxHeight': 200 }

""" Shares """
class MountPointForm(ModelForm):
    class Meta:
        model = MountPoint

class CIFS_ShareForm(ModelForm):
    class Meta:
        model = CIFS_Share 
    def save(self):
        ret = super(CIFS_ShareForm, self).save()
        notifier().reload("cifs")
        return ret

class AFP_ShareForm(ModelForm):
    class Meta:
        model = AFP_Share 
    def save(self):
        ret = super(AFP_ShareForm, self).save()
        notifier().reload("afp")
        return ret

class NFS_ShareForm(ModelForm):
    class Meta:
        model = NFS_Share 
    nfs_maproot_user = forms.ChoiceField(choices=(),
                                         widget = forms.Select(attrs=attrs_dict),
                                         label = _("Maproot User"),
                                         required = False,
                                         )
    nfs_maproot_group = forms.ChoiceField(choices=(),
                                         widget = forms.Select(attrs=attrs_dict),
                                         label = _("Maproot Group"),
                                         required = False,
                                         )
    nfs_mapall_user = forms.ChoiceField(choices=(),
                                         widget = forms.Select(attrs=attrs_dict),
                                         label = _("Mapall User"),
                                         required = False,
                                         )
    nfs_mapall_group = forms.ChoiceField(choices=(),
                                         widget = forms.Select(attrs=attrs_dict),
                                         label = _("Mapall Group"),
                                         required = False,
                                         )

    def __init__(self, *args, **kwargs):
        super(NFS_ShareForm, self).__init__(*args, **kwargs)

        self.userlist = []
        self.userlist.append(('-----', 'N/A'))
        for a in list((x.bsdusr_username, x.bsdusr_username)
                      for x in FreeNAS_Users()):
             self.userlist.append(a)

        self.grouplist = []
        self.grouplist.append(('-----', 'N/A'))
        for a in list((x.bsdusr_group, x.bsdusr_group)
                      for x in FreeNAS_Users()):
             self.grouplist.append(a)

        self.fields['nfs_maproot_user'].widget = widgets.FilteringSelect()
        self.fields['nfs_maproot_group'].widget = widgets.FilteringSelect()
        self.fields['nfs_mapall_user'].widget = widgets.FilteringSelect()
        self.fields['nfs_mapall_group'].widget = widgets.FilteringSelect()
        self.fields['nfs_maproot_user'].choices = self.userlist
        self.fields['nfs_maproot_group'].choices = self.grouplist
        self.fields['nfs_mapall_user'].choices = self.userlist
        self.fields['nfs_mapall_group'].choices = self.grouplist

    def clean(self):

        cdata = self.cleaned_data
        for field in ('nfs_maproot_user', 'nfs_maproot_group', 
                        'nfs_mapall_user', 'nfs_mapall_group'):
            if cdata.get(field, None) == '-----':
                cdata[field] = None

        if cdata.get('nfs_maproot_group', None) != None and cdata.get('nfs_maproot_user', None) == None:
            self._errors['nfs_maproot_group'] = self.error_class([_("Maproot group requires Maproot user"),])
        if cdata.get('nfs_mapall_group', None) != None and cdata.get('nfs_mapall_user', None) == None:
            self._errors['nfs_mapall_group'] = self.error_class([_("Mapall group requires Mapall user"),])
        if cdata.get('nfs_maproot_user', None) != None or cdata.get('nfs_maproot_group', None) != None:
            if cdata.get('nfs_mapall_user', None) != None:
                self._errors['nfs_mapall_user'] = self.error_class([_("Maproot user/group disqualifies Mapall"),])
                del cdata['nfs_mapall_user']
            if cdata.get('nfs_mapall_group', None) != None:
                self._errors['nfs_mapall_group'] = self.error_class([_("Maproot user/group disqualifies Mapall"),])
                del cdata['nfs_mapall_group']
        #elif cdata.get('nfs_mapall_user', False) or cdata.get('nfs_mapall_group', False):
        #    if cdata.get('nfs_maproot_user', False) != False:
        #        self._errors['nfs_maproot_user'] = self.error_class([_("Mapall user/group disqualifies Maproot"),])
        #        del cdata['nfs_maproot_user']
        #    if cdata.get('nfs_maproot_group', False) != False:
        #        self._errors['nfs_maproot_group'] = self.error_class([_("Mapall user/group disqualifies Maproot"),])
        #        del cdata['nfs_maproot_group']

        return cdata

    def save(self, *args, **kwargs):
        super(NFS_ShareForm, self).save(*args, **kwargs)
        notifier().reload("nfs")
