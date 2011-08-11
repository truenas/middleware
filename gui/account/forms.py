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
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User as django_User
from django.utils.safestring import mark_safe
from django.http import QueryDict

from freenasUI.common.forms import ModelForm, Form
from freenasUI.account import models
from freenasUI.middleware.notifier import notifier
from dojango import forms

class SharedFunc():
    def _populate_shell_choices(self):
        from os import popen
        from os.path import basename

        shell_dict = {}
        shells = popen("grep ^/ /etc/shells").read().split('\n')
        for shell in shells:
            shell_dict[shell] = basename(shell)
        shell_dict['/sbin/nologin'] = 'nologin'
        return shell_dict.items()

class FilteredSelectJSON(forms.widgets.ComboBox):
#class FilteredSelectJSON(forms.widgets.FilteringSelect):

    def __init__(self, attrs=None, choices=(), url=[]):
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
        super(UserChangeForm, self).save()
        notifier().start('ix-msmtp')
        return self.instance

class bsdUserCreationForm(ModelForm, SharedFunc):
    """
    # Yanked from django/contrib/auth/
    A form that creates a user, with no privileges, from the given username and password.
    """
    bsdusr_username = forms.RegexField(label=_("Username"), max_length=30, regex=r'^[\w.@+-]+$',
        help_text = _("Required. 30 characters or fewer. Letters, digits and @/./+/-/_ only."),
        error_messages = {'invalid': _("This value may contain only letters, numbers and @/./+/-/_ characters.")})
    bsdusr_password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput, required=False)
    bsdusr_password2 = forms.CharField(label=_("Password confirmation"), widget=forms.PasswordInput,
        help_text = _("Enter the same password as above, for verification."), required=False)
    bsdusr_shell = forms.ChoiceField(label=_("Shell"), initial=u'/bin/csh', choices=())
    bsdusr_login_disabled = forms.BooleanField(label=_("Disable logins"), required=False)
    bsdusr_group2 = forms.ModelChoiceField(label=_("Primary Group"), queryset=models.bsdGroups.objects.all(), required=False)

    class Meta:
        model = models.bsdUsers
        widgets = {
                'bsdusr_uid': forms.widgets.ValidationTextInput(),
                }
        exclude = ('bsdusr_unixhash','bsdusr_smbhash','bsdusr_builtin','bsdusr_group')
        fields = ('bsdusr_uid', 'bsdusr_username', 'bsdusr_group2', 'bsdusr_home', 'bsdusr_shell', 'bsdusr_full_name', 'bsdusr_email', 'bsdusr_password1', 'bsdusr_password2', 'bsdusr_login_disabled')

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
        self.initial['bsdusr_uid'] = notifier().user_getnextuid()
        self.fields['bsdusr_group2'].widget.attrs['maxHeight'] = 200
        self.fields['bsdusr_group2'].choices = (('-----', '-----'),) + tuple([x for x in self.fields['bsdusr_group2'].choices][1:])
        self.fields['bsdusr_group2'].required = False

    def clean_bsdusr_username(self):
        if self.instance.id is None:
            bsdusr_username = self.cleaned_data["bsdusr_username"]
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
        if self.cleaned_data['bsdusr_home'][0:5] != u'/mnt/' and self.cleaned_data['bsdusr_home'] not in (u'/nonexistent',u'/mnt'):
            raise forms.ValidationError(_("Home directory has to start with /mnt/"))
        return self.cleaned_data['bsdusr_home']

    def clean(self):
        cleaned_data = self.cleaned_data

        login = cleaned_data["bsdusr_login_disabled"] = \
                cleaned_data.get("bsdusr_login_disabled", False)
        if login:
            cleaned_data['bsdusr_password'] = ""
            cleaned_data['bsdusr_password2'] = ""
        else:
            if ((self.instance.id is not None and cleaned_data["bsdusr_password1"] != "") or \
                (self.instance.id is None and cleaned_data["bsdusr_password1"] == "")):
                self._errors['bsdusr_password1'] = self.error_class([_("This field is required.")])
                del cleaned_data['bsdusr_password1']
            if ((self.instance.id is not None and cleaned_data.get("bsdusr_password2", None) != "") or \
                (self.instance.id is None and cleaned_data.get("bsdusr_password2", None) == "")):
                self._errors['bsdusr_password2'] = self.error_class([_("This field is required.")])
                del cleaned_data['bsdusr_password2']

        return cleaned_data

    def save(self, commit=True):
        if commit:
            group = self.cleaned_data['bsdusr_group2']
            if group == None:
                try:
                    gid = models.bsdGroups.objects.get(bsdgrp_group = self.cleaned_data['bsdusr_username']).bsdgrp_gid
                except:
                    gid = -1
            else:
                gid = group.bsdgrp_gid
            uid, gid, unixhash, smbhash = notifier().user_create(
                username = self.cleaned_data['bsdusr_username'].__str__(),
                fullname = self.cleaned_data['bsdusr_full_name'].encode('utf8', 'ignore').replace(":",""),
                password = self.cleaned_data['bsdusr_password2'].encode('utf8', 'ignore'),
                uid = self.cleaned_data['bsdusr_uid'],
                gid = gid,
                shell = self.cleaned_data['bsdusr_shell'].__str__(),
                homedir = self.cleaned_data['bsdusr_home'].__str__(),
                password_disabled = self.cleaned_data['bsdusr_login_disabled']
            )
            bsduser = super(bsdUserCreationForm, self).save(commit=False)
            try:
                grp = models.bsdGroups.objects.get(bsdgrp_gid=gid)
            except models.bsdGroups.DoesNotExist:
                grp = models.bsdGroups(bsdgrp_gid=gid, bsdgrp_group=self.cleaned_data['bsdusr_username'], bsdgrp_builtin=False)
                grp.save()
            bsduser.bsdusr_group=grp
            bsduser.bsdusr_uid=uid
            bsduser.bsdusr_shell=self.cleaned_data['bsdusr_shell']
            bsduser.bsdusr_unixhash=unixhash
            bsduser.bsdusr_smbhash=smbhash
            bsduser.bsdusr_builtin=False
            bsduser.save()
            notifier().reload("user")
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
            unixhash, smbhash = notifier().user_changepassword(
                username = self.instance.bsdusr_username.__str__(),
                password = self.cleaned_data['bsdusr_password2'].__str__(),
            )
            self.instance.bsdusr_unixhash=unixhash
            self.instance.bsdusr_smbhash=smbhash
            self.instance.save()
            notifier().reload("user")
        return self.instance

