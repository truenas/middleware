#
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
import crypt
import logging
import os
import time

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.common.samba import Samba4
from freenasUI.common.system import domaincontroller_enabled
from freenasUI.freeadmin.models import DictField, Model, PathField
from freenasUI.middleware.client import client
from freenasUI.middleware.notifier import notifier

log = logging.getLogger('account.models')


class bsdGroups(Model):
    bsdgrp_gid = models.IntegerField(
        verbose_name=_("Group ID"),
        validators=[MinValueValidator(0), MaxValueValidator(4294967295)],
    )
    bsdgrp_group = models.CharField(
        unique=True,
        max_length=120,
        verbose_name=_("Group Name")
    )
    bsdgrp_builtin = models.BooleanField(
        default=False,
        editable=False,
        verbose_name=_("Built-in Group"),
    )
    bsdgrp_sudo = models.BooleanField(
        default=False,
        verbose_name=_("Permit Sudo"),
    )

    class Meta:
        verbose_name = _("Group")
        verbose_name_plural = _("Groups")
        ordering = ['bsdgrp_builtin', 'bsdgrp_group']

    def __str__(self):
        return self.bsdgrp_group

    def delete(self, using=None, reload=True, pwdelete=True):
        if self.bsdgrp_builtin is True:
            raise ValueError(_(
                "Group %s is built-in and can not be deleted!"
            ) % (self.bsdgrp_group))
        if pwdelete:
            notifier().user_deletegroup(self.bsdgrp_group)
        if domaincontroller_enabled():
            Samba4().group_delete(self.bsdgrp_group)
        super(bsdGroups, self).delete(using)
        if reload:
            notifier().reload("user")


def get_sentinel_group():
    return bsdGroups.objects.get(bsdgrp_group='nobody')


class UserManager(models.Manager):
    def get_by_natural_key(self, username):
        return self.get(**{self.model.USERNAME_FIELD: username})


