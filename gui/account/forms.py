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
from freenasUI.common.freenassysctl import freenas_sysctl as _fs
from freenasUI.freeadmin.forms import SelectMultipleField
from freenasUI.freeadmin.utils import key_order
from freenasUI.storage.widgets import UnixPermissionField
from freenasUI.middleware.client import client
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
                user.set_password(self.cleaned_data['password'])
                user.save()
                self.user_cache = authenticate(
                    username=user.bsdusr_username,
                    password=self.cleaned_data['password'],
                )

                #
                # XXX hackity hackness XXX
                # Catch call timeout exceptions. We should really return this to the user
                # in the UI, but there is no easy way to currently do this. For now this
                # prevents a stack trace in the UI, which is slightly better than nothing ;-)
                # This same try/except structure is littered throughout this code.
                #
                try:
                    notifier().reload("user", timeout=_fs().account.user.timeout.reload)
                except Exception as e:
                    log.debug("ERROR: failed to reload user: %s", e)

        return valid


class bsdUserGroupMixin:

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


class FilteredSelectJSON(forms.widgets.ComboBox):
#class FilteredSelectJSON(forms.widgets.FilteringSelect):

    def __init__(self, attrs=None, choices=(), url=None):
        if url is None:
            url = []
        self.url = url
        super(FilteredSelectJSON, self).__init__(attrs, choices)

    def render(self, name, value, attrs=None):
        if attrs is None:
            attrs = {}
        self.url = reverse(*self.url)
        store = 'state' + attrs['id']
        attrs.update({
            'store': store,
            'searchAttr': 'name',
            'autoComplete': 'false',
            'intermediateChanges': 'true',
            'displayedValue': value or '',
        })
        ret = super(FilteredSelectJSON, self).render(name, value, attrs)
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
        key_order(self, 3, 'bsdusr_group', instance=True)
        if self._api is True:
            del self.fields['bsdusr_password2']
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
            self.bsdusr_home_saved = self.instance.bsdusr_home
            key_order(self, len(self.fields) - 1, 'bsdusr_mode', instance=True)
            self.fields['bsdusr_username'].widget.attrs['readonly'] = True
            self.fields['bsdusr_username'].widget.attrs['class'] = (
                'dijitDisabled dijitTextBoxDisabled '
                'dijitValidationTextBoxDisabled')
            if os.path.exists(self.instance.bsdusr_home):
                mode = os.stat(self.instance.bsdusr_home).st_mode & 0o777
                self.fields['bsdusr_mode'].initial = oct(mode)[2:]
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
        if home is not None:
            if home == '/nonexistent':
                return home

            if home.startswith('/mnt/'):
                bsdusr_username = self.cleaned_data.get('bsdusr_username', '')

                if home.endswith(bsdusr_username):
                    return home

                if not self.instance.id:
                    home = "%s/%s" % (home.rstrip('/'), bsdusr_username)

                if not self.instance.id and not home.endswith(bsdusr_username):
                    raise forms.ValidationError(
                        _('Home directory must end with username')
                    )

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
            ssh = re.sub(r'(\S{20,})\n(\S{20,})', '\\1\\2', ssh, re.M)
            if ssh == old:
                break
            old = ssh
        return ssh

    def save(self, *args, **kwargs):
        data = self.cleaned_data.copy()

        if self.instance.id is None:
            args = ['user.create']
            data['group_create'] = data.pop('creategroup', False)
        else:
            args = ['user.update', self.instance.id]

        # Convert attributes to new middleware API
        for k in list(data.keys()):
            if k.startswith('bsdusr_'):
                data[k[len('bsdusr_'):]] = data.pop(k)

        data.pop('password2', None)
        data['home_mode'] = data.pop('mode')
        if data['group']:
            data['group'] = data['group'].id
        else:
            data.pop('group')
        data['groups'] = [int(group) for group in data.pop('to_group', [])]

        with client as c:
            pk = c.call(*args, data)

        return models.bsdUsers.objects.get(pk=pk)

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

    def save(self, *args, **kwargs):
        with client as c:
            pk = c.call('user.update', self.instance.id, {
                'password': self.cleaned_data['bsdusr_password'],
            })
        return models.bsdUsers.objects.get(pk=pk)


class bsdUserEmailForm(ModelForm, bsdUserGroupMixin):

    class Meta:
        model = models.bsdUsers
        fields = ('bsdusr_email',)

    def save(self):
        bsduser = super(bsdUserEmailForm, self).save(commit=True)
        try:
            notifier().reload("user", timeout=_fs().account.user.timeout.reload)
        except Exception as e:
            log.debug("ERROR: failed to reload user: %s", e)
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

        try:
            notifier().reload("user", timeout=_fs().account.user.timeout.reload)
        except Exception as e:
            log.debug("ERROR: failed to reload user: %s", e)
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
        try:
            notifier().reload("user", timeout=_fs().account.user.timeout.reload)
        except Exception as e:
            log.debug("ERROR: failed to reload user: %s", e)


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
        try:
            notifier().reload("user", timeout=_fs().account.user.timeout.reload)
        except Exception as e:
            log.debug("ERROR: failed to reload user: %s", e)


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
