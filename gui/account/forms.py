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
from dojango.forms import ModelForm
from freenasUI.account.models import *                         
from freenasUI.middleware.notifier import notifier
from django.utils.translation import ugettext_lazy as _

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

    class Meta:
        model = bsdUsers
        exclude = ('bsdusr_password',)

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
        bsdusr_username = super(bsdUserCreationForm, self).save(commit=False)
        bsdusr_username.set_password(self.cleaned_data["bsdusr_password1"])
        if commit:
            bsdusr_username.save()
        return bsdusr_username

class bsdGroupsForm(ModelForm):
    class Meta:
        model = bsdGroups
    def save(self):
        super(bsdGroupsForm, self).save()
        #notifier().do("something")
