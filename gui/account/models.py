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
from freenasUI.choices import UserShell
from django.contrib.auth.models import get_hexdigest

class bsdGroups(models.Model):
    bsdgrp_gid = models.IntegerField(
            verbose_name="Group ID"
            )
    bsdgrp_group = models.CharField(
            unique = True,
            max_length=120,
            verbose_name="Group Name"
            )
    bsdgrp_builtin = models.BooleanField(
            default=False,
            )
    class Meta:
        verbose_name = "Group"
    def __unicode__(self):
        return self.bsdgrp_group

class bsdUsers(models.Model):
    bsdusr_uid = models.IntegerField(
            max_length=10,
            unique="True",
            verbose_name="User ID"
            )
    bsdusr_username = models.CharField(
            max_length=30,
            unique=True,
            default='User &',
            verbose_name="Username"
            )
    bsdusr_unixhash = models.CharField(
            max_length=128,
            blank=True,
            default='*',
            verbose_name="Hashed UNIX password"
            )
    bsdusr_smbhash = models.CharField(
            max_length=128,
            blank=True,
            default='*',
            verbose_name="Hashed SMB password"
            )
    bsdusr_group = models.ForeignKey(
            bsdGroups,
            verbose_name="Primary Group ID"
            )
    bsdusr_home = models.CharField(
            max_length=120,
            default="/nonexistent",
            verbose_name="Home Directory"
            )
    bsdusr_shell = models.CharField(
            max_length=120,
            default='/bin/csh',
            verbose_name="Shell"
            )
    bsdusr_full_name = models.CharField(
            max_length=120,
            verbose_name="Full Name"
            )
    bsdusr_builtin = models.BooleanField(
            default=False,
            )

    class Meta:
        verbose_name = "User"
    def __unicode__(self):
        return self.bsdusr_username

class bsdGroupMembership(models.Model):
    bsdgrpmember_group = models.ForeignKey(
        bsdGroups,
        verbose_name="Group",
    )
    bsdgrpmember_user = models.ForeignKey(
        bsdUsers,
        verbose_name="User",
    )
