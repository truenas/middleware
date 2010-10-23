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

from django.db import models
from django import forms
from django.contrib.auth.models import User
import datetime
import time
from os import popen
from django.utils.text import capfirst
from django.forms.widgets import RadioFieldRenderer
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext_lazy as _
from datetime import datetime
from freenasUI.choices import *

  

""" Disk and Volume Management """

class Disk(models.Model):
    disk_name = models.CharField(
            unique=True,
            max_length=120, 
            verbose_name="Name"
            )
    disk_disks = models.CharField(
            max_length=120, 
            verbose_name="Disks"
            )
    disk_description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True
            )
    disk_sort = models.IntegerField(
            _('Disk order'), 
            default=0, 
            help_text='The order in which disks will be displayed.')
    disk_transfermode = models.CharField(
            max_length=120, 
            choices=TRANSFERMODE_CHOICES, 
            default="Auto", 
            verbose_name="Transfer Mode"
            )
    disk_hddstandby = models.CharField(
            max_length=120, 
            choices=HDDSTANDBY_CHOICES, 
            default="Always On", 
            verbose_name="HDD Standby"
            )
    disk_advpowermgmt = models.CharField(
            max_length=120, 
            choices=ADVPOWERMGMT_CHOICES, 
            default="Disabled", 
            verbose_name="Advanced Power Management"
            )
    disk_acousticlevel = models.CharField(
            max_length=120, 
            choices=ACOUSTICLVL_CHOICES, 
            default="Disabled", 
            verbose_name="Acoustic Level"
            )
    disk_togglesmart = models.BooleanField(default=True)
    disk_smartoptions = models.CharField(
            max_length=120, 
            verbose_name="S.M.A.R.T. extra options", 
            blank=True
            )
    class Meta:
        verbose_name = "Disk"
        ordering = ['disk_sort',]
    def __unicode__(self):
        return self.disk_disks + ' (' + self.disk_name + ')'
    def save(self, *args, **kwargs):
        super(Disk, self).save(*args, **kwargs)

class DiskGroup(models.Model):
    group_name = models.CharField(
            unique=True,
            max_length=120, 
            verbose_name="Name"
            )
    group_members = models.ForeignKey(
            Disk,
            verbose_name="Members",
            help_text="Assign disks to a group"
            )
    group_type = models.CharField(
            max_length=120, 
            choices=ZFS_Choices, 
            default=" ", 
            verbose_name="Type", 
            blank="True"
            )
    
    def __unicode__(self):
        return self.group_name

""" Volume Management """
class Volume(models.Model):
    vol_name = models.CharField(
            unique=True,
            max_length=120, 
            verbose_name="Name"
            )
    vol_type = models.CharField(
            max_length=120, 
            choices=VolumeType_Choices, 
            default=" ", 
            verbose_name="Volume Type", 
            blank="True"
            )
    vol_groups = models.ForeignKey(
            DiskGroup,
            verbose_name="Disk Groups",
            help_text="Assign a disk group to a Volume",
            )
    class Meta:
        verbose_name = "Volume"
    def __unicode__(self):
        return self.vol_name
    def save(self, *args, **kwargs):
        super(Volume, self).save(*args, **kwargs)


class MountPoint(models.Model):
    mp_volumeid = models.ForeignKey(Volume)
    mp_path = models.CharField(
            unique=True,
            max_length=120,
            verbose_name="Mount Point",
            help_text="Path to mount point",
            )
    mp_options = models.CharField(
            max_length=120,
            verbose_name="Mount options",
            help_text="Enter Mount Point options here",
            null=True,
            )
    def __unicode__(self):
        return self.mp_path

