#+
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
import hashlib
import hmac
import logging
import random
import time

from django.db import models
from django.utils.translation import ugettext_lazy as _

from freenasUI.freeadmin.models import Model

log = logging.getLogger('api.models')


class APIClient(Model):

    name = models.CharField(
        verbose_name=_("Name"),
        max_length=100,
        unique=True,
    )
    secret = models.CharField(max_length=1024, editable=False)

    class Meta:
        verbose_name = _("API Client")
        verbose_name_plural = _("API Clients")

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.secret:
            log.debug('Generating new secret for %s', self.name)
            h = hmac.HMAC(
                key="%s:%s:%s" % (
                    self.name.encode('utf8'),
                    random.random(),
                    time.time(),
                ),
                digestmod=hashlib.sha512
            )
            self.secret = str(h.hexdigest())
        super(APIClient, self).save(*args, **kwargs)
