# Copyright 2010-2011 iXsystems, Inc.
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

from django.contrib.auth import authenticate
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.http import QueryDict

from dojango import forms
from freenasUI.account import models
from freenasUI.common.forms import ModelForm, Form
from freenasUI.common.pipesubr import pipeopen
from freenasUI.freeadmin.forms import SelectMultipleField
from freenasUI.storage.widgets import UnixPermissionField
from freenasUI.middleware.notifier import notifier

log = logging.getLogger('account.forms')


class NewPasswordForm(Form):

    def __init__(self, request=None, *args, **kwargs):
        super(NewPasswordForm, self).__init__(*args, **kwargs)

    password = forms.CharField(
        label=_('New Password'),
        widget=forms.widgets.PasswordInput(),
    )

    confirm_password = forms.CharField(
        label=_('Confirm New Password'),
        widget=forms.widgets.PasswordInput(),
    )

    def clean_confirm_password(self):
        p1 = self.cleaned_data.get('password')
        p2 = self.cleaned_data.get('confirm_password')
        if p1 != p2:
            raise forms.ValidationError(_('Passwords do not match'))

    def get_user(self):
        return self.user_cache

    def is_valid(self):
        valid = super(NewPasswordForm, self).is_valid()
        if valid:
            qs = models.bsdUsers.objects.filter(
                bsdusr_uid=0, bsdusr_unixhash='*'
            )
            if qs.exists():
                user = qs[0]
                user.set_password(
                    self.cleaned_data['password'].encode('utf-8'),
                )
                user.save()
                self.user_cache = authenticate(
                    username=user.bsdusr_username,
                    password=self.cleaned_data['password'].encode('utf-8'),
                )
                notifier().reload("user")
        return valid


class bsdUserGroupMixin:
    def _populate_shell_choices(self):
        with open('/etc/shells') as fd:
            shells = map(str.rstrip,
                         filter(lambda x: x.startswith('/'), fd.readlines()))
        shell_dict = {}
        for shell in shells + ['/sbin/nologin']:
            shell_dict[shell] = os.path.basename(shell)
        return shell_dict.items()

    def pw_checkname(self, bsdusr_username):
        if bsdusr_username.startswith('-'):
            raise forms.ValidationError(_("Your name cannot start with \"-\""))
        if bsdusr_username.find('$') not in (-1, len(bsdusr_username) - 1):
            raise forms.ValidationError(
                _("The character $ is only allowed as the final character")
            )
        INVALID_CHARS = ' ,\t:+&#%\^()!@~\*?<>=|\\/"'
        invalids = []
        for char in bsdusr_username:
            # INVALID_CHARS nor 8-bit characters are allowed
            if (
                char in INVALID_CHARS and char not in invalids
            ) or ord(char) & 0x80:
                invalids.append(char)
        if invalids:
            raise forms.ValidationError(
                _("Your name contains invalid characters (%s).") % (
                    ", ".join(invalids),
                ))

    def pw_checkfullname(self, name):
        INVALID_CHARS = ':'
        invalids = []
        for char in name:
            if char in INVALID_CHARS and char not in invalids:
                invalids.append(char)
        if invalids:
            raise forms.ValidationError(
                _("Your full name contains invalid characters (%s).") % (
                    ", ".join(invalids),
                ))


class FilteredSelectJSON(forms.widgets.ComboBox):
#class FilteredSelectJSON(forms.widgets.FilteringSelect):

    def __init__(self, attrs=None, choices=(), url=None):
        if url is None:
            url = []
        self.url = url
        super(FilteredSelectJSON, self).__init__(attrs, choices)

    def render(self, name, value, attrs={}, choices=()):
        self.url = reverse(*self.url)
        store = 'state' + attrs['id']
        attrs.update({
            'store': store,
            'searchAttr': 'name',
            'autoComplete': 'false',
            'intermediateChanges': 'true',
            'displayedValue': value or '',
        })
        ret = super(FilteredSelectJSON, self).render(
            name, value, attrs, choices
        )
        ret = ret.split("</select>")
        ret = "".join(ret[:-1]) + """
        <script type="dojo/method" event="onChange" args="e">
        var sel = dijit.byId("%s");
        var t = sel.get('displayedValue');
        var store = sel.store;
        store.url = store.url.split('?')[0] + '?q='+t;
        store.close();
        store.fetch();
        </script>""" % (attrs['id']) + "</select>" + ret[-1]
        ret = """
        <div dojoType="dojo.data.ItemFileReadStore" jsId="%s"
        clearOnClose="true" url="%s"></div>""" % (store, self.url) + ret
        return ret


