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
import socket
import re

from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.http import QueryDict

from dojango import forms
from dojango.forms import widgets 
from freenasUI.sharing import models
from freenasUI.middleware.notifier import notifier
from freenasUI.common.forms import ModelForm
from freenasUI.common.freenasldap import FreeNAS_Users, FreeNAS_Groups, \
                                         FreeNAS_User, FreeNAS_Group


attrs_dict = { 'class': 'required', 'maxHeight': 200 }

""" Shares """
class MountPointForm(ModelForm):
    class Meta:
        model = models.MountPoint

class CIFS_ShareForm(ModelForm):
    cifs_guest = forms.ChoiceField(choices=(),
                                       widget=forms.Select(attrs=attrs_dict),
                                       label=_('Guest Account')
                                       )
    class Meta:
        model = models.CIFS_Share 

    def __init__(self, *args, **kwargs):
        #FIXME: Workaround for DOJO not showing select options with blank values
        if len(args) > 0 and isinstance(args[0], QueryDict):
            new = args[0].copy()
            if new.get('cifs_guest', None) == '-----':
                new['cifs_guest'] = ''
            args = (new,) + args[1:]
        super(CIFS_ShareForm, self).__init__(*args, **kwargs)
        from account.forms import FilteredSelectJSON
        if len(FreeNAS_Users()) > 500:
            if len(args) > 0 and isinstance(args[0], QueryDict):
                self.fields['cifs_guest'].choices = ((args[0]['cifs_guest'],args[0]['cifs_guest']),)
                self.fields['cifs_guest'].initial= args[0]['cifs_guest']
            self.fields['cifs_guest'].widget = FilteredSelectJSON(url=reverse("account_bsduser_json"))
        else:
            self.fields['cifs_guest'].widget = widgets.FilteringSelect()
            self.fields['cifs_guest'].choices = (
                                                 (x.bsdusr_username, x.bsdusr_username)
                                                      for x in FreeNAS_Users()
                                                )
    def clean_cifs_guest(self):
        user = self.cleaned_data['cifs_guest']
        if FreeNAS_User(user) == None:
            raise forms.ValidationError(_("The user %s is not valid.") % user)
        return user
    def save(self):
        ret = super(CIFS_ShareForm, self).save()
        notifier().reload("cifs")
        return ret

class AFP_ShareForm(ModelForm):
    class Meta:
        model = models.AFP_Share 
    def save(self):
        ret = super(AFP_ShareForm, self).save()
        notifier().reload("afp")
        return ret

class NFS_ShareForm(ModelForm):
    class Meta:
        model = models.NFS_Share 
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

        from account.forms import FilteredSelectJSON
        if len(FreeNAS_Users()) > 500:
            if len(args) > 0 and isinstance(args[0], QueryDict):
                self.fields['nfs_maproot_user'].choices = ((args[0]['nfs_maproot_user'],args[0]['nfs_maproot_user']),)
                self.fields['nfs_maproot_user'].initial = args[0]['nfs_maproot_user']
                self.fields['nfs_mapall_user'].choices = ((args[0]['nfs_mapall_user'],args[0]['nfs_mapall_user']),)
                self.fields['nfs_mapall_user'].initial = args[0]['nfs_mapall_user']
            self.fields['nfs_maproot_user'].widget = FilteredSelectJSON(url=reverse("account_bsduser_json"))
            self.fields['nfs_mapall_user'].widget = FilteredSelectJSON(url=reverse("account_bsduser_json"))
        else:
            self.userlist = []
            self.userlist.append(('-----', 'N/A'))
            for a in list((x.bsdusr_username, x.bsdusr_username)
                          for x in FreeNAS_Users()):
                self.userlist.append(a)
            self.fields['nfs_maproot_user'].widget = widgets.FilteringSelect()
            self.fields['nfs_mapall_user'].widget = widgets.FilteringSelect()
            self.fields['nfs_maproot_user'].choices = self.userlist
            self.fields['nfs_mapall_user'].choices = self.userlist

        if len(FreeNAS_Groups()) > 500:
            if len(args) > 0 and isinstance(args[0], QueryDict):
                self.fields['nfs_maproot_group'].choices = ((args[0]['nfs_maproot_group'],args[0]['nfs_maproot_group']),)
                self.fields['nfs_maproot_group'].initial = args[0]['nfs_maproot_group']
                self.fields['nfs_mapall_group'].choices = ((args[0]['nfs_mapall_group'],args[0]['nfs_mapall_group']),)
                self.fields['nfs_mapall_group'].initial = args[0]['nfs_mapall_group']
            self.fields['nfs_maproot_group'].widget = FilteredSelectJSON(url=reverse("account_bsdgroup_json"))
            self.fields['nfs_mapall_group'].widget = FilteredSelectJSON(url=reverse("account_bsdgroup_json"))
        else:
            self.grouplist = []
            self.grouplist.append(('-----', 'N/A'))
            for a in list((x.bsdgrp_group, x.bsdgrp_group)
                          for x in FreeNAS_Groups()):
                self.grouplist.append(a)

            self.fields['nfs_maproot_group'].widget = widgets.FilteringSelect()
            self.fields['nfs_mapall_group'].widget = widgets.FilteringSelect()
            self.fields['nfs_maproot_group'].choices = self.grouplist
            self.fields['nfs_mapall_group'].choices = self.grouplist

    def clean_nfs_network(self):
        net = self.cleaned_data['nfs_network']
        net = re.sub(r'\s{2,}', ' ', net).strip()
        if not net:
            return net
        #only one address = netmask CIDR
        if net.find(" ") == -1:
            if net.find("/") == -1:
                try:
                    socket.inet_aton(net)
                except socket.error:
                    raise forms.ValidationError(_("The IP '%s' is not valid.") % net)
            else:
                try:
                    socket.inet_aton(net.split("/")[0])
                    if int(net.split("/")[1]) > 32 or int(net.split("/")[1]) < 0:
                        raise
                except:
                    raise forms.ValidationError(_("The netmask '%s' is not valid.") % net)
        else:
            for ip in net.split(' '):
                try:
                    socket.inet_aton(ip)
                except socket.error:
                    raise forms.ValidationError(_("The IP '%s' is not valid.") % ip)
        return net

    def clean_nfs_mapall_user(self):
        user = self.cleaned_data['nfs_mapall_user']
        if user in ('','-----'):
            return None
        if FreeNAS_User(user) == None:
            raise forms.ValidationError(_("The user %s is not valid.") % user)
        return user

    def clean_nfs_maproot_user(self):
        user = self.cleaned_data['nfs_maproot_user']
        if user in ('','-----'):
            return None
        if FreeNAS_User(user) == None:
            raise forms.ValidationError(_("The user %s is not valid.") % user)
        return user

    def clean_nfs_mapall_group(self):
        group = self.cleaned_data['nfs_mapall_group']
        if group in ('','-----'):
            return None
        if FreeNAS_Group(group) == None:
            raise forms.ValidationError(_("The group %s is not valid.") % group)
        return group

    def clean_nfs_maproot_group(self):
        group = self.cleaned_data['nfs_maproot_group']
        if group in ('','-----'):
            return None
        if FreeNAS_Group(group) == None:
            raise forms.ValidationError(_("The group %s is not valid.") % group)
        return group

    def clean(self):

        cdata = self.cleaned_data
        for field in ('nfs_maproot_user', 'nfs_maproot_group', 
                        'nfs_mapall_user', 'nfs_mapall_group'):
            if cdata.get(field, None) in ('', '-----'):
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
