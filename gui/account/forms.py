#+
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
# $FreeBSD$
#####################################################################
import os

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User as django_User
from django.utils.safestring import mark_safe
from django.http import QueryDict

from freenasUI.common.forms import ModelForm, Form
from freenasUI.account import models
from freenasUI.middleware.notifier import notifier
from dojango import forms

class bsdUserGroupMixin:
    def _populate_shell_choices(self):
        with open('/etc/shells') as fd:
            shells = map(str.rstrip,
                         filter(lambda x: x.startswith('/'), fd.readlines()))
        shell_dict = {}
        for shell in shells + [ '/sbin/nologin' ]:
            shell_dict[shell] = os.path.basename(shell)
        return shell_dict.items()

    def pw_checkname(self, bsdusr_username):
        if bsdusr_username.startswith('-'):
            raise forms.ValidationError(_("Your name cannot start with \"-\""))
        if bsdusr_username.find('$') not in (-1, len(bsdusr_username) - 1):
            raise forms.ValidationError(_("The character $ is only allowed as the final character"))
        INVALID_CHARS = ' ,\t:+&#%\^()!@~\*?<>=|\\/"'
        invalids = []
        for char in bsdusr_username:
            if char in INVALID_CHARS and char not in invalids:
                invalids.append(char)
        if invalids:
            raise forms.ValidationError(_("Your name contains invalid characters (%s).") % ", ".join(invalids))

class FilteredSelectJSON(forms.widgets.ComboBox):
#class FilteredSelectJSON(forms.widgets.FilteringSelect):

    def __init__(self, attrs=None, choices=(), url=None):
        if url is None:
            url = []
        self.url = url
        super(FilteredSelectJSON, self).__init__(attrs, choices)

    def render(self, name, value, attrs={}, choices=()):
        self.url = reverse(*self.url)
        store = 'state'+attrs['id']
        attrs.update({
            'store': store,
            'searchAttr': 'name',
            'autoComplete': 'false',
            'intermediateChanges': 'true',
            'displayedValue': value or '',
            })
        ret = super(FilteredSelectJSON, self).render(name, value, attrs, choices)
        ret = ret.split("</select>")
        ret = "".join(ret[:-1]) + """ <script type="dojo/method" event="onChange" args="e">
        var sel = dijit.byId("%s");
        var t = sel.get('displayedValue');
        var store = sel.store;
        store.url = store.url.split('?')[0] + '?q='+t;
        store.close();
        store.fetch();
        </script>""" % (attrs['id'] ) + "</select>" + ret[-1]
        ret = """<div dojoType="dojo.data.ItemFileReadStore" jsId="%s" clearOnClose="true" url="%s"></div>""" % (store, self.url) + ret
        return ret

class FilteredSelectMultiple(forms.widgets.SelectMultiple):

    def __init__(self, attrs=None, choices=()):

        super(FilteredSelectMultiple, self).__init__(attrs, choices)

    def render(self, name, value, attrs=None, choices=()):

        selected = []
        for choice in list(self.choices):
            if choice[0] in value:
                selected.append(choice)
                self.choices.remove(choice)

        output = ['<div class="selector" style>', '<div class="select-available">%s<br/>' % _('Available')]
        _from = super(FilteredSelectMultiple, self).render('select_from', value, {'id': 'select_from'}, ())
        _from = _from.split('</select>')
        output.append(u''.join(_from[:-1]))
        output.append("""
        <script type="dojo/method">
                var turn = this;
                     while(1) {
                        turn = dijit.getEnclosingWidget(turn.domNode.parentNode);
                         if(turn.isInstanceOf(dijit.form.Form)) break;
                   }
            old = turn.onSubmit;
            turn.onSubmit = function(e) {
                dojo.query("select", turn.domNode).forEach(function(s) {
                                for (var i = 0; i < s.length; i++) {
                                        s.options[i].selected = 'selected';
                                   }
                       });
                old.call(turn, e);
                };
        </script>
        <script type="dojo/connect" event="onDblClick" item="e">
        var s = this.getSelected()[0];
        var sel = dijit.byId("%s");
        var c = dojo.doc.createElement('option');
        c.innerHTML = s.text;
        c.value = s.value;
        sel.domNode.appendChild(c);
        s.parentNode.removeChild(s);
        </script>
        """ % attrs['id'])
        output.append('</select>')
        output.append('</div>')

        output.append('''
            <div class="select-options">
            <br />
            <br />
            <br />
            <a href="#" onClick=" var s=dijit.byId('%s'); var s2=dijit.byId('select_from'); s.getSelected().forEach(function(i){ var c = dojo.doc.createElement('option');c.innerHTML = i.text;c.value = i.value; s2.domNode.appendChild(c); i.parentNode.removeChild(i); }); ">
                &lt;&lt;
            </a>
            <br />
            <br />
            <br />
            <a href="#" onClick=" var s2=dijit.byId('%s'); var s=dijit.byId('select_from'); s.getSelected().forEach(function(i){ var c = dojo.doc.createElement('option');c.innerHTML = i.text;c.value = i.value; s2.domNode.appendChild(c); i.parentNode.removeChild(i); }); ">
                &gt;&gt;
            </a>
            </div>
            <div class="select-selected">
            %s<br/>
        ''' % (attrs['id'], attrs['id'], _('Selected')))

        #print output
        _from = forms.widgets.SelectMultiple().render(name, value, attrs, selected)
        _from = _from.split('</select>')
        output.append(u''.join(_from[:-1]))
        output.append("""
        <script type="dojo/connect" event="onDblClick" item="e">
        var s = this.getSelected()[0];
        var sel = dijit.byId("%s");
        var c = dojo.doc.createElement('option');
        c.innerHTML = s.text;
        c.value = s.value;
        sel.domNode.appendChild(c);
        s.parentNode.removeChild(s);
        </script>
        """ % 'select_from')
        output.append('</select>')
        output.append('</div></div>')
        return mark_safe(u''.join(output))

