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

import base64
import re
import os

from django.core.exceptions import ObjectDoesNotExist
from django.http import QueryDict
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse

import choices
from services import models
from services.exceptions import ServiceFailed
from storage.models import Volume, MountPoint, DiskGroup, Disk
from storage.forms import UnixPermissionField
from freenasUI.common.forms import ModelForm, Form
from freenasUI.common.freenasldap import FreeNAS_Users, FreeNAS_User
from freenasUI.middleware.notifier import notifier
from dojango import forms
from dojango.forms import widgets
from freeadmin.forms import CronMultiple

""" Services """

attrs_dict = { 'class': 'required' }

class servicesForm(ModelForm):
    class Meta:
        model = models.services

class CIFSForm(ModelForm):
    class Meta:
        model = models.CIFS
    cifs_srv_guest = forms.ChoiceField(choices=(),
                                       widget=forms.Select(attrs=attrs_dict),
                                       label=_('Guest Account')
                                       )
    def __init__(self, *args, **kwargs):
        #FIXME: Workaround for DOJO not showing select options with blank values
        if len(args) > 0 and isinstance(args[0], QueryDict):
            new = args[0].copy()
            if new.get('cifs_srv_homedir', None) == '-----':
                new['cifs_srv_homedir'] = ''
            args = (new,) + args[1:]
        super(CIFSForm, self).__init__(*args, **kwargs)
        from account.forms import FilteredSelectJSON
        if len(FreeNAS_Users()) > 500:
            if len(args) > 0 and isinstance(args[0], QueryDict):
                self.fields['cifs_srv_guest'].choices = ((args[0]['cifs_srv_guest'],args[0]['cifs_srv_guest']),)
                self.fields['cifs_srv_guest'].initial= args[0]['cifs_srv_guest']
            self.fields['cifs_srv_guest'].widget = FilteredSelectJSON(url=reverse("account_bsduser_json"))
        else:
            self.fields['cifs_srv_guest'].widget = widgets.FilteringSelect()
            self.fields['cifs_srv_guest'].choices = ((x.bsdusr_username,
                                                      x.bsdusr_username)
                                                      for x in FreeNAS_Users()
                                                     )
        #FIXME: Workaround for DOJO not showing select options with blank values
        self.fields['cifs_srv_homedir'].choices = (('-----', _('N/A')),) + tuple([x for x in self.fields['cifs_srv_homedir'].choices][1:])
    def clean_cifs_srv_guest(self):
        user = self.cleaned_data['cifs_srv_guest']
        if FreeNAS_User(user) == None:
            raise forms.ValidationError(_("The user %s is not valid.") % user)
        return user
    def clean(self):
        cleaned_data = self.cleaned_data
        home = cleaned_data['cifs_srv_homedir_enable']
        browse = cleaned_data['cifs_srv_homedir_browseable_enable']
        hdir = cleaned_data['cifs_srv_homedir']
        if (browse or hdir) and not home:
            self._errors['cifs_srv_homedir_enable'] = self.error_class()
            if browse:
                self._errors['cifs_srv_homedir_enable'] += self.error_class([_("This field is required for \"Enable home directories browsing\"."),])
                cleaned_data.pop('cifs_srv_homedir_enable', None)
            if hdir:
                self._errors['cifs_srv_homedir_enable'] += self.error_class([_("This field is required for \"Home directories\"."),])
                cleaned_data.pop('cifs_srv_homedir_enable', None)
        return cleaned_data

    def save(self):
        super(CIFSForm, self).save()
        started = notifier().reload("cifs")
        if started is False and models.services.objects.get(srv_service='cifs').srv_enable:
            raise ServiceFailed("cifs", "The CIFS service failed to reload.")

class AFPForm(ModelForm):
    class Meta:
        model = models.AFP
    afp_srv_guest_user = forms.ChoiceField(choices=(),
                                           widget=forms.Select(attrs=attrs_dict),
                                           label = _("Guest Account")
                                           )
    def __init__(self, *args, **kwargs):
        super(AFPForm, self).__init__(*args, **kwargs)
        from account.forms import FilteredSelectJSON
        if len(FreeNAS_Users()) > 500:
            if len(args) > 0 and isinstance(args[0], QueryDict):
                self.fields['afp_srv_guest_user'].choices = ((args[0]['afp_srv_guest_user'],args[0]['afp_srv_guest_user']),)
                self.fields['afp_srv_guest_user'].initial= args[0]['afp_srv_guest_user']
            self.fields['afp_srv_guest_user'].widget = FilteredSelectJSON(url=reverse("account_bsduser_json"))
        else:
            self.fields['afp_srv_guest_user'].widget = widgets.FilteringSelect()
            self.fields['afp_srv_guest_user'].choices = ((x.bsdusr_username,
                                                          x.bsdusr_username)
                                                         for x in FreeNAS_Users())
    def clean_afp_srv_guest_user(self):
        user = self.cleaned_data['afp_srv_guest_user']
        if FreeNAS_User(user) == None:
            raise forms.ValidationError(_("The user %s is not valid.") % user)
        return user
    def save(self):
        super(AFPForm, self).save()
        started = notifier().restart("afp")
        if started is False and models.services.objects.get(srv_service='afp').srv_enable:
            raise ServiceFailed("afp", _("The AFP service failed to reload."))