class bsdUsersForm(ModelForm, bsdUserGroupMixin):

    bsdusr_username = forms.CharField(
        label=_("Username"),
        max_length=16)
    bsdusr_password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput,
        required=False)
    bsdusr_password2 = forms.CharField(
        label=_("Password confirmation"),
        widget=forms.PasswordInput,
        help_text=_("Enter the same password as above, for verification."),
        required=False)
    bsdusr_group = forms.ModelChoiceField(
        label=_("Primary Group"),
        queryset=models.bsdGroups.objects.all(),
        required=False)
    bsdusr_shell = forms.ChoiceField(
        label=_("Shell"),
        initial=u'/bin/csh',
        choices=())
    bsdusr_creategroup = forms.BooleanField(
        label=_("Create a new primary group for the user"),
        required=False,
        initial=True)
    bsdusr_sshpubkey = forms.CharField(
        label=_("SSH Public Key"),
        widget=forms.Textarea,
        required=False)
    bsdusr_mode = UnixPermissionField(
        label=_('Home Directory Mode'),
        initial='755',
        required=False)
    bsdusr_to_group = SelectMultipleField(
        label=_('Auxiliary groups'),
        choices=(),
        required=False)
    advanced_fields = ['bsdusr_mode']

    class Meta:
        model = models.bsdUsers
        widgets = {
            'bsdusr_uid': forms.widgets.ValidationTextInput(),
        }
        exclude = (
            'bsdusr_unixhash',
            'bsdusr_smbhash',
            'bsdusr_group',
        )
        fields = (
            'bsdusr_uid',
            'bsdusr_username',
            'bsdusr_creategroup',
            'bsdusr_home',
            'bsdusr_mode',
            'bsdusr_shell',
            'bsdusr_full_name',
            'bsdusr_email',
            'bsdusr_password',
            'bsdusr_password2',
            'bsdusr_password_disabled',
            'bsdusr_locked',
            'bsdusr_sudo',
            'bsdusr_microsoft_account',
            'bsdusr_sshpubkey',
            'bsdusr_to_group',
        )

    def __init__(self, *args, **kwargs):
        #FIXME: Workaround for DOJO not showing select with blank values
        if len(args) > 0 and isinstance(args[0], QueryDict):
            new = args[0].copy()
            if new.get('bsdusr_group', None) == '-----':
                new['bsdusr_group'] = ''
            args = (new,) + args[1:]
        super(bsdUsersForm, self).__init__(*args, **kwargs)
        self.fields.keyOrder.remove('bsdusr_group')
        self.fields.keyOrder.insert(3, 'bsdusr_group')
        if self._api is True:
            del self.fields['bsdusr_password2']
        self.fields['bsdusr_shell'].choices = self._populate_shell_choices()
        self.fields['bsdusr_shell'].choices.sort()
        self.fields['bsdusr_to_group'].choices = [
            (x.id, x.bsdgrp_group)
            for x in models.bsdGroups.objects.all()
        ]
        self.fields['bsdusr_password_disabled'].widget.attrs['onChange'] = (
            'javascript:toggleGeneric("id_bsdusr_password_disabled", '
            '["id_bsdusr_locked", "id_bsdusr_sudo"], false);')
        self.fields['bsdusr_locked'].widget.attrs['onChange'] = (
            'javascript:toggleGeneric("id_bsdusr_locked", '
            '["id_bsdusr_password_disabled"], false);')
        self.fields['bsdusr_sudo'].widget.attrs['onChange'] = (
            'javascript:toggleGeneric("id_bsdusr_sudo", '
            '["id_bsdusr_password_disabled"], false);')

        if not self.instance.id:
            try:
                self.fields['bsdusr_uid'].initial = notifier().user_getnextuid()
            except:
                pass
            self.fields['bsdusr_home'].label = _('Create Home Directory In')
            self.fields['bsdusr_creategroup'].widget.attrs['onChange'] = (
                'javascript:toggleGeneric("id_bsdusr_creategroup", '
                '["id_bsdusr_group"], false);')
            self.fields['bsdusr_group'].widget.attrs['maxHeight'] = 200
            self.fields['bsdusr_group'].widget.attrs['disabled'] = 'disabled'
            self.fields['bsdusr_group'].choices = (
                ('-----', '-----'),
            ) + tuple(
                [x for x in self.fields['bsdusr_group'].choices][1:]
            )
            self.fields['bsdusr_group'].required = False
            self.bsdusr_home_saved = '/nonexistent'
            self.bsdusr_home_copy = False

        elif self.instance.id:
            self.fields['bsdusr_to_group'].initial = [
                x.bsdgrpmember_group.id
                for x in models.bsdGroupMembership.objects.filter(
                    bsdgrpmember_user=self.instance.id
                )
            ]

            del self.fields['bsdusr_creategroup']
            self.fields['bsdusr_group'].initial = self.instance.bsdusr_group
            self.advanced_fields = []
            self.bsdusr_home_saved = self.instance.bsdusr_home.encode('utf8')
            self.bsdusr_home_copy = False
            self.fields.keyOrder.remove('bsdusr_mode')
            self.fields.keyOrder.insert(
                len(self.fields.keyOrder) - 1,
                'bsdusr_mode',
            )
            self.fields['bsdusr_username'].widget.attrs['readonly'] = True
            self.fields['bsdusr_username'].widget.attrs['class'] = (
                'dijitDisabled dijitTextBoxDisabled '
                'dijitValidationTextBoxDisabled')
            if os.path.exists(self.instance.bsdusr_home.encode('utf8')):
                mode = os.stat(self.instance.bsdusr_home.encode('utf8')).st_mode & 0o777
                self.fields['bsdusr_mode'].initial = oct(mode)
            if self.instance.bsdusr_builtin:
                self.fields['bsdusr_uid'].widget.attrs['readonly'] = True
                self.fields['bsdusr_uid'].widget.attrs['class'] = (
                    'dijitDisabled dijitTextBoxDisabled '
                    'dijitValidationTextBoxDisabled'
                )
                self.fields['bsdusr_group'].widget.attrs['readonly'] = True
                self.fields['bsdusr_group'].widget.attrs['class'] = (
                    'dijitDisabled dijitSelectDisabled')
                self.fields['bsdusr_home'].widget.attrs['readonly'] = True
                self.fields['bsdusr_home'].widget.attrs['class'] = (
                    'dijitDisabled dijitTextBoxDisabled '
                    'dijitValidationTextBoxDisabled'
                )
                self.fields['bsdusr_mode'].widget.attrs['disabled'] = True
                self.fields['bsdusr_mode'].required = False
            if self.instance.bsdusr_locked or self.instance.bsdusr_sudo:
                self.fields['bsdusr_password_disabled'].widget.attrs[
                    'disabled'
                ] = True
            if self.instance.bsdusr_password_disabled is True:
                self.fields['bsdusr_locked'].widget.attrs['disabled'] = True
                self.fields['bsdusr_sudo'].widget.attrs['disabled'] = True
            self.fields['bsdusr_sshpubkey'].initial = (
                self.instance.bsdusr_sshpubkey
            )

    def clean_bsdusr_username(self):
        if self.instance.id is None:
            bsdusr_username = self.cleaned_data["bsdusr_username"]
            self.pw_checkname(bsdusr_username)
            try:
                models.bsdUsers.objects.get(bsdusr_username=bsdusr_username)
            except models.bsdUsers.DoesNotExist:
                return bsdusr_username
            raise forms.ValidationError(
                _("A user with that username already exists.")
            )
        else:
            return self.instance.bsdusr_username

    def clean_bsdusr_uid(self):
        if self.instance.id and self.instance.bsdusr_builtin:
            return self.instance.bsdusr_uid
        else:
            return self.cleaned_data.get("bsdusr_uid")

    def clean_bsdusr_group(self):
        if self.instance.id and self.instance.bsdusr_builtin:
            return self.instance.bsdusr_group
        else:
            create = self.cleaned_data.get("bsdusr_creategroup")
            group = self.cleaned_data.get("bsdusr_group")
            if not group and not create:
                raise forms.ValidationError(_("This field is required"))
            return group

    def clean_bsdusr_password(self):
        bsdusr_password = self.cleaned_data.get('bsdusr_password')
        # See bug #4098
        if bsdusr_password and '?' in bsdusr_password:
            raise forms.ValidationError(_(
                'Passwords containing a question mark (?) are currently not '
                'allowed due to problems with SMB.'
            ))
        return bsdusr_password

    def clean_bsdusr_password2(self):
        bsdusr_password = self.cleaned_data.get("bsdusr_password", "")
        bsdusr_password2 = self.cleaned_data["bsdusr_password2"]
        if bsdusr_password and bsdusr_password != bsdusr_password2:
            raise forms.ValidationError(
                _("The two password fields didn't match.")
            )
        return bsdusr_password2

    def clean_bsdusr_home(self):
        home = self.cleaned_data['bsdusr_home']
        if self.instance.id and self.instance.bsdusr_uid == 0:
            return self.instance.bsdusr_home
        elif home is not None:
            if ':' in home:
                raise forms.ValidationError(
                    _("Home directory cannot contain colons")
                )

            if home == u'/nonexistent':
                return home

            if home.startswith(u'/mnt/'):
                bsdusr_username = self.cleaned_data.get('bsdusr_username', '')
                saved_home = self.bsdusr_home_saved

                if home.endswith(bsdusr_username):
                    if self.instance.id and home != saved_home:
                        self.bsdusr_home_copy = True
                    return home

                if not self.instance.id:
                    home = "%s/%s" % (home.rstrip('/'), bsdusr_username)

                if not self.instance.id and not home.endswith(bsdusr_username):
                    raise forms.ValidationError(
                        _('Home directory must end with username')
                    )

                if self.instance.id and home != saved_home:
                    self.bsdusr_home_copy = True

                return home

        raise forms.ValidationError(
            _('Home directory has to start with /mnt/ or be /nonexistent')
        )

    def clean_bsdusr_mode(self):
        mode = self.cleaned_data.get('bsdusr_mode')
        if not self.instance.id and not mode:
            return '755'
        return mode

    def clean_bsdusr_sshpubkey(self):
        ssh = self.cleaned_data.get('bsdusr_sshpubkey', '')
        ssh = ssh.strip(' ').strip('\n')
        ssh = re.sub(r'[ ]{2,}', ' ', ssh, re.M)
        ssh = re.sub(r'\n{2,}', '\n', ssh, re.M)
        old = ssh
        while True:
            ssh = re.sub(r'(\S{15,})\n(\S{15,})', '\\1\\2', ssh, re.M)
            if ssh == old:
                break
            old = ssh
        return ssh

    def clean_bsdusr_full_name(self):
        name = self.cleaned_data["bsdusr_full_name"]
        self.pw_checkfullname(name)
        return name

    def clean_bsdusr_to_group(self):
        v = self.cleaned_data.get("bsdusr_to_group")
        if len(v) > 64:
            raise forms.ValidationError(
                _("A user cannot belong to more than 64 auxiliary groups"))
        return v

    def clean(self):
        cleaned_data = self.cleaned_data

        password_disable = cleaned_data["bsdusr_password_disabled"] = (
            cleaned_data.get("bsdusr_password_disabled", False)
        )
        bsdusr_home = cleaned_data.get('bsdusr_home', '')
        if (
            bsdusr_home and cleaned_data.get('bsdusr_sshpubkey') and
            (
                not bsdusr_home.startswith(u'/mnt/') and (
                    self.instance.id is None or
                    (self.instance.id and self.instance.bsdusr_uid != 0)
                )
            )
        ):
            del cleaned_data['bsdusr_sshpubkey']
            self._errors['bsdusr_sshpubkey'] = self.error_class([
                _("Home directory is not writable, leave this blank")])
        if self.instance.id is None:
            FIELDS = ['bsdusr_password', 'bsdusr_password2']
            if password_disable:
                for field in FIELDS:
                    if field in cleaned_data and cleaned_data.get(field) != '':
                        self._errors[field] = self.error_class([
                            _("Password is disabled, leave this blank")])
                        del cleaned_data[field]
            else:
                for field in FIELDS:
                    if field in cleaned_data and cleaned_data.get(field) == '':
                        self._errors[field] = self.error_class([
                            _("This field is required.")])
                        del cleaned_data[field]

        return cleaned_data

    def save(self, commit=True):
        _notifier = notifier()
        if self.instance.id is None:
            group = self.cleaned_data['bsdusr_group']
            if group is None:
                try:
                    gid = models.bsdGroups.objects.get(
                        bsdgrp_group=self.cleaned_data['bsdusr_username']
                    ).bsdgrp_gid
                except:
                    gid = -1
            else:
                gid = group.bsdgrp_gid
            uid, gid, unixhash, smbhash = _notifier.user_create(
                username=self.cleaned_data['bsdusr_username'].encode(
                    'utf8', 'ignore'
                ),
                fullname=self.cleaned_data['bsdusr_full_name'].encode(
                    'utf8', 'ignore'
                ).replace(':', ''),
                password=self.cleaned_data['bsdusr_password'].encode(
                    'utf8', 'ignore'
                ),
                uid=self.cleaned_data['bsdusr_uid'],
                gid=gid,
                shell=str(self.cleaned_data['bsdusr_shell']),
                homedir=self.cleaned_data['bsdusr_home'].encode('utf8'),
                homedir_mode=int(
                    self.cleaned_data.get('bsdusr_mode', '755'),
                    8
                ),
                password_disabled=self.cleaned_data.get(
                    'bsdusr_password_disabled', False
                ),
            )
            bsduser = super(bsdUsersForm, self).save(commit=False)
            try:
                grp = models.bsdGroups.objects.get(bsdgrp_gid=gid)
            except models.bsdGroups.DoesNotExist:
                grp = models.bsdGroups(
                    bsdgrp_gid=gid,
                    bsdgrp_group=self.cleaned_data['bsdusr_username'],
                    bsdgrp_builtin=False,
                )
                grp.save()
            bsduser.bsdusr_group = grp
            bsduser.bsdusr_uid = uid
            bsduser.bsdusr_shell = self.cleaned_data['bsdusr_shell']
            bsduser.bsdusr_unixhash = unixhash
            bsduser.bsdusr_smbhash = smbhash
            bsduser.bsdusr_builtin = False
            bsduser.save()

        else:
            bsduser = super(bsdUsersForm, self).save(commit=False)
            bsduser.bsdusr_group = self.cleaned_data['bsdusr_group']
            bsduser.save()

            #
            # Check if updating password
            #
            bsdusr_password = self.cleaned_data.get("bsdusr_password", "")
            if self._api is True:
                bsdusr_password2 = bsdusr_password
            else:
                bsdusr_password2 = self.cleaned_data["bsdusr_password2"]
            if bsdusr_password and (bsdusr_password == bsdusr_password2):
                unixhash, smbhash = _notifier.user_changepassword(
                    username=bsduser.bsdusr_username.encode('utf8'),
                    password=bsdusr_password.encode('utf8'),
                )
                bsduser.bsdusr_unixhash = unixhash
                bsduser.bsdusr_smbhash = smbhash
                bsduser.save()

            homedir_mode = self.cleaned_data.get('bsdusr_mode')
            if (
                not bsduser.bsdusr_builtin and homedir_mode is not None and
                os.path.exists(bsduser.bsdusr_home.encode('utf8'))
            ):
                try:
                    homedir_mode = int(homedir_mode, 8)
                    os.chmod(bsduser.bsdusr_home.encode('utf8'), homedir_mode)
                except:
                    log.warn('Failed to set homedir mode', exc_info=True)

        #
        # Check if updating group membership
        #
        models.bsdGroupMembership.objects.filter(
            bsdgrpmember_user=bsduser
        ).delete()
        groupid_list = self.cleaned_data['bsdusr_to_group']
        for groupid in groupid_list:
            group = models.bsdGroups.objects.get(id=groupid)
            m = models.bsdGroupMembership(
                bsdgrpmember_group=group,
                bsdgrpmember_user=bsduser)
            m.save()

        _notifier.reload("user")
        if self.bsdusr_home_copy:
            p = pipeopen("su - %s -c '/bin/cp -a %s/* %s/'" % (
                self.cleaned_data['bsdusr_username'],
                self.bsdusr_home_saved,
                self.cleaned_data['bsdusr_home']
            ))
            p.communicate()

        bsdusr_sshpubkey = self.cleaned_data.get('bsdusr_sshpubkey')
        if bsdusr_sshpubkey:
            _notifier.save_pubkey(
                bsduser.bsdusr_home.encode('utf8'),
                bsdusr_sshpubkey,
                bsduser.bsdusr_username,
                bsduser.bsdusr_group.bsdgrp_group)
        else:
            _notifier.delete_pubkey(bsduser.bsdusr_home.encode('utf8'))
        return bsduser

    def delete(self, **kwargs):
        if self.data.get('nodelgroup'):
            kwargs['delete_group'] = False
        else:
            kwargs['delete_group'] = True
        super(bsdUsersForm, self).delete(**kwargs)