class bsdUserChangeForm(ModelForm, SharedFunc):
    bsdusr_login_disabled = forms.BooleanField(label=_("Disable logins"), required=False)
    bsdusr_shell = forms.ChoiceField(label=_("Shell"),
                                     initial=u'/bin/csh',
                                     choices=()
                                     )
  
    class Meta:
        model = models.bsdUsers
        exclude = ('bsdusr_unixhash', 'bsdusr_smbhash', 'bsdusr_builtin',)

    def __init__(self, *args, **kwargs):
        super(bsdUserChangeForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance:
            if instance.id:
                self.fields['bsdusr_username'].widget.attrs['readonly'] = True
            if instance.bsdusr_unixhash == '*' or instance.bsdusr_unixhash[0:8] == '*LOCKED*':
                self.fields['bsdusr_login_disabled'].initial = True

        self.fields['bsdusr_shell'].choices = self._populate_shell_choices()
        self.fields['bsdusr_shell'].choices.sort()
        self.fields['bsdusr_group'].widget.attrs['maxHeight'] = 200

    def clean_bsdusr_username(self):
        return self.instance.bsdusr_username

    def clean_bsdusr_home(self):
        if self.cleaned_data['bsdusr_home'][0:5] != u'/mnt/' and self.cleaned_data['bsdusr_home'] not in (u'/nonexistent',u'/mnt'):
            raise forms.ValidationError(_("Home directory has to start with /mnt/"))
        return self.cleaned_data['bsdusr_home']

    def clean_bsdusr_login_disabled(self):
        return self.cleaned_data.get("bsdusr_login_disabled", False)

    def save(self):
        bsduser = super(bsdUserChangeForm, self).save(commit=False)
        bsduser_locked = (bsduser.bsdusr_unixhash[0:8] == '*LOCKED*')
        if self.cleaned_data["bsdusr_login_disabled"] == True and bsduser_locked == False:
            bsduser.bsdusr_unixhash = notifier().user_lock(bsduser.bsdusr_username.__str__())
        elif self.cleaned_data["bsdusr_login_disabled"] == False and bsduser_locked == True:
            bsduser.bsdusr_unixhash = notifier().user_unlock(bsduser.bsdusr_username.__str__())
        bsduser.bsduser_shell = self.cleaned_data['bsdusr_shell']
        bsduser.save()
        notifier().reload("user")
        return bsduser

class bsdUserEmailForm(ModelForm, SharedFunc):
    class Meta:
        model = models.bsdUsers
        fields = ('bsdusr_email',)
    def save(self):
        bsduser = super(bsdUserEmailForm, self).save(commit=True)
        notifier().reload("user")
        return bsduser

class bsdGroupsForm(ModelForm):
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
    old_password = forms.CharField(label=_("Old password"), widget=forms.PasswordInput)

    def clean_old_password(self):
        """
        Validates that the old_password field is correct.
        """
        old_password = self.cleaned_data["old_password"]
        if not self.user.check_password(old_password):
            raise forms.ValidationError(_("Your old password was entered incorrectly. Please enter it again."))
        return old_password
PasswordChangeForm.base_fields.keyOrder = ['old_password', 'new_password1', 'new_password2']