class NFSForm(ModelForm):
    class Meta:
        model = models.NFS
    def save(self):
        super(NFSForm, self).save()
        started = notifier().restart("nfs")
        if started is False and models.services.objects.get(srv_service='nfs').srv_enable:
            raise ServiceFailed("nfs", _("The NFS service failed to reload."))

class FTPForm(ModelForm):

    ftp_filemask = UnixPermissionField(label=_('File Permission'))
    ftp_dirmask = UnixPermissionField(label=_('Directory Permission'))
    class Meta:
        model = models.FTP 

    def __init__(self, *args, **kwargs):

        if kwargs.has_key('instance'):
            instance = kwargs['instance']
            try:
                mask = int(instance.ftp_filemask, 8)
                instance.ftp_filemask = "%.3o" % (~mask & 0o666)
            except ValueError:
                pass

            try:
                mask = int(instance.ftp_dirmask, 8)
                instance.ftp_dirmask = "%.3o" % (~mask & 0o777)
            except ValueError:
                pass

        super(FTPForm, self).__init__(*args, **kwargs)

    def clean_ftp_port(self):
        port = self.cleaned_data['ftp_port']
        if port < 0 or port > 65535:
            raise forms.ValidationError(_("This value must be between 0 and 65535, inclusive."))
        return port

    def clean_ftp_clients(self):
        clients = self.cleaned_data['ftp_clients']
        if clients < 0 or clients > 10000:
            raise forms.ValidationError(_("This value must be between 0 and 10000, inclusive."))
        return clients

    def clean_ftp_ipconnections(self):
        conn = self.cleaned_data['ftp_ipconnections']
        if conn < 0 or conn > 1000:
            raise forms.ValidationError(_("This value must be between 0 and 1000, inclusive."))
        return conn

    def clean_ftp_loginattempt(self):
        attempt = self.cleaned_data['ftp_loginattempt']
        if attempt < 0 or attempt > 1000:
            raise forms.ValidationError(_("This value must be between 0 and 1000, inclusive."))
        return attempt

    def clean_ftp_timeout(self):
        timeout = self.cleaned_data['ftp_timeout']
        if timeout < 0 or timeout > 10000:
            raise forms.ValidationError(_("This value must be between 0 and 10000, inclusive."))
        return timeout

    def clean_ftp_passiveportsmin(self):
        ports = self.cleaned_data['ftp_passiveportsmin']
        if (ports < 1024 or ports > 65535) and ports != 0:
            raise forms.ValidationError(_("This value must be between 1024 and 65535, inclusive. 0 for default"))
        return ports

    def clean_ftp_passiveportsmax(self):
        ports = self.cleaned_data['ftp_passiveportsmax']
        if (ports < 1024 or ports > 65535) and ports != 0:
            raise forms.ValidationError(_("This value must be between 1024 and 65535, inclusive. 0 for default."))
        return ports

    def clean_ftp_filemask(self):
        perm = self.cleaned_data['ftp_filemask']
        perm = int(perm, 8)
        mask = (~perm & 0o666)
        return "%.3o" % mask

    def clean_ftp_dirmask(self):
        perm = self.cleaned_data['ftp_dirmask']
        perm = int(perm, 8)
        mask = (~perm & 0o777)
        return "%.3o" % mask

    def clean_ftp_anonpath(self):
        anon = self.cleaned_data['ftp_onlyanonymous']
        path = self.cleaned_data['ftp_anonpath']
        if anon and not path:
            raise forms.ValidationError(_("This field is required for anonymous login"))
        return path

    def save(self):
        super(FTPForm, self).save()
        started = notifier().reload("ftp")
        if started is False and models.services.objects.get(srv_service='ftp').srv_enable:
            raise ServiceFailed("ftp", _("The ftp service failed to start."))

class TFTPForm(ModelForm):
    tftp_username = forms.ChoiceField(widget=forms.Select(attrs=attrs_dict),
                                      label = _("Username")
                                      )
    def __init__(self, *args, **kwargs):
        super(TFTPForm, self).__init__(*args, **kwargs)
        from account.forms import FilteredSelectJSON
        if len(FreeNAS_Users()) > 500:
            if len(args) > 0 and isinstance(args[0], QueryDict):
                self.fields['tftp_username'].choices = ((args[0]['tftp_username'],args[0]['tftp_username']),)
                self.fields['tftp_username'].initial= args[0]['tftp_username']
            self.fields['tftp_username'].widget = FilteredSelectJSON(url=reverse("account_bsduser_json"))
        else:
            self.fields['tftp_username'].widget = widgets.FilteringSelect()
            self.fields['tftp_username'].choices = ((x.bsdusr_username, x.bsdusr_username)
                                                    for x in FreeNAS_Users())
    def clean_tftp_username(self):
        user = self.cleaned_data['tftp_username']
        if FreeNAS_User(user) == None:
            raise forms.ValidationError(_("The user %s is not valid.") % user)
        return user
    def save(self):
        super(TFTPForm, self).save()
        started = notifier().reload("tftp")
        if started is False and models.services.objects.get(srv_service='tftp').srv_enable:
            raise ServiceFailed("tftp", _("The tftp service failed to reload."))
    class Meta:
        model = models.TFTP 