class bsdUserPasswordForm(ModelForm):
    bsdusr_username2 = forms.CharField(label=_("Username"), required=False)
    bsdusr_password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput,
    )
    bsdusr_password2 = forms.CharField(
        label=_("Password confirmation"),
        widget=forms.PasswordInput,
        help_text=_("Enter the same password as above, for verification."),
    )

    class Meta:
        model = models.bsdUsers
        fields = ('bsdusr_username',)
        widgets = {
            'bsdusr_username': forms.widgets.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        self._confirm = kwargs.pop('confirm', True)
        super(bsdUserPasswordForm, self).__init__(*args, **kwargs)
        self.fields['bsdusr_username'].widget.attrs['readonly'] = True
        self.fields['bsdusr_username2'].widget.attrs['disabled'] = 'disabled'
        self.fields['bsdusr_username2'].initial = self.instance.bsdusr_username
        if self._confirm is False:
            del self.fields['bsdusr_password2']

    def clean_bsdusr_username(self):
        return self.instance.bsdusr_username

    def clean_bsdusr_password2(self):
        bsdusr_password = self.cleaned_data.get("bsdusr_password", "")
        bsdusr_password2 = self.cleaned_data["bsdusr_password2"]
        if bsdusr_password != bsdusr_password2:
            raise forms.ValidationError(
                _("The two password fields didn't match.")
            )
        return bsdusr_password2

    def save(self, commit=True):
        if commit:
            _notifier = notifier()
            unixhash, smbhash = _notifier.user_changepassword(
                username=str(self.instance.bsdusr_username),
                password=str(self.cleaned_data['bsdusr_password']),
            )
            self.instance.bsdusr_unixhash = unixhash
            self.instance.bsdusr_smbhash = smbhash
            self.instance.save()
            _notifier.reload("user")
        return self.instance


class bsdUserEmailForm(ModelForm, bsdUserGroupMixin):

    class Meta:
        model = models.bsdUsers
        fields = ('bsdusr_email',)

    def save(self):
        bsduser = super(bsdUserEmailForm, self).save(commit=True)
        notifier().reload("user")
        return bsduser


class DeleteUserForm(forms.Form):

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)
        super(DeleteUserForm, self).__init__(*args, **kwargs)
        qs = models.bsdUsers.objects.filter(bsdusr_group__id=self.instance.bsdusr_group.id).exclude(id=self.instance.id)
        if not qs.exists():
            self.fields['nodelgroup'] = forms.BooleanField(
                label=_("Do not delete user primary group"),
                required=False,
                initial=False,
            )


