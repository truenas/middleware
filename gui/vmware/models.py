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
import dateutil
import logging
import os
import string
import uuid

from datetime import datetime
from dateutil import tz, parser as dtparser

from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.freeadmin.models import Model
from freenasUI.middleware.notifier import notifier

log = logging.getLogger('vmware.models')


class Settings(Model):

    hostname = models.CharField(
        verbose_name=_('Hostname'),
        max_length=200,
    )
    username = models.CharField(
        verbose_name=_('Username'),
        max_length=200,
        help_text=_(
            'Username on the above VMWare host with enough privileges to '
            'snapshot virtual machines.'
        ),
    )
    password = models.CharField(
        verbose_name=_('Password'),
        max_length=200,
    )

    class Meta:
        verbose_name = _('Configure')

    def __unicode__(self):
        return self.hostname