class SSHForm(ModelForm):
    def save(self):
        super(SSHForm, self).save()
        started = notifier().reload("ssh")
        if started is False and models.services.objects.get(srv_service='ssh').srv_enable:
            raise ServiceFailed("ssh", _("The SSH service failed to reload."))
    class Meta:
        model = models.SSH 

class DynamicDNSForm(ModelForm):
    class Meta:
        model = models.DynamicDNS
    def save(self):
        super(DynamicDNSForm, self).save()
        started = notifier().restart("dynamicdns")
        if started is False and models.services.objects.get(srv_service='dynamicdns').srv_enable:
            raise ServiceFailed("dynamicdns", _("The DynamicDNS service failed to reload."))

class SNMPForm(ModelForm):
    class Meta:
        model = models.SNMP
    def save(self):
        super(SNMPForm, self).save()
        started = notifier().restart("snmp")
        if started is False and models.services.objects.get(srv_service='snmp').srv_enable:
            raise ServiceFailed("snmp", _("The SNMP service failed to reload."))

class UPSForm(ModelForm):
    class Meta:
        model = models.UPS

class ActiveDirectoryForm(ModelForm):
    #file = forms.FileField(label="Kerberos Keytab File", required=False)
    def save(self):
        if self.files.has_key('file'):
            self.instance.ad_keytab = base64.encodestring(self.files['file'].read())
        super(ActiveDirectoryForm, self).save()
        started = notifier().start("activedirectory")
        if started is False and models.services.objects.get(srv_service='activedirectory').srv_enable:
            raise ServiceFailed("activedirectory", _("The activedirectory service failed to reload."))
    class Meta:
        model = models.ActiveDirectory
        exclude = ('ad_keytab','ad_spn','ad_spnpw')
        widgets = {'ad_adminpw': forms.widgets.PasswordInput(render_value=True), } 

class LDAPForm(ModelForm):
    def save(self):
        super(LDAPForm, self).save()
        started = notifier().restart("ldap")
        if started is False and models.services.objects.get(srv_service='ldap').srv_enable:
            raise ServiceFailed("ldap", _("The ldap service failed to reload."))
    class Meta:
        model = models.LDAP
        widgets = {'ldap_rootbindpw': forms.widgets.PasswordInput(render_value=True), } 

class iSCSITargetAuthCredentialForm(ModelForm):
    iscsi_target_auth_secret1 = forms.CharField(label=_("Secret"), 
            widget=forms.PasswordInput, help_text=_("Target side secret."))
    iscsi_target_auth_secret2 = forms.CharField(label=_("Secret (Confirm)"), 
            widget=forms.PasswordInput, 
            help_text=_("Enter the same secret above for verification."))
    iscsi_target_auth_peersecret1 = forms.CharField(label=_("Initiator Secret"),
            widget=forms.PasswordInput, help_text=
            _("Initiator side secret. (for mutual CHAP authentication)"),
            required=False)
    iscsi_target_auth_peersecret2 = forms.CharField(
            label=_("Initiator Secret (Confirm)"), 
            widget=forms.PasswordInput, 
            help_text=_("Enter the same secret above for verification."),
            required=False)

    def _clean_secret_common(self, secretprefix):
        secret1 = self.cleaned_data.get(("%s1" % secretprefix), "")
        secret2 = self.cleaned_data[("%s2" % secretprefix)]
        if secret1 != secret2:
            raise forms.ValidationError(_("Secret does not match"))
        return secret2

    def clean_iscsi_target_auth_secret2(self):
        return self._clean_secret_common("iscsi_target_auth_secret")

    def clean_iscsi_target_auth_peersecret2(self):
        return self._clean_secret_common("iscsi_target_auth_peersecret")

    def clean(self):
        cdata = self.cleaned_data

        if len(cdata.get('iscsi_target_auth_peeruser', '')) > 0:
            if len(cdata.get('iscsi_target_auth_peersecret1', '')) == 0:
                del cdata['iscsi_target_auth_peersecret1']
                self._errors['iscsi_target_auth_peersecret1'] = self.error_class([_("The peer secret is required if you set a peer user.")])
                self._errors['iscsi_target_auth_peersecret2'] = self.error_class([_("The peer secret is required if you set a peer user.")])
            elif cdata.get('iscsi_target_auth_peersecret1', '') == cdata.get('iscsi_target_auth_secret1', ''):
                del cdata['iscsi_target_auth_peersecret1']
                self._errors['iscsi_target_auth_peersecret1'] = self.error_class([_("The peer secret cannot be the same as user secret.")])

        return cdata

    class Meta:
        model = models.iSCSITargetAuthCredential
        exclude = ('iscsi_target_auth_secret', 'iscsi_target_auth_peersecret',)

    def save(self, commit=True):
        oAuthCredential = super(iSCSITargetAuthCredentialForm, self).save(commit=False)
        oAuthCredential.iscsi_target_auth_secret = self.cleaned_data["iscsi_target_auth_secret1"]
        oAuthCredential.iscsi_target_auth_peersecret = self.cleaned_data["iscsi_target_auth_peersecret1"]
        if commit:
            oAuthCredential.save()
        started = notifier().reload("iscsitarget")
        if started is False and models.services.objects.get(srv_service='iscsitarget').srv_enable:
            raise ServiceFailed("iscsitarget", _("The iSCSI service failed to reload."))
        return oAuthCredential

    def __init__(self, *args, **kwargs):
        super(iSCSITargetAuthCredentialForm, self).__init__(*args, **kwargs)
        self.fields.keyOrder = [
            'iscsi_target_auth_tag',
            'iscsi_target_auth_user',
            'iscsi_target_auth_secret1',
            'iscsi_target_auth_secret2',
            'iscsi_target_auth_peeruser',
            'iscsi_target_auth_peersecret1',
            'iscsi_target_auth_peersecret2']

        try:
            self.fields['iscsi_target_auth_secret1'].initial = self.instance.iscsi_target_auth_secret
            self.fields['iscsi_target_auth_secret2'].initial = self.instance.iscsi_target_auth_secret
            self.fields['iscsi_target_auth_peersecret1'].initial = self.instance.iscsi_target_auth_peersecret
            self.fields['iscsi_target_auth_peersecret2'].initial = self.instance.iscsi_target_auth_peersecret
        except:
            pass

