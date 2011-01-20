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
            max_length=120,
            verbose_name="Group"
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
            verbose_name="Username"
            )
    bsdusr_password = models.CharField(
            max_length=128,
            verbose_name="Password"
            )
    bsdusr_gid = models.ManyToManyField(
            bsdGroups, 
            verbose_name="Group ID"
            )
    bsdusr_home = models.CharField(
            max_length=120,
            verbose_name="Home Directory"
            )
    bsdusr_shell = models.CharField(
            max_length=120,
            choices=UserShell,
            default="csh",
            verbose_name="Shell"
            )
    bsdusr_full_name = models.CharField(
            max_length=120,
            verbose_name="Full Name"
            )

    def set_password(self, raw_password):
        import random
        algo = 'sha1'
        salt = get_hexdigest(algo, str(random.random()), str(random.random()))[:5]
        hsh = get_hexdigest(algo, salt, raw_password)
        self.bsdusr_password = '%s$%s$%s' % (algo, salt, hsh)

    def check_password(self, raw_password):
        """
        Returns a boolean of whether the raw_password was correct. Handles
        encryption formats behind the scenes.
        """
        # Backwards-compatibility check. Older passwords won't include the
        # algorithm or salt.
        if '$' not in self.bsdusr_password:
            is_correct = (self.bsdusr_password == get_hexdigest('md5', '', raw_password))
            if is_correct:
                # Convert the password to the new, more secure format.
                self.set_password(raw_password)
                self.save()
            return is_correct
        return check_password(raw_password, self.bsdusr_password)

    def set_unusable_password(self):
        # Sets a value that will never be a valid hash
        self.bsdusr_password = UNUSABLE_PASSWORD

    def has_usable_password(self):
        return self.bsdusr_password != UNUSABLE_PASSWORD


    class Meta:
        verbose_name = "User"
    def __unicode__(self):
        return self.bsdusr_username


