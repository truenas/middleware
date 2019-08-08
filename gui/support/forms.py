# Copyright 2013 iXsystems, Inc.
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

from django.utils.translation import ugettext as _

from dojango import forms
from freenasUI.common.forms import Form, ModelForm
from freenasUI.middleware.client import client
from freenasUI.support import models

log = logging.getLogger("support.forms")


class ProductionForm(Form):

    production = forms.BooleanField(
        label=_('This is production system'),
        required=False,
    )

    send_debug = forms.BooleanField(
        label=_('Send initial debug'),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super(ProductionForm, self).__init__(*args, **kwargs)

        self.fields['production'].widget.attrs['onChange'] = (
            'support_production_toggle();'
        )

        with client as c:
            self.initial['production'] = c.call('truenas.is_production')

    def save(self):
        with client as c:
            c.call('truenas.set_production', self.cleaned_data['production'], self.cleaned_data['send_debug'])


class SupportForm(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.Support

    def __init__(self, *args, **kwargs):
        super(SupportForm, self).__init__(*args, **kwargs)


class LicenseUpdateForm(Form):

    license = forms.CharField(
        label=_('License'),
        widget=forms.widgets.Textarea,
    )