class iSCSITargetToExtentForm(ModelForm):
    class Meta:
        model = models.iSCSITargetToExtent
    def clean_iscsi_target_lun(self):
        try:
            models.iSCSITargetToExtent.objects.get(iscsi_target=self.cleaned_data.get('iscsi_target'),
                                                  iscsi_target_lun=self.cleaned_data.get('iscsi_target_lun'))
            raise forms.ValidationError(_("LUN already exists in the same target."))
        except ObjectDoesNotExist:
            return self.cleaned_data.get('iscsi_target_lun')

    def save(self):
        super(iSCSITargetToExtentForm, self).save()
        started = notifier().reload("iscsitarget")
        if started is False and models.services.objects.get(srv_service='iscsitarget').srv_enable:
            raise ServiceFailed("iscsitarget", _("The iSCSI service failed to reload."))

class iSCSITargetGlobalConfigurationForm(ModelForm):
    iscsi_luc_authgroup = forms.ChoiceField(label=_("Controller Auth Group"),
            help_text=_("The istgtcontrol can access the targets with correct user and secret in specific Auth Group."))
    iscsi_discoveryauthgroup = forms.ChoiceField(label=_("Discovery Auth Group"))
    class Meta:
        model = models.iSCSITargetGlobalConfiguration
    def __init__(self, *args, **kwargs):
        super(iSCSITargetGlobalConfigurationForm, self).__init__(*args, **kwargs)
        self.fields['iscsi_luc_authgroup'].required = False
        self.fields['iscsi_luc_authgroup'].choices = [(-1, _('None'))] + [(i['iscsi_target_auth_tag'], i['iscsi_target_auth_tag']) for i in models.iSCSITargetAuthCredential.objects.all().values('iscsi_target_auth_tag').distinct()]
        self.fields['iscsi_discoveryauthgroup'].required = False
        self.fields['iscsi_discoveryauthgroup'].choices = [('-1', _('None'))] + [(i['iscsi_target_auth_tag'], i['iscsi_target_auth_tag']) for i in models.iSCSITargetAuthCredential.objects.all().values('iscsi_target_auth_tag').distinct()]
        self.fields['iscsi_toggleluc'].widget.attrs['onChange'] = 'javascript:toggleLuc(this);'
        ro = True
        if len(self.data) > 0:
            if self.data.get("iscsi_toggleluc", None) == "on":
                ro = False
        else:
            if self.instance.iscsi_toggleluc == True:
                ro = False
        if ro:
            self.fields['iscsi_lucip'].widget.attrs['disabled'] = 'disabled'
            self.fields['iscsi_lucport'].widget.attrs['disabled'] = 'disabled'
            self.fields['iscsi_luc_authnetwork'].widget.attrs['disabled'] = 'disabled'
            self.fields['iscsi_luc_authmethod'].widget.attrs['disabled'] = 'disabled'
            self.fields['iscsi_luc_authgroup'].widget.attrs['disabled'] = 'disabled'

    def _clean_number_range(self, field, start, end):
        f = self.cleaned_data[field]
        if f < start or f > end:
            raise forms.ValidationError(_("This value must be between %(start)d and %(end)d, inclusive.") % { 'start': start, 'end': end })
        return f

    def clean_iscsi_discoveryauthgroup(self):
        discoverymethod = self.cleaned_data['iscsi_discoveryauthmethod']
        discoverygroup = self.cleaned_data['iscsi_discoveryauthgroup']
        if discoverymethod in ('CHAP', 'CHAP Mutual'):
            if int(discoverygroup) == -1:
                raise forms.ValidationError(_("This field is required if discovery method is set to CHAP or CHAP Mutal."))
        elif int(discoverygroup) == -1:
            return None
        return discoverygroup

    def clean_iscsi_iotimeout(self):
        return self._clean_number_range("iscsi_iotimeout", 0, 300)

    def clean_iscsi_nopinint(self):
        return self._clean_number_range("iscsi_nopinint", 0, 300)

    def clean_iscsi_maxsesh(self):
        return self._clean_number_range("iscsi_maxsesh", 1, 64)

    def clean_iscsi_maxconnect(self):
        return self._clean_number_range("iscsi_maxconnect", 1, 64)

    def clean_iscsi_r2t(self):
        return self._clean_number_range("iscsi_r2t", 1, 255)

    def clean_iscsi_maxoutstandingr2t(self):
        return self._clean_number_range("iscsi_maxoutstandingr2t", 1, 255)

    def clean_iscsi_firstburst(self):
        return self._clean_number_range("iscsi_firstburst", 1, pow(2,32))

    def clean_iscsi_maxburst(self):
        return self._clean_number_range("iscsi_maxburst", 1, pow(2,32))

    def clean_iscsi_maxrecdata(self):
        return self._clean_number_range("iscsi_maxrecdata", 1, pow(2,32))

    def clean_iscsi_defaultt2w(self):
        return self._clean_number_range("iscsi_defaultt2w", 1, 300)

    def clean_iscsi_defaultt2r(self):
        return self._clean_number_range("iscsi_defaultt2r", 1, 300)

    def clean_iscsi_lucport(self):
        if self.cleaned_data.get('iscsi_toggleluc', False):
            return self._clean_number_range("iscsi_lucport", 1000, pow(2,16))
        return None

    def clean_iscsi_luc_authgroup(self):
        lucmethod = self.cleaned_data['iscsi_luc_authmethod']
        lucgroup = self.cleaned_data['iscsi_luc_authgroup']
        if lucmethod in ('CHAP', 'CHAP Mutual'):
            if lucgroup != '' and int(lucgroup) == -1:
                raise forms.ValidationError(_("This field is required."))
        elif lucgroup != '' and int(lucgroup) == -1:
            return None
        return lucgroup

    def clean(self):
        cdata = self.cleaned_data

        luc = cdata.get("iscsi_toggleluc", False)
        if luc:
            for field in ('iscsi_lucip', 'iscsi_luc_authnetwork', 
                    'iscsi_luc_authmethod', 'iscsi_luc_authgroup'):
                if cdata.has_key(field) and cdata[field] == '':
                    self._errors[field] = self.error_class([_("This field is required.")])
                    del cdata[field]
        else:
            cdata['iscsi_lucip'] = None
            cdata['iscsi_lucport'] = None
            cdata['iscsi_luc_authgroup'] = None

        return cdata

    def save(self):
        super(iSCSITargetGlobalConfigurationForm, self).save()
        started = notifier().reload("iscsitarget")
        if started is False and models.services.objects.get(srv_service='iscsitarget').srv_enable:
            raise ServiceFailed("iscsitarget", _("The iSCSI service failed to reload."))