class FilteredSelectField(forms.fields.MultipleChoiceField):

    widget = FilteredSelectMultiple
    def __init__(self, *args, **kwargs):
        super(FilteredSelectField, self).__init__(*args, **kwargs)

class UserChangeForm(ModelForm):
    username = forms.RegexField(label=_("Username"), max_length=16, regex=r'^[\w.-_]+$',
        help_text = _("Required. 16 characters or fewer. Letters, digits and ./-/_ only."),
        error_messages = {'invalid': _("This value may contain only letters, numbers and ./-/_ characters.")})

    class Meta:
        fields = ('username', 'first_name', 'last_name',)
        model = django_User

    def __init__(self, *args, **kwargs):
        super(UserChangeForm, self).__init__(*args, **kwargs)
        f = self.fields.get('user_permissions', None)
        if f is not None:
            f.queryset = f.queryset.select_related('content_type')

    def save(self):
        obj = super(UserChangeForm, self).save()
        return obj

class bsdUserCreationForm(ModelForm, bsdUserGroupMixin):
    """
    # Yanked from django/contrib/auth/
    A form that creates a user, with no privileges, from the given username and password.
    """
    bsdusr_username = forms.CharField(label=_("Username"), max_length=16)
    bsdusr_password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput, required=False)
    bsdusr_password2 = forms.CharField(label=_("Password confirmation"), widget=forms.PasswordInput,
        help_text = _("Enter the same password as above, for verification."), required=False)
    bsdusr_shell = forms.ChoiceField(label=_("Shell"), initial=u'/bin/csh', choices=())
    bsdusr_password_disabled = forms.BooleanField(label=_("Disable password logins"), required=False)
    bsdusr_locked = forms.BooleanField(label=_("Lock user"), required=False)
    bsdusr_group2 = forms.ModelChoiceField(label=_("Primary Group"), queryset=models.bsdGroups.objects.all(), required=False)
    bsdusr_sshpubkey = forms.CharField(label=_("SSH Public Key"), widget=forms.Textarea, max_length=8192, required=False)

    class Meta:
        model = models.bsdUsers
        widgets = {
                'bsdusr_uid': forms.widgets.ValidationTextInput(),
                }
        exclude = ('bsdusr_unixhash','bsdusr_smbhash','bsdusr_builtin','bsdusr_group')
        fields = ('bsdusr_uid', 'bsdusr_username', 'bsdusr_group2', 'bsdusr_home', 'bsdusr_shell', 'bsdusr_full_name', 'bsdusr_email', 'bsdusr_password1', 'bsdusr_password2', 'bsdusr_password_disabled', 'bsdusr_sshpubkey', 'bsdusr_locked')

    def __init__(self, *args, **kwargs):
        #FIXME: Workaround for DOJO not showing select options with blank values
        if len(args) > 0 and isinstance(args[0], QueryDict):
            new = args[0].copy()
            if new.get('bsdusr_group2', None) == '-----':
                new['bsdusr_group2'] = ''
            args = (new,) + args[1:]
        super(bsdUserCreationForm, self).__init__(*args, **kwargs)
        self.fields['bsdusr_shell'].choices = self._populate_shell_choices()
        self.fields['bsdusr_shell'].choices.sort()
        self.fields['bsdusr_uid'].initial = notifier().user_getnextuid()
        self.fields['bsdusr_group2'].widget.attrs['maxHeight'] = 200
        self.fields['bsdusr_group2'].choices = (('-----', '-----'),) + tuple([x for x in self.fields['bsdusr_group2'].choices][1:])
        self.fields['bsdusr_group2'].required = False

    def clean_bsdusr_uid(self):
        bsdusr_uid = self.cleaned_data["bsdusr_uid"]
        users = models.bsdUsers.objects.filter(bsdusr_uid=bsdusr_uid)
        if self.instance.id is not None:
            users = users.exclude(id=self.instance.id)
        if users.exists():
            raise forms.ValidationError(_("A user with that uid already exists."))
        return bsdusr_uid

    def clean_bsdusr_username(self):
        if self.instance.id is None:
            bsdusr_username = self.cleaned_data["bsdusr_username"]
            self.pw_checkname(bsdusr_username)
            try:
                models.bsdUsers.objects.get(bsdusr_username=bsdusr_username)
            except models.bsdUsers.DoesNotExist:
                return bsdusr_username
            raise forms.ValidationError(_("A user with that username already exists."))
        else:
            return self.instance.bsdusr_username

    def clean_bsdusr_password2(self):
        bsdusr_password1 = self.cleaned_data.get("bsdusr_password1", "")
        bsdusr_password2 = self.cleaned_data["bsdusr_password2"]
        if bsdusr_password1 != bsdusr_password2:
            raise forms.ValidationError(_("The two password fields didn't match."))
        return bsdusr_password2

    def clean_bsdusr_home(self):
        if (self.cleaned_data['bsdusr_home'].startswith(u'/mnt/') or
            self.cleaned_data['bsdusr_home'] == u'/nonexistent'):
            return self.cleaned_data['bsdusr_home']
        raise forms.ValidationError(_('Home directory has to start with /mnt/ '
                                      'or be /nonexistent'))

    def clean_bsdusr_sshpubkey(self):
        return self.cleaned_data.get('bsdusr_sshpubkey', '')

    def clean(self):
        cleaned_data = self.cleaned_data

        locked = cleaned_data["bsdusr_locked"] = \
                cleaned_data.get("bsdusr_locked", False)
        password_disable = cleaned_data["bsdusr_password_disabled"] = \
                cleaned_data.get("bsdusr_password_disabled", False)
        if ((not (self.cleaned_data['bsdusr_home'].startswith(u'/mnt/'))) and
            self.cleaned_data.get('bsdusr_sshpubkey', '') != ''):
                del self.cleaned_data['bsdusr_sshpubkey']
                self._errors['bsdusr_sshpubkey'] = self.error_class([_("Home directory is not writable, leave this blank")])
        if self.instance.id is None:
            FIELDS = ['bsdusr_password1', 'bsdusr_password2']
            if password_disable:
                for field in FIELDS:
                    if cleaned_data.get(field, '') != '':
                        self._errors[field] = self.error_class([_("Password is disabled, leave this blank")])
                        del cleaned_data[field]
            else:
                for field in FIELDS:
                    if cleaned_data.get(field, '') == '':
                        self._errors[field] = self.error_class([_("This field is required.")])
                        del cleaned_data[field]

        return cleaned_data

    def save(self, commit=True):
        if commit:
            _notifier = notifier()
            group = self.cleaned_data['bsdusr_group2']
            if group is None:
                try:
                    gid = models.bsdGroups.objects.get(bsdgrp_group = self.cleaned_data['bsdusr_username']).bsdgrp_gid
                except:
                    gid = -1
            else:
                gid = group.bsdgrp_gid
            uid, gid, unixhash, smbhash = _notifier.user_create(
                username = str(self.cleaned_data['bsdusr_username']),
                fullname = self.cleaned_data['bsdusr_full_name'].encode('utf8', 'ignore').replace(':', ''),
                password = self.cleaned_data['bsdusr_password2'].encode('utf8', 'ignore'),
                uid = self.cleaned_data['bsdusr_uid'],
                gid = gid,
                shell = str(self.cleaned_data['bsdusr_shell']),
                homedir = str(self.cleaned_data['bsdusr_home']),
                password_disabled = self.cleaned_data['bsdusr_password_disabled'],
                locked = self.cleaned_data['bsdusr_locked']
            )
            bsduser = super(bsdUserCreationForm, self).save(commit=False)
            try:
                grp = models.bsdGroups.objects.get(bsdgrp_gid=gid)
            except models.bsdGroups.DoesNotExist:
                grp = models.bsdGroups(bsdgrp_gid=gid,
                                       bsdgrp_group=self.cleaned_data['bsdusr_username'],
                                       bsdgrp_builtin=False)
                grp.save()
            bsduser.bsdusr_group=grp
            bsduser.bsdusr_uid=uid
            bsduser.bsdusr_shell=self.cleaned_data['bsdusr_shell']
            bsduser.bsdusr_unixhash=unixhash
            bsduser.bsdusr_smbhash=smbhash
            bsduser.bsdusr_builtin=False
            bsduser.save()
            _notifier.reload("user")
            bsdusr_sshpubkey = self.cleaned_data['bsdusr_sshpubkey']
            if bsdusr_sshpubkey:
                _notifier.save_pubkey(bsduser.bsdusr_home, bsdusr_sshpubkey, bsduser.bsdusr_username, bsduser.bsdusr_group.bsdgrp_group)
        return bsduser

