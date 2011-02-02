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
from freenasUI.common.forms import ModelForm, Form
from dojango import forms
from freenasUI.account.models import *
from freenasUI.middleware.notifier import notifier
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.forms import UserChangeForm as django_UCF
from django.contrib.auth.models import User as django_User

class UserChangeForm(django_UCF):
    class Meta:
        fields = ('username', 'first_name', 'last_name', 'email',)
        model = django_User
    def __init__(self, *args, **kwargs):
        super(UserChangeForm, self).__init__(*args, **kwargs)

class bsdUserCreationForm(ModelForm):
    """
    # Yanked from django/contrib/auth/
    A form that creates a user, with no privileges, from the given username and password.
    """
    bsdusr_username = forms.RegexField(label=_("Username"), max_length=30, regex=r'^[\w.@+-]+$',
        help_text = _("Required. 30 characters or fewer. Letters, digits and @/./+/-/_ only."),
        error_messages = {'invalid': _("This value may contain only letters, numbers and @/./+/-/_ characters.")})
    bsdusr_password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput)
    bsdusr_password2 = forms.CharField(label=_("Password confirmation"), widget=forms.PasswordInput,
        help_text = _("Enter the same password as above, for verification."))
    bsdusr_shell = forms.ChoiceField(label=_("Shell"), initial=u'/bin/csh', choices=())

    class Meta:
        model = bsdUsers
        exclude = ('bsdusr_unixhash','bsdusr_smbhash','bsdusr_group','bsdusr_builtin',)

    def __init__(self, *args, **kwargs):
        super(bsdUserCreationForm, self).__init__(*args, **kwargs)
        self.fields['bsdusr_shell'].choices = self._populate_shell_choices()
        self.fields['bsdusr_shell'].choices.sort()
        self.initial['bsdusr_uid'] = notifier().user_getnextuid()

    def _populate_shell_choices(self):
        from os import popen
        from os.path import basename
        import re
    
        shell_dict = {}
        shells = popen("grep ^/ /etc/shells").read().split('\n')
        for shell in shells:
            shell_dict[shell] = basename(shell)
        return shell_dict.items()

    def clean_bsdusr_username(self):
        bsdusr_username = self.cleaned_data["bsdusr_username"]
        try:
            bsdUsers.objects.get(bsdusr_username=bsdusr_username)
        except bsdUsers.DoesNotExist:
            return bsdusr_username
        raise forms.ValidationError(_("A user with that username already exists."))

    def clean_bsdusr_password2(self):
        bsdusr_password1 = self.cleaned_data.get("bsdusr_password1", "")
        bsdusr_password2 = self.cleaned_data["bsdusr_password2"]
        if bsdusr_password1 != bsdusr_password2:
            raise forms.ValidationError(_("The two password fields didn't match."))
        return bsdusr_password2

    def save(self, commit=True):
        if commit:
            uid, gid, unixhash, smbhash = notifier().user_create(
                username = self.cleaned_data['bsdusr_username'].__str__(),
                fullname = self.cleaned_data['bsdusr_full_name'].__str__(),
                password = self.cleaned_data['bsdusr_password2'].__str__(),
                uid = self.cleaned_data['bsdusr_uid'],
                shell = self.cleaned_data['bsdusr_shell'].__str__(),
                homedir = self.cleaned_data['bsdusr_home'].__str__(),
            )
            bsduser = super(bsdUserCreationForm, self).save(commit=False)
            try:
                grp = bsdGroups.objects.get(bsdgrp_gid=gid)
            except bsdGroups.DoesNotExist:
                grp = bsdGroups(bsdgrp_gid=gid, bsdgrp_group=self.cleaned_data['bsdusr_username'], bsdgrp_builtin=False)
                grp.save()
            bsduser.bsdusr_group=grp
            bsduser.bsdusr_uid=uid
            bsduser.bsdusr_shell=self.cleaned_data['bsdusr_shell']
            bsduser.bsdusr_unixhash=unixhash
            bsduser.bsdusr_smbhash=smbhash
            bsduser.bsdusr_builtin=False
            bsduser.save()
        return bsduser