class iSCSITargetExtentEditForm(ModelForm):
    class Meta:
        model = models.iSCSITargetExtent
        exclude = ('iscsi_target_extent_type',)
    def clean_iscsi_target_extent_path(self):
        path = self.cleaned_data["iscsi_target_extent_path"]
        if path[-1] == '/':
            raise forms.ValidationError(_("You need to specify a filepath, not a directory."))
        valid = False
        for mp in MountPoint.objects.all():
            if path == mp.mp_path:
                raise forms.ValidationError(_("You need to specify a file inside your volume/dataset."))
            if path.startswith(mp.mp_path):
                valid = True
        if not valid:
            raise forms.ValidationError(_("Your path to the extent must reside inside a volume/dataset mount point."))
        return path
    def save(self):
        super(iSCSITargetExtentEditForm, self).save()
        path = self.cleaned_data["iscsi_target_extent_path"]
        dirs = "/".join(path.split("/")[:-1])
        if not os.path.exists(dirs):
            try:
                os.makedirs(dirs)
            except Exception, e:
                pass
        started = notifier().reload("iscsitarget")
        if started is False and models.services.objects.get(srv_service='iscsitarget').srv_enable:
            raise ServiceFailed("iscsitarget", _("The iSCSI service failed to reload."))

class iSCSITargetFileExtentForm(ModelForm):
    class Meta:
        model = models.iSCSITargetExtent
        exclude = ('iscsi_target_extent_type')
    def clean_iscsi_target_extent_path(self):
        path = self.cleaned_data["iscsi_target_extent_path"]
        if path[-1] == '/':
            raise forms.ValidationError(_("You need to specify a filepath, not a directory."))
        valid = False
        for mp in MountPoint.objects.all():
            if path == mp.mp_path:
                raise forms.ValidationError(_("You need to specify a file inside your volume/dataset."))
            if path.startswith(mp.mp_path):
                valid = True
        if not valid:
            raise forms.ValidationError(_("Your path to the extent must reside inside a volume/dataset mount point."))
        return path
        
    def clean_iscsi_target_extent_filesize(self):
        size = self.cleaned_data['iscsi_target_extent_filesize']
        try:
            int(size)
        except ValueError:
            suffixes = ['KB', 'MB', 'GB', 'TB']
            for x in suffixes:
                if size.upper().endswith(x):
                    m = re.match(r'(\d+)\s*?(%s)' % x, size)
                    if m:
                        return "%s%s" % (m.group(1), m.group(2))
            raise forms.ValidationError(_("This value can be a size in bytes, or can be postfixed with KB, MB, GB, TB"))
        return size
    def save(self, commit=True):
        oExtent = super(iSCSITargetFileExtentForm, self).save(commit=False)
        oExtent.iscsi_target_extent_type = 'File'
        if commit:
            oExtent.save()
        path = self.cleaned_data["iscsi_target_extent_path"]
        dirs = "/".join(path.split("/")[:-1])
        if not os.path.exists(dirs):
            try:
                os.makedirs(dirs)
            except Exception, e:
                pass
        started = notifier().reload("iscsitarget")
        if started is False and models.services.objects.get(srv_service='iscsitarget').srv_enable:
            raise ServiceFailed("iscsitarget", _("The iSCSI service failed to reload."))
        return oExtent

