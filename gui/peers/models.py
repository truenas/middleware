# Copyright 2017 iXsystems, Inc.
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

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.core.validators import MaxValueValidator, MinValueValidator

from freenasUI.freeadmin.models import Model

class Peer(Model):
    name = models.CharField(
        max_length=150,
        verbose_name=_('Peer name'),
    )
    description = models.CharField(
        max_length=250,
        verbose_name=_('Peer description')
    )

class SSH_Peer(Peer):
    ssh_port = models.IntegerField(
        verbose_name=_('SSH remote peer port number'),
        default=22,
        validators=[MinValueValidator(1), MaxValueValidator(65536)],
    )
    ssh_remote_hostname = models.CharField(
        max_length=120,
        verbose_name=_("Remote hostname"),
    )
    ssh_remote_user = models.CharField(
        verbose_name=_("Remote Dedicated User"),
        max_length=120,
    )
    ssh_remote_hostkey = models.CharField(
        max_length=2048,
        verbose_name=_("Remote hostkey"),
    )