class bsdUsers(Model):

    USERNAME_FIELD = 'bsdusr_username'
    REQUIRED_FIELDS = []

    bsdusr_uid = models.IntegerField(
        verbose_name=_("User ID"),
        validators=[MinValueValidator(0), MaxValueValidator(4294967295)],
    )
    bsdusr_username = models.CharField(
        max_length=16,
        unique=True,
        default=_('User &'),
        verbose_name=_("Username")
    )
    bsdusr_unixhash = models.CharField(
        max_length=128,
        blank=True,
        default='*',
        verbose_name=_("Hashed UNIX password")
    )
    bsdusr_smbhash = models.CharField(
        max_length=128,
        blank=True,
        default='*',
        verbose_name=_("Hashed SMB password")
    )
    bsdusr_group = models.ForeignKey(
        bsdGroups,
        on_delete=models.SET(get_sentinel_group),
        verbose_name=_("Primary Group ID")
    )
    bsdusr_home = PathField(
        default="/nonexistent",
        verbose_name=_("Home Directory"),
        includes=["/root", "/nonexistent"],
    )
    bsdusr_shell = models.CharField(
        max_length=120,
        default='/bin/csh',
        verbose_name=_("Shell"),
        choices=choices.SHELL_CHOICES(),
    )
    bsdusr_full_name = models.CharField(
        max_length=120,
        verbose_name=_("Full Name")
    )
    bsdusr_builtin = models.BooleanField(
        default=False,
        editable=False,
        verbose_name=_("Built-in User"),
    )
    bsdusr_email = models.EmailField(
        verbose_name=_("E-mail"),
        blank=True
    )
    bsdusr_password_disabled = models.BooleanField(
        verbose_name=_("Disable password login"),
        default=False,
        help_text=_(
            'This disables all forms of password login, including for sharing.'
        ),
    )
    bsdusr_locked = models.BooleanField(
        verbose_name=_("Lock user"),
        default=False,
    )
    bsdusr_sudo = models.BooleanField(
        verbose_name=_("Permit Sudo"),
        default=False,
    )
    bsdusr_microsoft_account = models.BooleanField(
        verbose_name=_("Microsoft Account"),
        default=False
    )
    bsdusr_attributes = DictField(
        default=None,
        editable=False,
    )

    is_active = True
    is_staff = True
    objects = UserManager()

    @classmethod
    def has_root_password(cls):
        qs = cls.objects.filter(bsdusr_uid=0).exclude(bsdusr_unixhash='*')
        return qs.exists()

    @property
    def bsdusr_sshpubkey(self):
        keysfile = '%s/.ssh/authorized_keys' % self.bsdusr_home
        if not os.path.exists(keysfile):
            return ''
        try:
            with open(keysfile, 'r') as f:
                keys = f.read()
            return keys
        except:
            return ''

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ['bsdusr_builtin', 'bsdusr_username']

    def __str__(self):
        return self.bsdusr_username

    def get_username(self):
        "Return the identifying username for this User"
        return getattr(self, self.USERNAME_FIELD)

    def natural_key(self):
        return (self.get_username(),)

    @property
    def is_anonymous(self):
        """
        Always returns False. This is a way of comparing User objects to
        anonymous users.
        """
        return False

    @property
    def is_authenticated(self):
        """
        Always return True. This is a way to tell if the user has been
        authenticated in templates.
        """
        return True

    def set_password(self, password):
        # Django auth backend calls set_password even if user doesnt exist
        if not self.bsdusr_username or not self.id:
            time.sleep(0.1)
            return
        with client as c:
            pk = c.call('user.update', self.id, {'password': password})
        user = bsdUsers.objects.get(pk=pk)
        self.bsdusr_unixhash = user.bsdusr_unixhash
        self.bsdusr_smbhash = user.bsdusr_smbhash

    def check_password(self, raw_password):
        # Only allow uid 0 for now
        if self.bsdusr_uid != 0:
            return False
        if self.bsdusr_unixhash:
            if self.bsdusr_unixhash == 'x' or self.bsdusr_unixhash == '*':
                return False
            if isinstance(raw_password, bytes):
                raw_password = raw_password.decode('utf-8')
            return crypt.crypt(
                raw_password, str(self.bsdusr_unixhash)
            ) == str(self.bsdusr_unixhash)

    def delete(self, using=None, reload=True, delete_group=True):
        from freenasUI.services.models import CIFS
        if self.bsdusr_builtin is True:
            raise ValueError(_(
                "User %s is built-in and can not be deleted!"
            ) % (self.bsdusr_username))
        notifier().user_deleteuser(self.bsdusr_username)
        if domaincontroller_enabled():
            Samba4().user_delete(self.bsdusr_username)
        try:
            gobj = self.bsdusr_group
            count = bsdGroupMembership.objects.filter(
                bsdgrpmember_group=gobj).count()
            count2 = bsdUsers.objects.filter(bsdusr_group=gobj).exclude(
                id=self.id).count()
            if delete_group and not gobj.bsdgrp_builtin and count == 0 and count2 == 0:
                gobj.delete(reload=False, pwdelete=False)
        except:
            log.warn('Failed to delete primary group of %s', self, exc_info=True)
        cifs = CIFS.objects.latest('id')
        if cifs:
            if cifs.cifs_srv_guest == self.bsdusr_username:
                cifs.cifs_srv_guest = 'nobody'
                cifs.save()
        super(bsdUsers, self).delete(using)
        if reload:
            notifier().reload("user")

    def save(self, *args, **kwargs):
        # TODO: Add last_login field
        if (
            'update_fields' in kwargs and
            'last_login' in kwargs['update_fields']
        ):
            kwargs['update_fields'].remove('last_login')
        super(bsdUsers, self).save(*args, **kwargs)


class bsdGroupMembership(Model):
    bsdgrpmember_group = models.ForeignKey(
        bsdGroups,
        verbose_name=_("Group"),
    )
    bsdgrpmember_user = models.ForeignKey(
        bsdUsers,
        verbose_name=_("User"),
    )

    class Meta:
        verbose_name = _("Group Membership")
        verbose_name_plural = _("Group Memberships")

    def __str__(self):
        return "%s:%s" % (
            self.bsdgrpmember_group.bsdgrp_group,
            self.bsdgrpmember_user.bsdusr_username,
        )
