# Copyright 2011 iXsystems, Inc.
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
from django.forms.utils import flatatt
from django.forms.widgets import Widget
from django.utils.safestring import mark_safe
from dojango.forms.widgets import DojoWidgetMixin

import json


class CloudSyncWidget(DojoWidgetMixin, Widget):
    dojo_type = 'freeadmin.CloudSync'

    def render(self, name, value, attrs=None):
        from freenasUI.system.models import CloudCredentials
        if value is None:
            value = ''
        extra_attrs = {
            'data-dojo-name': name,
            'data-dojo-props': mark_safe("credentials: '{}', initial: '{}'".format(
                json.dumps([
                    (str(i), i.id)
                    for i in CloudCredentials.objects.all()
                ]),
                json.dumps(value),
            ).replace('"', '&quot;')),
        }
        final_attrs = self.build_attrs(attrs, name=name, **extra_attrs)
        return mark_safe('<div%s></div>' % (flatatt(final_attrs),))