class iSCSITargetDeviceExtentForm(ModelForm):
    iscsi_extent_disk = forms.ChoiceField(choices=(), 
            widget=forms.Select(attrs=attrs_dict), label = _('Disk device'))
    def __init__(self, *args, **kwargs):
        super(iSCSITargetDeviceExtentForm, self).__init__(*args, **kwargs)
        self.fields['iscsi_extent_disk'].choices = self._populate_disk_choices()
        self.fields['iscsi_extent_disk'].choices.sort()
    # TODO: This is largely the same with disk wizard.
    def _populate_disk_choices(self):
        from os import popen
        import re
    
        diskchoices = dict()
    
        extents = [i[0] for i in models.iSCSITargetExtent.objects.values_list('iscsi_target_extent_path')]
        for volume in Volume.objects.filter(vol_fstype__exact='ZFS'):
            zvols = notifier().list_zfs_vols(volume.vol_name)
            for zvol, attrs in zvols.items():
                if "/dev/zvol/"+zvol not in extents:
                    diskchoices["zvol/"+zvol] = "%s (%s)" % (zvol, attrs['available'])
        # Grab disk list
        # NOTE: This approach may fail if device nodes are not accessible.
        pipe = popen("/usr/sbin/diskinfo ` /sbin/sysctl -n kern.disks` | /usr/bin/cut -f1,3")
        diskinfo = pipe.read().strip().split('\n')
        for disk in diskinfo:
            devname, capacity = disk.split('\t')
            capacity = int(capacity)
            if capacity >= 1099511627776:
                    capacity = "%.1f TiB" % (capacity / 1099511627776.0)
            elif capacity >= 1073741824:
                    capacity = "%.1f GiB" % (capacity / 1073741824.0)
            elif capacity >= 1048576:
                    capacity = "%.1f MiB" % (capacity / 1048576.0)
            else:
                    capacity = "%d Bytes" % (capacity)
            diskchoices[devname] = "%s (%s)" % (devname, capacity)
        # Exclude the root device
        rootdev = popen("""glabel status | grep `mount | awk '$3 == "/" {print $1}' | sed -e 's/\/dev\///'` | awk '{print $3}'""").read().strip()
        rootdev_base = re.search('[a-z/]*[0-9]*', rootdev)
        if rootdev_base != None:
            try:
                del diskchoices[rootdev_base.group(0)]
            except:
                pass
        # Exclude what's already added
        for devname in [ x['disk_disks'] for x in Disk.objects.all().values('disk_disks')]:
            try:
                del diskchoices[devname]
            except:
                pass
        return diskchoices.items()
    class Meta:
        model = models.iSCSITargetExtent
        exclude = ('iscsi_target_extent_type', 'iscsi_target_extent_path', 'iscsi_target_extent_filesize')
    def save(self, commit=True):
        oExtent = super(iSCSITargetDeviceExtentForm, self).save(commit=False)
        oExtent.iscsi_target_extent_type = 'Disk'
        oExtent.iscsi_target_extent_filesize = 0
        oExtent.iscsi_target_extent_path = '/dev/' + self.cleaned_data["iscsi_extent_disk"]
        if commit:
            oExtent.save()
            # Construct a corresponding volume.
            volume_name = 'iscsi:' + self.cleaned_data["iscsi_extent_disk"]
            volume_fstype = 'iscsi'

            volume = Volume(vol_name = volume_name, vol_fstype = volume_fstype)
            volume.save()

            mp = MountPoint(mp_volume=volume, mp_path=volume_name, mp_options='noauto')
            mp.save()

            grp = DiskGroup(group_name= volume_name, group_type = 'raw', group_volume = volume)
            grp.save()

            diskobj = Disk(disk_name = self.cleaned_data["iscsi_extent_disk"],
                           disk_disks = self.cleaned_data["iscsi_extent_disk"],
                           disk_description = 'iSCSI exported disk',
                           disk_group = grp)
            diskobj.save()
        started = notifier().reload("iscsitarget")
        if started is False and models.services.objects.get(srv_service='iscsitarget').srv_enable:
            raise ServiceFailed("iscsitarget", _("The iSCSI service failed to reload."))
        return oExtent

class iSCSITargetPortalForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(iSCSITargetPortalForm, self).__init__(*args, **kwargs)
        self.fields["iscsi_target_portal_tag"].initial = models.iSCSITargetPortal.objects.all().count() + 1
    class Meta:
        model = models.iSCSITargetPortal
        widgets = {
            'iscsi_target_portal_tag': forms.widgets.HiddenInput(),
        }
    def clean_iscsi_target_portal_tag(self):
        tag = self.cleaned_data["iscsi_target_portal_tag"]
        higher = models.iSCSITargetPortal.objects.all().count() + 1
        if tag > higher:
            raise forms.ValidationError(_("Your Portal Group ID cannot be higher than %d") % higher)
        return tag
    def save(self):
        super(iSCSITargetPortalForm, self).save()
        started = notifier().reload("iscsitarget")
        if started is False and models.services.objects.get(srv_service='iscsitarget').srv_enable:
            raise ServiceFailed("iscsitarget", _("The iSCSI service failed to reload."))

class iSCSITargetAuthorizedInitiatorForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(iSCSITargetAuthorizedInitiatorForm, self).__init__(*args, **kwargs)
        self.fields["iscsi_target_initiator_tag"].initial = models.iSCSITargetAuthorizedInitiator.objects.all().count() + 1
    class Meta:
        model = models.iSCSITargetAuthorizedInitiator
        widgets = {
            'iscsi_target_initiator_tag': forms.widgets.HiddenInput(),
        }
    def clean_iscsi_target_initiator_tag(self):
        tag = self.cleaned_data["iscsi_target_initiator_tag"]
        higher = models.iSCSITargetPortal.objects.all().count() + 1
        if tag > higher:
            raise forms.ValidationError(_("Your Group ID cannot be higher than %d") % higher)
        return tag
    def save(self):
        super(iSCSITargetAuthorizedInitiatorForm, self).save()
        started = notifier().reload("iscsitarget")
        if started is False and models.services.objects.get(srv_service='iscsitarget').srv_enable:
            raise ServiceFailed("iscsitarget", _("The iSCSI service failed to reload."))

class iSCSITargetForm(ModelForm):
    iscsi_target_authgroup = forms.ChoiceField(label=_("Authentication Group number"))
    class Meta:
        model = models.iSCSITarget
        exclude = ('iscsi_target_initialdigest',)
    def __init__(self, *args, **kwargs):
        super(iSCSITargetForm, self).__init__(*args, **kwargs)
        self.fields['iscsi_target_authgroup'].required = False
        self.fields['iscsi_target_authgroup'].choices = [(-1, _('None'))] + [(i['iscsi_target_auth_tag'], i['iscsi_target_auth_tag']) for i in models.iSCSITargetAuthCredential.objects.all().values('iscsi_target_auth_tag').distinct()]

    def clean_iscsi_target_authgroup(self):
        method = self.cleaned_data['iscsi_target_authtype']
        group = self.cleaned_data['iscsi_target_authgroup']
        if method in ('CHAP', 'CHAP Mutual'):
            if group != '' and int(group) == -1:
                raise forms.ValidationError(_("This field is required."))
        elif group != '' and int(group) == -1:
            return None
        return int(group)

    def clean_iscsi_target_alias(self):
        alias = self.cleaned_data['iscsi_target_alias']
        if not alias:
            alias = None
        return alias

    def save(self):
        super(iSCSITargetForm, self).save()
        started = notifier().reload("iscsitarget")
        if started is False and models.services.objects.get(srv_service='iscsitarget').srv_enable:
            raise ServiceFailed("iscsitarget", _("The iSCSI service failed to reload."))