class bsdGroupsForm(ModelForm, bsdUserGroupMixin):

    class Meta:
        fields = '__all__'
        model = models.bsdGroups
        widgets = {
            'bsdgrp_gid': forms.widgets.ValidationTextInput(),
        }

    def __init__(self, *args, **kwargs):
        super(bsdGroupsForm, self).__init__(*args, **kwargs)
        if self.instance.id:
            self.fields['bsdgrp_gid'].widget.attrs['readonly'] = True
            self.fields['bsdgrp_gid'].widget.attrs['class'] = (
                'dijitDisabled dijitTextBoxDisabled '
                'dijitValidationTextBoxDisabled'
            )
            self.instance._original_bsdgrp_group = self.instance.bsdgrp_group

        else:
            try:
                self.initial['bsdgrp_gid'] = notifier().user_getnextgid()
            except:
                pass
            self.fields['allow'] = forms.BooleanField(
                label=_("Allow repeated GIDs"),
                initial=False,
                required=False,
            )

    def clean_bsdgrp_group(self):
        bsdgrp_group = self.cleaned_data.get("bsdgrp_group")
        self.pw_checkname(bsdgrp_group)
        if self.instance.id is None:
            try:
                models.bsdGroups.objects.get(bsdgrp_group=bsdgrp_group)
            except models.bsdGroups.DoesNotExist:
                return bsdgrp_group
            raise forms.ValidationError(
                _("A group with that name already exists.")
            )
        else:
            if self.instance.bsdgrp_builtin:
                return self.instance.bsdgrp_group
            else:
                return bsdgrp_group

    def clean_bsdgrp_gid(self):
        if self.instance.id:
            return self.instance.bsdgrp_gid
        else:
            return self.cleaned_data['bsdgrp_gid']

    def clean(self):
        cdata = self.cleaned_data
        grp = cdata.get("bsdgrp_gid")
        if not cdata.get("allow", False):
            grps = models.bsdGroups.objects.filter(bsdgrp_gid=grp)
            if self.instance and self.instance.id:
                grps = grps.exclude(bsdgrp_gid=self.instance.bsdgrp_gid)
            if grps.exists():
                self._errors['bsdgrp_gid'] = self.error_class([
                    _("A group with this gid already exists"),
                ])
                cdata.pop('bsdgrp_gid', None)
        return cdata

    def save(self):
        ins = super(bsdGroupsForm, self).save()

        if self.instance and hasattr(self.instance, "_original_bsdgrp_group") and \
            self.instance._original_bsdgrp_group != self.instance.bsdgrp_group:
            notifier().groupmap_delete(ntgroup=self.instance._original_bsdgrp_group)

        notifier().groupmap_add(unixgroup=self.instance.bsdgrp_group,
            ntgroup=self.instance.bsdgrp_group)

        notifier().reload("user")
        return ins


