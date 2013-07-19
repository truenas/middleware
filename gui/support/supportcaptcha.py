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
import requests

from dojango import forms

from django.forms import ValidationError
from django.forms.fields import MultiValueField
from django.utils.translation import ugettext_lazy as _
from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from django.forms import ValidationError
from django.forms.widgets import MultiWidget

from freenasUI.common.forms import ModelForm, Form
from freenasUI.support import models

from captcha.conf import settings
from captcha.models import CaptchaStore, get_safe_now
from captcha.fields import CaptchaField, CaptchaTextInput

from bs4 import BeautifulSoup

log = logging.getLogger("support.supportcaptcha")

SUPPORT_PROTO = "http"
SUPPORT_HOST = "tickets.ixsystems.com"
SUPPORT_BASE = "%s://%s" % (SUPPORT_PROTO, SUPPORT_HOST)
SUPPORT_URL = "%s/postproxy/index" % SUPPORT_BASE
SUPPORT_URL_GET = SUPPORT_URL
SUPPORT_URL_POST = "%s/" % SUPPORT_URL

class BaseSupportCaptchaTextInput(MultiWidget):
    """
    Base class for Captcha widgets
    """
    def __init__(self, attrs=None):
        widgets = (
            forms.HiddenInput(attrs),
            forms.TextInput(attrs),
        )

        try:
            self.req = requests.get(SUPPORT_URL_GET)
            self.soup = BeautifulSoup(self.req.text)  

        except Exception as e:
            raise ValidationError("Unable to reach %s: %s" % (SUPPORT_URL_GET, e))

        super(BaseSupportCaptchaTextInput, self).__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return value.split(',')
        return [None, None]

    def fetch_captcha_store(self, name, value, attrs=None):
        """
        Fetches a new CaptchaStore
        This has to be called inside render
        """

       	key = self.soup.find(id='id_captcha_0')['value']

        # these can be used by format_output and render
        self._value = [key, u'']
        self._key = key
        self.id_ = "id_captcha"

    def render(self, name, value, attrs=None):
        return super(BaseSupportCaptchaTextInput, self).render(name, self._value, attrs=attrs)

    def id_for_label(self, id_):
        return "id_captcha_1"
        #return id_ + '_1'

    def image_url(self):
        src = self.soup.find('img')['src']
        return "%s%s" % (SUPPORT_BASE, src)

class SupportCaptchaTextInput(BaseSupportCaptchaTextInput):
    def __init__(self, attrs=None, **kwargs):
        self._args = kwargs
        self._args['output_format'] = self._args.get('output_format') or settings.CAPTCHA_OUTPUT_FORMAT

        for key in ('image', 'hidden_field', 'text_field'):
            if '%%(%s)s' % key not in self._args['output_format']:
                raise ImproperlyConfigured('All of %s must be present in your CAPTCHA_OUTPUT_FORMAT setting. Could not find %s' % (
                    ', '.join(['%%(%s)s' % k for k in ('image', 'hidden_field', 'text_field')]),
                    '%%(%s)s' % key
                ))
        super(SupportCaptchaTextInput, self).__init__(attrs)

    def format_output(self, rendered_widgets):
        hidden_field, text_field = rendered_widgets
        return self._args['output_format'] % {
            'image': self.image_and_audio,
            'hidden_field': hidden_field,
            'text_field': text_field
        }

    def render(self, name, value, attrs=None):
        self.fetch_captcha_store(name, value, attrs)

        self.image_and_audio = '<img src="%s" alt="captcha" class="captcha" />' % self.image_url()
        return super(SupportCaptchaTextInput, self).render(name, self._value, attrs=attrs)


class SupportCaptchaField(MultiValueField):
    def __init__(self, *args, **kwargs):
        fields = (
            forms.CharField(show_hidden_initial=True),
            forms.CharField(),
        )
        if 'error_messages' not in kwargs or 'invalid' not in kwargs.get('error_messages'):
            if 'error_messages' not in kwargs:
                kwargs['error_messages'] = {}
            kwargs['error_messages'].update({'invalid': _('Invalid CAPTCHA')})

        kwargs['widget'] = kwargs.pop('widget', SupportCaptchaTextInput(output_format=kwargs.pop('output_format', None)))

        super(SupportCaptchaField, self).__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        if data_list:
            return ','.join(data_list)
        return None

    def clean(self, value):
        super(SupportCaptchaField, self).clean(value)
        response, value[1] = value[1].strip().lower(), ''
        #CaptchaStore.remove_expired()

        # XXX
        return value  

        if settings.CATPCHA_TEST_MODE and response.lower() == 'passed':
            # automatically pass the test
            try:
                # try to delete the captcha based on its hash
                CaptchaStore.objects.get(hashkey=value[0]).delete()
            except CaptchaStore.DoesNotExist:
                # ignore errors
                pass
        else:
            try:
                CaptchaStore.objects.get(response=response, hashkey=value[0], expiration__gt=get_safe_now()).delete()
            except CaptchaStore.DoesNotExist:
                raise ValidationError(getattr(self, 'error_messages', {}).get('invalid', _('Invalid CAPTCHA')))
        return value
