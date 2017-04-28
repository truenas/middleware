# +
# Copyright 2016 ZFStor
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

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.core.validators import MaxValueValidator, MinValueValidator

from freenasUI import choices
from freenasUI.freeadmin.models import DictField, Model

log = logging.getLogger('vm.models')


class VM(Model):
    name = models.CharField(
        max_length=150,
        verbose_name=_('Name'),
        help_text=_('Name of the virtual machine.'),
    )
    description = models.CharField(
        max_length=250,
        verbose_name=_('Description'),
        help_text=_('A short description of the virtual machine.'),
        blank=True,
    )
    vcpus = models.IntegerField(
        verbose_name=_('Virtual CPUs'),
        help_text=_('Number of virtual CPUs allocated to the VM.'),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(16)],
    )
    memory = models.IntegerField(
        verbose_name=_('Memory Size (MiB)'),
        help_text=_('Megabytes of RAM for the virtual machine.'
                    'This memory will be allocated when the VM is running '
                    'and not available to the host system or other VMs.'),
    )
    bootloader = models.CharField(
        verbose_name=_('Boot Method'),
        max_length=50,
        help_text=_('System boot method and architecture.'),
        choices=choices.VM_BOOTLOADER,
        default='UEFI',
    )

    class Meta:
        verbose_name = _(u"VM")
        verbose_name_plural = _(u"VMs")

    def __str__(self):
        return self.name


class Device(Model):
    vm = models.ForeignKey(
        VM,
        verbose_name=_('VM'),
    )
    dtype = models.CharField(
        verbose_name=_('Type'),
        max_length=50,
        choices=choices.VM_DEVTYPES,
    )
    attributes = DictField(
        editable=False,
    )

    def __str__(self):
        return '{0}:{1}'.format(self.vm, self.get_dtype_display())