class bsdGroupToUserForm(Form):
    bsdgroup_to_user = SelectMultipleField(
        label=_('Member users'),
        choices=(),
        required=False,
    )

    def __init__(self, groupid, *args, **kwargs):
        super(bsdGroupToUserForm, self).__init__(*args, **kwargs)
        self.groupid = groupid
        group = models.bsdGroups.objects.get(id=self.groupid)
        self.fields['bsdgroup_to_user'].choices = [
            (x.id, x.bsdusr_username) for x in models.bsdUsers.objects.all()
        ]
        self.fields['bsdgroup_to_user'].initial = [
            (x.bsdgrpmember_user.id)
            for x in models.bsdGroupMembership.objects.filter(
                bsdgrpmember_group=group
            )
        ]

    def save(self):
        group = models.bsdGroups.objects.get(id=self.groupid)
        models.bsdGroupMembership.objects.filter(
            bsdgrpmember_group=group
        ).delete()
        userid_list = self.cleaned_data['bsdgroup_to_user']
        for userid in userid_list:
            user = models.bsdUsers.objects.get(id=userid)
            m = models.bsdGroupMembership(
                bsdgrpmember_group=group,
                bsdgrpmember_user=user)
            m.save()
        notifier().reload("user")


class bsdUserToGroupForm(Form):
    bsduser_to_group = SelectMultipleField(
        label=_('Auxiliary groups'),
        choices=(),
        required=False,
    )

    def __init__(self, userid, *args, **kwargs):
        super(bsdUserToGroupForm, self).__init__(*args, **kwargs)
        self.userid = userid
        user = models.bsdUsers.objects.get(id=self.userid)
        self.fields['bsduser_to_group'].choices = [
            (x.id, x.bsdgrp_group)
            for x in models.bsdGroups.objects.all()
        ]
        self.fields['bsduser_to_group'].initial = [
            x.bsdgrpmember_group.id
            for x in models.bsdGroupMembership.objects.filter(
                bsdgrpmember_user=user
            )
        ]

    def clean_bsduser_to_group(self):
        v = self.cleaned_data.get("bsduser_to_group")
        if len(v) > 64:
            raise forms.ValidationError(
                _("A user cannot belong to more than 64 auxiliary groups")
            )
        return v

    def save(self):
        user = models.bsdUsers.objects.get(id=self.userid)
        models.bsdGroupMembership.objects.filter(
            bsdgrpmember_user=user
        ).delete()
        groupid_list = self.cleaned_data['bsduser_to_group']
        for groupid in groupid_list:
            group = models.bsdGroups.objects.get(id=groupid)
            m = models.bsdGroupMembership(
                bsdgrpmember_group=group,
                bsdgrpmember_user=user)
            m.save()
        notifier().reload("user")


class DeleteGroupForm(forms.Form):

    cascade = forms.BooleanField(
        label=_("Do you want to delete all users with this primary group?"),
        required=False,
        initial=False,
    )

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)
        super(DeleteGroupForm, self).__init__(*args, **kwargs)

    def done(self, *args, **kwargs):
        if self.cleaned_data.get("cascade") is True:
            models.bsdUsers.objects.filter(bsdusr_group=self.instance).delete()
        notifier().groupmap_delete(self.instance.bsdgrp_group)
