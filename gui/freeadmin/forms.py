#+
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
import os
import re

from django.forms.widgets import Widget
from django.forms.util import flatatt
from django.utils.safestring import mark_safe
from django.utils.encoding import StrAndUnicode, force_unicode
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from dojango.forms.widgets import DojoWidgetMixin
from dojango import forms
from dojango.forms import widgets
from freenasUI.common.freenasldap import FLAGS_DBINIT, FLAGS_CACHE_READ_USER, \
    FLAGS_CACHE_WRITE_USER, FLAGS_CACHE_READ_GROUP, FLAGS_CACHE_WRITE_GROUP
from freenasUI.common.freenasusers import FreeNAS_Users, FreeNAS_User, \
                                         FreeNAS_Groups, FreeNAS_Group
from account.forms import FilteredSelectJSON
from storage.models import MountPoint

class CronMultiple(DojoWidgetMixin, Widget):
    dojo_type = 'freeadmin.form.Cron'
    def render(self, name, value, attrs=None):
        if value is None: value = ''
        final_attrs = self.build_attrs(attrs, name=name)
        final_attrs['value'] = force_unicode(value)
        if value.startswith('*/'):
            final_attrs['typeChoice'] = "every"
        elif re.search(r'^[0-9].*',value):
            final_attrs['typeChoice'] = "selected"
        return mark_safe(u'<div%s></div>' % (flatatt(final_attrs),))

class DirectoryBrowser(widgets.Widget):
    def __init__(self, *args, **kwargs):
        self._dirsonly = kwargs.pop('dirsonly', True)
        super(DirectoryBrowser, self).__init__(*args, **kwargs)
    def render(self, name, value, attrs=None):
        context = {
            'name': name,
            'value': value,
            'attrs': attrs,
            'dirsonly': self._dirsonly,
            }
        return mark_safe(render_to_string('freeadmin/directory_browser.html', context))

class UserField(forms.ChoiceField):
    widget = widgets.Select()

    def __init__(self, *args, **kwargs):
        kwargs.pop('max_length', None)
        self._exclude = kwargs.pop('exclude', [])
        super(UserField, self).__init__(*args, **kwargs)

    def prepare_value(self, value):
        rv = super(UserField, self).prepare_value(value)
        user = FreeNAS_User(rv)
        if rv and not user:
            return 'nobody'
        return rv

    def _reroll(self):
        if len(FreeNAS_Users(flags=FLAGS_DBINIT|FLAGS_CACHE_READ_USER|FLAGS_CACHE_WRITE_USER)) > 500:
            if self.initial:
                self.choices = ((self.initial, self.initial),)
            kwargs = {}
            if len(self._exclude) > 0:
                kwargs['exclude'] = ','.join(self._exclude)
            self.widget = FilteredSelectJSON(url=("account_bsduser_json", None, (), kwargs))
        else:
            ulist = []
            if not self.required:
                ulist.append(('-----', 'N/A'))
            ulist.extend(map(lambda x: (x.pw_name, x.pw_name, ),
                             filter(lambda y: y.pw_name not in self._exclude,
                                              FreeNAS_Users(flags=FLAGS_DBINIT|FLAGS_CACHE_READ_USER|FLAGS_CACHE_WRITE_USER))))

            self.widget = widgets.FilteringSelect()
            self.choices = ulist


    def clean(self, user):
        if not self.required and user in ('-----',''):
            return None
        if FreeNAS_User(user, flags=FLAGS_DBINIT) == None:
            raise forms.ValidationError(_("The user %s is not valid.") % user)
        return user

class GroupField(forms.ChoiceField):
    widget = widgets.Select()

    def __init__(self, *args, **kwargs):
        kwargs.pop('max_length', None)
        super(GroupField, self).__init__(*args, **kwargs)

    def prepare_value(self, value):
        rv = super(GroupField, self).prepare_value(value)
        group = FreeNAS_Group(rv)
        if rv and not group:
            return 'nobody'
        return rv

    def _reroll(self):
        if len(FreeNAS_Groups(flags=FLAGS_DBINIT|FLAGS_CACHE_READ_GROUP|FLAGS_CACHE_WRITE_GROUP)) > 500:
            if self.initial:
                self.choices = ((self.initial, self.initial),)
            self.widget = FilteredSelectJSON(url=("account_bsdgroup_json",))
        else:
            glist = []
            if not self.required:
                glist.append(('-----', 'N/A'))
            glist.extend([(x.gr_name, x.gr_name) for x in FreeNAS_Groups(flags=FLAGS_DBINIT|FLAGS_CACHE_READ_GROUP|FLAGS_CACHE_WRITE_GROUP)])
            self.widget = widgets.FilteringSelect()
            self.choices = glist

    def clean(self, group):
        if not self.required and group in ('-----',''):
            return None
        if FreeNAS_Group(group, flags=FLAGS_DBINIT) == None:
            raise forms.ValidationError(_("The group %s is not valid.") % group)
        return group

class PathField(forms.CharField):
    def __init__(self, *args, **kwargs):
        dirsonly = kwargs.pop('dirsonly', True)
        self.widget = DirectoryBrowser(dirsonly=dirsonly)
        super(PathField, self).__init__(*args, **kwargs)
    def clean(self, value):
        if value not in ('', None):
            value = os.path.abspath(value)
            valid = False
            for mp in MountPoint.objects.all().values_list('mp_path',):
                if value.startswith(mp[0]+'/') or value == mp[0]:
                    valid = True
                    break
            if not valid:
                raise forms.ValidationError(_("The path must reside within a volume mount point"))
        return value