class bsdUserPasswordForm(ModelForm):
    bsdusr_password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput)
    bsdusr_password2 = forms.CharField(label=_("Password confirmation"), widget=forms.PasswordInput,
        help_text = _("Enter the same password as above, for verification."))

    class Meta:
        model = models.bsdUsers
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
            _notifier = notifier()
            unixhash, smbhash = _notifier.user_changepassword(
                username = str(self.instance.bsdusr_username),
                password = str(self.cleaned_data['bsdusr_password2']),
            )
            self.instance.bsdusr_unixhash=unixhash
            self.instance.bsdusr_smbhash=smbhash
            self.instance.save()
            _notifier.reload("user")
        return self.instance

class bsdUserChangeForm(ModelForm, bsdUserGroupMixin):
    bsdusr_password_disabled = forms.BooleanField(label=_("Disable password"), required=False)
    bsdusr_locked = forms.BooleanField(label=_("Lock user"), required=False)
    bsdusr_shell = forms.ChoiceField(label=_("Shell"),
                                     initial=u'/bin/csh',
                                     choices=()
                                     )
    bsdusr_sshpubkey = forms.CharField(label=_("SSH Public Key"), widget=forms.Textarea, max_length=8192, required=False)

    class Meta:
        model = models.bsdUsers
        exclude = ('bsdusr_unixhash', 'bsdusr_smbhash', 'bsdusr_builtin',)
        widgets = {
                'bsdusr_uid': forms.widgets.ValidationTextInput(),
                }

    def __init__(self, *args, **kwargs):
        super(bsdUserChangeForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance:
            if instance.id:
                self.fields['bsdusr_username'].widget.attrs['readonly'] = True
            if instance.bsdusr_builtin:
                self.fields['bsdusr_uid'].widget.attrs['readonly'] = True
                self.fields['bsdusr_group'].widget.attrs['readonly'] = True
                self.fields['bsdusr_home'].widget.attrs['readonly'] = True
            if instance.bsdusr_unixhash == '*':
                self.fields['bsdusr_password_disabled'].initial = True
            if instance.bsdusr_unixhash.startswith('*LOCKED*'):
                self.fields['bsdusr_locked'].initial = True
            try:
                self.fields['bsdusr_sshpubkey'].initial = open('%s/.ssh/authorized_keys' % (instance.bsdusr_home)).read()
            except:
                self.fields['bsdusr_sshpubkey'].initial = ''
        self.fields['bsdusr_shell'].choices = self._populate_shell_choices()
        self.fields['bsdusr_shell'].choices.sort()
        self.fields['bsdusr_group'].widget.attrs['maxHeight'] = 200

    def clean_bsdusr_uid(self):
        instance = getattr(self, 'instance', None)
        if instance and instance.bsdusr_builtin:
            return self.instance.bsdusr_uid
        else:
            return self.cleaned_data.get("bsdusr_uid")

    def clean_bsdusr_group(self):
        instance = getattr(self, 'instance', None)
        if instance and instance.bsdusr_builtin:
            return self.instance.bsdusr_group
        else:
            return self.cleaned_data.get("bsdusr_group")

    def clean_bsdusr_username(self):
        return self.instance.bsdusr_username

    def clean_bsdusr_home(self):
        instance = getattr(self, 'instance', None)
        if instance and instance.bsdusr_builtin:
            return self.instance.bsdusr_home
        if (self.cleaned_data['bsdusr_home'].startswith(u'/mnt/') or
            self.cleaned_data['bsdusr_home'] == u'/nonexistent'):
            return self.cleaned_data['bsdusr_home']
        raise forms.ValidationError(_('Home directory has to start with /mnt '
                                      'or be /nonexistent'))

    def clean_bsdusr_password_disabled(self):
        return self.cleaned_data.get("bsdusr_password_disabled", False)

    def clean_bsdusr_locked(self):
        return self.cleaned_data.get("bsdusr_locked", False)

    def clean(self):
        cleaned_data = self.cleaned_data
        if ((not (self.cleaned_data['bsdusr_home'].startswith(u'/mnt/') or
            self.cleaned_data['bsdusr_home'] == '/root')) and
            self.cleaned_data.get('bsdusr_sshpubkey', '')):
                del self.cleaned_data['bsdusr_sshpubkey']
                self._errors['bsdusr_sshpubkey'] = self.error_class([_("Home directory is not writable, leave this blank")])
        return cleaned_data

    def save(self):
        bsduser = super(bsdUserChangeForm, self).save(commit=False)
        bsduser_locked = self.cleaned_data['bsdusr_locked']
	bsdusr_sshpubkey = self.cleaned_data['bsdusr_sshpubkey']
        instance = getattr(self, 'instance', None)
        _notifier = notifier()
        if bsduser_locked and instance.bsdusr_unixhash.startswith('*LOCKED*'):
            bsduser.bsdusr_unixhash, bsduser.smbhash = \
                _notifier.user_unlock(str(bsduser.bsdusr_username))
        elif (bsduser_locked and
              instance.bsdusr_unixhash.startswith('*LOCKED*')):
            bsduser.bsdusr_unixhash, bsduser.smbhash = \
                _notifier.user_lock(str(bsduser.bsdusr_username))
        if self.cleaned_data["bsdusr_password_disabled"]:
            bsduser.bsdusr_unixhash = "*"
            bsduser.bsdusr_smbhash = ""
        bsduser.bsduser_shell = self.cleaned_data['bsdusr_shell']
        bsduser.save()
        _notifier.reload("user")
        if (self.cleaned_data['bsdusr_home'].startswith(u'/mnt/') or
            self.cleaned_data['bsdusr_home'] == '/root'):
            if bsdusr_sshpubkey:
                _notifier.save_pubkey(bsduser.bsdusr_home, bsdusr_sshpubkey, bsduser.bsdusr_username, bsduser.bsdusr_group.bsdgrp_group)
        return bsduser

class bsdUserEmailForm(ModelForm, bsdUserGroupMixin):
    class Meta:
        model = models.bsdUsers
        fields = ('bsdusr_email',)
    def save(self):
        bsduser = super(bsdUserEmailForm, self).save(commit=True)
        notifier().reload("user")
        return bsduser

class bsdGroupsForm(ModelForm, bsdUserGroupMixin):
    class Meta:
        model = models.bsdGroups
        exclude = ('bsdgrp_builtin',)
        widgets = {
                'bsdgrp_gid': forms.widgets.ValidationTextInput(),
                }
    def __init__(self, *args, **kwargs):
        super(bsdGroupsForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.id:
            self.fields['bsdgrp_gid'].widget.attrs['readonly'] = True
        else:
            self.initial['bsdgrp_gid'] = notifier().user_getnextgid()
            self.fields['allow'] = forms.BooleanField(
                                        label=_("Allow repeated GIDs"),
                                        initial=False,
                                        required=False,
                                    )

    def clean_bsdgrp_group(self):
        if self.instance.id is None:
            bsdgrp_group = self.cleaned_data.get("bsdgrp_group")
            self.pw_checkname(bsdgrp_group)
            try:
                models.bsdGroups.objects.get(bsdgrp_group=bsdgrp_group)
            except models.bsdGroups.DoesNotExist:
                return bsdgrp_group
            raise forms.ValidationError(_("A group with that name already exists."))
        else:
            return self.instance.bsdgrp_group

    def clean_bsdgrp_gid(self):
        instance = getattr(self, 'instance', None)
        if instance and instance.id:
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
                self._errors['bsdgrp_gid'] = self.error_class([_("A group with this gid already exists")])
                cdata.pop('bsdgrp_gid', None)
        return cdata

    def save(self):
        ins = super(bsdGroupsForm, self).save()
        notifier().reload("user")
        return ins

attrs_dict = { 'class': 'required' }

class bsdGroupToUserForm(Form):
    bsdgroup_to_user = FilteredSelectField(label = _('Member users'), choices=(), required=False)
    def __init__(self, groupid, *args, **kwargs):
        super(bsdGroupToUserForm, self).__init__(*args, **kwargs)
        self.groupid = groupid
        group = models.bsdGroups.objects.get(id=self.groupid)
        self.fields['bsdgroup_to_user'].choices = [(x.id, x.bsdusr_username) for x in models.bsdUsers.objects.all()]
        self.fields['bsdgroup_to_user'].initial = [(x.bsdgrpmember_user.id) for x in models.bsdGroupMembership.objects.filter(bsdgrpmember_group=group)]
    def save(self):
        group = models.bsdGroups.objects.get(id=self.groupid)
        models.bsdGroupMembership.objects.filter(bsdgrpmember_group=group).delete()
        userid_list = self.cleaned_data['bsdgroup_to_user']
        for userid in userid_list:
            user = models.bsdUsers.objects.get(id=userid)
            m = models.bsdGroupMembership(bsdgrpmember_group=group, bsdgrpmember_user=user)
            m.save()
        notifier().reload("user")

class bsdUserToGroupForm(Form):
    bsduser_to_group = FilteredSelectField(label = _('Auxiliary groups'), choices=(), required=False)
    def __init__(self, userid, *args, **kwargs):
        super(bsdUserToGroupForm, self).__init__(*args, **kwargs)
        self.userid = userid
        user = models.bsdUsers.objects.get(id=self.userid)
        self.fields['bsduser_to_group'].choices = [(x.id, x.bsdgrp_group) for x in models.bsdGroups.objects.all()]
        self.fields['bsduser_to_group'].initial = [(x.bsdgrpmember_group.id) for x in models.bsdGroupMembership.objects.filter(bsdgrpmember_user=user)]
    def clean_bsduser_to_group(self):
        v = self.cleaned_data.get("bsduser_to_group")
        if len(v) > 64:
            raise forms.ValidationError(_("A user cannot belong to more than 64 auxiliary groups"))
        return v
    def save(self):
        user = models.bsdUsers.objects.get(id=self.userid)
        models.bsdGroupMembership.objects.filter(bsdgrpmember_user=user).delete()
        groupid_list = self.cleaned_data['bsduser_to_group']
        for groupid in groupid_list:
            group = models.bsdGroups.objects.get(id=groupid)
            m = models.bsdGroupMembership(bsdgrpmember_group=group, bsdgrpmember_user=user)
            m.save()
        notifier().reload("user")

class SetPasswordForm(forms.Form):
    """
    A form that lets a user change set his/her password without
    entering the old password
    """
    new_password1 = forms.CharField(label=_("New password"), widget=forms.PasswordInput)
    new_password2 = forms.CharField(label=_("New password confirmation"), widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super(SetPasswordForm, self).__init__(*args, **kwargs)

    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError(_("The two password fields didn't match."))
        return password2

    def save(self, commit=True):
        self.user.set_password(self.cleaned_data['new_password1'])
        if commit:
            self.user.save()
        return self.user

class PasswordChangeForm(SetPasswordForm):
    """
    A form that lets a user change his/her password by entering
    their old password.
    """
    old_password = forms.CharField(label=_("Old password"),
        widget=forms.PasswordInput,
        required=False)
    change_root = forms.BooleanField(label=_("Change root password as well"),
        initial=True,
        required=False)

    def clean_old_password(self):
        """
        Validates that the old_password field is correct.
        """
        if not self.user.has_usable_password():
            return ''
        old_password = self.cleaned_data["old_password"]
        if not self.user.check_password(old_password):
            raise forms.ValidationError(_("Your old password was entered incorrectly. Please enter it again."))
        return old_password
PasswordChangeForm.base_fields.keyOrder = ['old_password', 'new_password1', 'new_password2', 'change_root']

