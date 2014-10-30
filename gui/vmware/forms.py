# +
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

from collections import defaultdict, OrderedDict
from datetime import datetime
import cPickle as pickle
import json
import logging
import math
import os
import re
import stat
import subprocess
import tempfile

from django.conf import settings
from django.http import HttpResponse
from django.utils.html import escapejs
from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI import choices
from freenasUI.common.forms import ModelForm, Form
from freenasUI.common.freenasldap import (
    FreeNAS_ActiveDirectory,
    FreeNAS_LDAP
)
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.vmware import models

class SettingsForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.Settings
        widgets = {
            'password': forms.widgets.PasswordInput(),
        }

    def __init__(self, *args, **kwargs):
        super(SettingsForm, self).__init__(*args, **kwargs)
        self.fields['password'].required = False

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password:
            if self.instance.id:
                return self.instance.password
            else:
                raise forms.ValidationError(_('This field is required.'))
        return password

    def clean(self):
        from pysphere import VIServer
        cdata = self.cleaned_data
        if (
            cdata.get('hostname') and cdata.get('username') and
            cdata.get('password')
        ):
            try:
                server = VIServer()
                server.connect(
                    cdata.get('hostname'),
                    cdata.get('username'),
                    cdata.get('password'),
                    sock_timeout=7,
                )
                server.disconnect()
            except Exception, e:
                self._errors['__all__'] = self.error_class([_(
                    'Failed to connect: %s'
                ) % e])
        return cdata