class bsdUserPasswordForm(ModelForm):
    bsdusr_password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput)
    bsdusr_password2 = forms.CharField(label=_("Password confirmation"), widget=forms.PasswordInput,
        help_text = _("Enter the same password as above, for verification."))

    class Meta:
        model = bsdUsers
        fields = ('bsdusr_username',)

    def __init__(self, *args, **kwargs):
        super(bsdUserPasswordForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.id:
            self.fields['bsdusr_username'].widget.attrs['readonly'] = True

    def clean_bsdusr_username(self):
        return self.instance.bsdusr_username

    def clean_bsdusr_password2(self):
        bsdusr_password1 = self.cleaned_data.get("bsdusr_password1", "")
        bsdusr_password2 = self.cleaned_data["bsdusr_password2"]
        if bsdusr_password1 != bsdusr_password2:
            raise forms.ValidationError(_("The two password fields didn't match."))
        return bsdusr_password2

    def save(self, commit=True):
        if commit:
            unixhash, smbhash = notifier().user_changepassword(
                username = self.instance.bsdusr_username.__str__(),
                password = self.cleaned_data['bsdusr_password2'].__str__(),
            )
            self.instance.bsdusr_unixhash=unixhash
            self.instance.bsdusr_smbhash=smbhash
            self.instance.save()
            notifier().reload("user")
        return self.instance

class bsdUserChangeForm(ModelForm):
    class Meta:
        model = bsdUsers
        exclude = ('bsdusr_unixhash', 'bsdusr_smbhash', 'bsdusr_builtin',)
    def __init__(self, *args, **kwargs):
        super(bsdUserChangeForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.id:
            self.fields['bsdusr_username'].widget.attrs['readonly'] = True

    def clean_bsdusr_username(self):
        return self.instance.bsdusr_username

    def save(self):
        super(bsdUserChangeForm, self).save()
        notifier().reload("user")
        return self.instance

class bsdGroupsForm(ModelForm):
    class Meta:
        model = bsdGroups
        exclude = ('bsdgrp_builtin',)
    def __init__(self, *args, **kwargs):
        super(bsdGroupsForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.id:
            self.fields['bsdgrp_gid'].widget.attrs['readonly'] = True
        else:
            self.initial['bsdgrp_gid'] = notifier().user_getnextgid()

    def clean_bsdgrp_gid(self):
        instance = getattr(self, 'instance', None)
        if instance and instance.id:
            return self.instance.bsdgrp_gid
        else:
            return self.cleaned_data['bsdgrp_gid']

    def save(self):
        super(bsdGroupsForm, self).save()
        notifier().reload("user")
        return self.instance

attrs_dict = { 'class': 'required' }

class bsdGroupToUserForm(Form):
    bsdgroup_to_user = forms.MultipleChoiceField(choices=(), widget=forms.SelectMultiple(attrs=attrs_dict), label = 'Member users')
    def __init__(self, groupid, *args, **kwargs):
        super(bsdGroupToUserForm, self).__init__(*args, **kwargs)
        self.groupid = groupid
        group = bsdGroups.objects.get(id=self.groupid)
        self.fields['bsdgroup_to_user'].choices = [(x.id, x.bsdusr_username) for x in bsdUsers.objects.all()]
        self.fields['bsdgroup_to_user'].initial = [(x.bsdgrpmember_user.id) for x in bsdGroupMembership.objects.filter(bsdgrpmember_group=group)]
    def save(self):
        group = bsdGroups.objects.get(id=self.groupid)
        bsdGroupMembership.objects.filter(bsdgrpmember_group=group).delete()
        userid_list = self.cleaned_data['bsdgroup_to_user']
        for userid in userid_list:
            user = bsdUsers.objects.get(id=userid)
            m = bsdGroupMembership(bsdgrpmember_group=group, bsdgrpmember_user=user)
            m.save()
        notifier().reload("user")

class bsdUserToGroupForm(Form):
    bsduser_to_group = forms.MultipleChoiceField(choices=(), widget=forms.SelectMultiple(attrs=attrs_dict), label = 'Auxilary groups')
    def __init__(self, userid, *args, **kwargs):
        super(bsdUserToGroupForm, self).__init__(*args, **kwargs)
        self.userid = userid
        user = bsdUsers.objects.get(id=self.userid)
        self.fields['bsduser_to_group'].choices = [(x.id, x.bsdgrp_group) for x in bsdGroups.objects.all()]
        self.fields['bsduser_to_group'].initial = [(x.bsdgrpmember_group.id) for x in bsdGroupMembership.objects.filter(bsdgrpmember_user=user)]
    def save(self):
        user = bsdUsers.objects.get(id=self.userid)
        bsdGroupMembership.objects.filter(bsdgrpmember_user=user).delete()
        groupid_list = self.cleaned_data['bsduser_to_group']
        for groupid in groupid_list:
            group = bsdGroups.objects.get(id=groupid)
            m = bsdGroupMembership(bsdgrpmember_group=group, bsdgrpmember_user=user)
            m.save()
        notifier().reload("user")

