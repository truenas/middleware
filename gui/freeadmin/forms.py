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

from django.forms.widgets import Widget, TextInput
from django.forms.util import flatatt
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext_lazy as _

from dojango import forms
from dojango.forms import widgets
from dojango.forms.widgets import DojoWidgetMixin
from freenasUI.common.freenasldap import FLAGS_DBINIT
from freenasUI.common.freenascache import (
    FLAGS_CACHE_READ_USER, FLAGS_CACHE_WRITE_USER, FLAGS_CACHE_READ_GROUP,
    FLAGS_CACHE_WRITE_GROUP
)
from freenasUI.common.freenasusers import (
    FreeNAS_Users, FreeNAS_User, FreeNAS_Groups, FreeNAS_Group
)
from freenasUI.storage.models import MountPoint

import ipaddr

MAC_RE = re.compile(r'^[0-9A-F]{12}$')


class CronMultiple(DojoWidgetMixin, Widget):
    dojo_type = 'freeadmin.form.Cron'

    def render(self, name, value, attrs=None):
        if value is None:
            value = ''
        final_attrs = self.build_attrs(
            attrs, name=name, **{'data-dojo-name': name}
        )
        final_attrs['value'] = force_unicode(value)
        if value.startswith('*/'):
            final_attrs['typeChoice'] = "every"
        elif re.search(r'^[0-9].*', value):
            final_attrs['typeChoice'] = "selected"
        return mark_safe(u'<div%s></div>' % (flatatt(final_attrs),))


class DirectoryBrowser(TextInput):
    def __init__(self, *args, **kwargs):
        dirsonly = kwargs.pop('dirsonly', True)
        kwargs.pop('filesonly', False)
        super(DirectoryBrowser, self).__init__(*args, **kwargs)
        self.attrs.update({
            'dojoType': 'freeadmin.form.PathSelector',
            'dirsonly': dirsonly,
        })


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
        from freenasUI.account.forms import FilteredSelectJSON
        users = FreeNAS_Users(
            flags=FLAGS_DBINIT | FLAGS_CACHE_READ_USER | FLAGS_CACHE_WRITE_USER
        )
        if len(users) > 500:
            if self.initial:
                self.choices = ((self.initial, self.initial),)
            kwargs = {}
            if len(self._exclude) > 0:
                kwargs['exclude'] = ','.join(self._exclude)
            self.widget = FilteredSelectJSON(
                url=("account_bsduser_json", None, (), kwargs)
            )
        else:
            ulist = []
            if not self.required:
                ulist.append(('-----', 'N/A'))
            ulist.extend(
                map(
                    lambda x: (x.pw_name, x.pw_name, ),
                    filter(
                        lambda y: (
                            y is not None and y.pw_name not in self._exclude
                        ),
                        users
                    )
                )
            )

            self.widget = widgets.FilteringSelect()
            self.choices = ulist

    def clean(self, user):
        if not self.required and user in ('-----', '', None):
            return None
        if FreeNAS_User(user, flags=FLAGS_DBINIT) is None:
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
        from freenasUI.account.forms import FilteredSelectJSON
        groups = FreeNAS_Groups(
            flags=FLAGS_DBINIT | FLAGS_CACHE_READ_GROUP |
            FLAGS_CACHE_WRITE_GROUP
        )
        if len(groups) > 500:
            if self.initial:
                self.choices = ((self.initial, self.initial),)
            self.widget = FilteredSelectJSON(url=("account_bsdgroup_json",))
        else:
            glist = []
            if not self.required:
                glist.append(('-----', 'N/A'))
            glist.extend(
                [(x.gr_name, x.gr_name) for x in groups]
            )
            self.widget = widgets.FilteringSelect()
            self.choices = glist

    def clean(self, group):
        if not self.required and group in ('-----', ''):
            return None
        if FreeNAS_Group(group, flags=FLAGS_DBINIT) is None:
            raise forms.ValidationError(
                _("The group %s is not valid.") % group
            )
        return group


class PathField(forms.CharField):

    def __init__(self, *args, **kwargs):
        self.dirsonly = kwargs.pop('dirsonly', True)
        self.filesonly = kwargs.pop('filesonly', False)
        if self.dirsonly and self.filesonly:
            raise ValueError("You cannot have dirsonly _and_ filesonly")
        self.abspath = kwargs.pop('abspath', True)
        self.includes = kwargs.pop('includes', [])
        self.widget = DirectoryBrowser(
            dirsonly=self.dirsonly,
            filesonly=self.filesonly
        )
        super(PathField, self).__init__(*args, **kwargs)

    def clean(self, value):
        if value not in ('', None):
            value = value.strip()
            absv = os.path.abspath(value)
            valid = False
            for mp in MountPoint.objects.all().values_list('mp_path',):
                if absv.startswith(mp[0] + '/') or absv == mp[0]:
                    valid = True
                    break
            if not valid and absv in self.includes:
                valid = True
            if not valid:
                raise forms.ValidationError(
                    _("The path must reside within a volume mount point")
                )
            if self.filesonly:
                if not(
                    os.path.exists(absv) and
                    (os.path.isfile(value) or os.path.islink(value))
                ):
                    raise forms.ValidationError(
                        _("A file is required")
                    )
            return value if not self.abspath else absv
        return value


class MACField(forms.CharField):

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 17
        super(MACField, self).__init__(*args, **kwargs)

    def clean(self, value):
        value = value.upper().replace(':', '')
        if value and not MAC_RE.search(value):
            raise forms.ValidationError("%s is not a valid MAC Address" % (
                value,
            ))
        value = super(MACField, self).clean(value)
        return value


class Network4Field(forms.CharField):

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 18  # 255.255.255.255/32
        super(Network4Field, self).__init__(*args, **kwargs)

    def clean(self, value):
        if not value:
            return value
        try:
            value = str(ipaddr.IPv4Network(value))
        except ipaddr.AddressValueError, e:
            raise forms.ValidationError(
                _("Invalid address: %s") % e
            )
        except ipaddr.NetmaskValueError, e:
            raise forms.ValidationError(
                _("Invalid network: %s") % e
            )
        value = super(Network4Field, self).clean(value)
        return value


class Network6Field(forms.CharField):

    def __init__(self, *args, **kwargs):
        # ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff/128
        kwargs['max_length'] = 43
        super(Network6Field, self).__init__(*args, **kwargs)

    def clean(self, value):
        if not value:
            return value
        try:
            value = str(ipaddr.IPv6Network(value))
        except ipaddr.AddressValueError, e:
            raise forms.ValidationError(
                _("Invalid address: %s") % e
            )
        except ipaddr.NetmaskValueError, e:
            raise forms.ValidationError(
                _("Invalid network: %s") % e
            )
        value = super(Network6Field, self).clean(value)
        return value


class WarningWidgetMixin(object):
    """
    This mixin for widgets adds a warning text above the widget

    The argument text is taken for that purpose
    """
    def __init__(self, *args, **kwargs):
        self.text = kwargs.pop('text')
        super(WarningWidgetMixin, self).__init__(*args, **kwargs)

    def render(self, *args, **kwargs):
        rendered = super(WarningWidgetMixin, self).render(*args, **kwargs)
        return u"%s<br />\n%s" % (self.text, rendered)


class WarningSelect(WarningWidgetMixin, forms.widgets.Select):
    pass