class ExtentDelete(Form):

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)
        super(ExtentDelete, self).__init__(*args, **kwargs)

    delete = forms.BooleanField(label=_("Delete underlying file"), initial=False)

    def done(self):
        if self.cleaned_data['delete'] and \
            self.instance.iscsi_target_extent_type == 'File':
            os.system("rm \"%s\"" % self.instance.iscsi_target_extent_path)

class CronJobForm(ModelForm):
    cron_user = forms.ChoiceField(choices=(),
                                       widget=forms.Select(attrs=attrs_dict),
                                       label=_('User')
                                       )
    class Meta:
        model = models.CronJob
        widgets = {
            'cron_minute': CronMultiple(attrs={'numChoices': 60,'label':_("minute")}),
            'cron_hour': CronMultiple(attrs={'numChoices': 24,'label':_("hour")}),
            'cron_daymonth': CronMultiple(attrs={'numChoices': 31,'start':1,'label':_("day of month")}),
            'cron_dayweek': forms.CheckboxSelectMultiple(choices=choices.WEEKDAYS_CHOICES),
            'cron_month': forms.CheckboxSelectMultiple(choices=choices.MONTHS_CHOICES),
        }
    def __init__(self, *args, **kwargs):
        if kwargs.has_key('instance'):
            ins = kwargs.get('instance')
            ins.cron_month = ins.cron_month.replace("10", "a").replace("11", "b").replace("12", "c")
        super(CronJobForm, self).__init__(*args, **kwargs)
        from account.forms import FilteredSelectJSON
        if len(FreeNAS_Users()) > 500:
            if len(args) > 0 and isinstance(args[0], QueryDict):
                self.fields['cron_user'].choices = ((args[0]['cron_user'],args[0]['cron_user']),)
                self.fields['cron_user'].initial= args[0]['cron_user']
            self.fields['cron_user'].widget = FilteredSelectJSON(url=reverse("account_bsduser_json"))
        else:
            self.fields['cron_user'].widget = widgets.FilteringSelect()
            self.fields['cron_user'].choices = (
                                                 (x.bsdusr_username, x.bsdusr_username)
                                                      for x in FreeNAS_Users()
                                                      )
    def clean_cron_month(self):
        m = eval(self.cleaned_data.get("cron_month"))
        m = ",".join(m)
        m = m.replace("a", "10").replace("b", "11").replace("c", "12")
        return m
    def clean_cron_dayweek(self):
        w = eval(self.cleaned_data.get("cron_dayweek"))
        w = ",".join(w)
        return w
    def save(self):
        super(CronJobForm, self).save()
        started = notifier().restart("cron")

from freeadmin.forms import DirectoryBrowser
class RsyncForm(ModelForm):
    rsync_user = forms.ChoiceField(choices=(),
                                       widget=forms.Select(attrs=attrs_dict),
                                       label=_('User')
                                       )
    class Meta:
        model = models.Rsync
        widgets = {
            'rsync_path': DirectoryBrowser(),
            'rsync_minute': CronMultiple(attrs={'numChoices': 60,'label':_("minute")}),
            'rsync_hour': CronMultiple(attrs={'numChoices': 24,'label':_("hour")}),
            'rsync_daymonth': CronMultiple(attrs={'numChoices': 31,'start':1,'label':_("day of month")}),
            'rsync_dayweek': forms.CheckboxSelectMultiple(choices=choices.WEEKDAYS_CHOICES),
            'rsync_month': forms.CheckboxSelectMultiple(choices=choices.MONTHS_CHOICES),
        }
    def __init__(self, *args, **kwargs):
        if kwargs.has_key('instance'):
            ins = kwargs.get('instance')
            ins.rsync_month = ins.rsync_month.replace("10", "a").replace("11", "b").replace("12", "c")
        super(RsyncForm, self).__init__(*args, **kwargs)
        from account.forms import FilteredSelectJSON
        if len(FreeNAS_Users()) > 500:
            if len(args) > 0 and isinstance(args[0], QueryDict):
                self.fields['rsync_user'].choices = ((args[0]['rsync_user'],args[0]['rsync_user']),)
                self.fields['rsync_user'].initial= args[0]['rsync_user']
            self.fields['rsync_user'].widget = FilteredSelectJSON(url=reverse("account_bsduser_json"))
        else:
            self.fields['rsync_user'].widget = widgets.FilteringSelect()
            self.fields['rsync_user'].choices = (
                                                 (x.bsdusr_username, x.bsdusr_username)
                                                      for x in FreeNAS_Users()
                                                      )
    def clean_rsync_month(self):
        m = eval(self.cleaned_data.get("rsync_month"))
        m = ",".join(m)
        m = m.replace("a", "10").replace("b", "11").replace("c", "12")
        return m
    def clean_rsync_dayweek(self):
        w = eval(self.cleaned_data.get("rsync_dayweek"))
        w = ",".join(w)
        return w
    def save(self):
        super(RsyncForm, self).save()
        started = notifier().restart("cron")
