from collections import OrderedDict

from django.utils.html import escapejs
from django.utils.translation import ugettext as _

from freenasUI.api.resources import (
    BsdUserResourceMixin, BsdGroupResourceMixin
)
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.account import models


class BsdUserFAdmin(BaseFreeAdmin):

    create_modelform = "bsdUserCreationForm"
    edit_modelform = "bsdUserChangeForm"

    object_filters = {'bsdusr_builtin__exact': False}
    object_num = -1

    icon_object = u"UserIcon"
    icon_model = u"UsersIcon"
    icon_add = u"AddUserIcon"
    icon_view = u"ViewAllUsersIcon"

    resource_mixin = BsdUserResourceMixin
    exclude_fields = (
        'id',
        'bsdusr_unixhash',
        'bsdusr_smbhash',
        )

    def _action_builder(self, name, label=None, url=None, builtin=None):
        func = "editObject"

        if url is None:
            url = "_%s_url" % (name, )

        if builtin is False:
            hide = "row.data.bsdusr_builtin == true"
        elif builtin is True:
            hide = "row.data.bsdusr_builtin == false"
        else:
            hide = "false"

        on_select_after = """function(evt, actionName, action) {
                for(var i=0;i < evt.rows.length;i++) {
                    var row = evt.rows[i];
                    if((%(hide)s)) {
                      query(".grid" + actionName).forEach(function(item, idx) {
                          domStyle.set(item, "display", "none");
                      });
                      break;
                    }
                }
            }""" % {
            'hide': hide,
            }

        on_click = """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    %(func)s('%(label)s', data.%(url)s, [mybtn,]);
                }
            }""" % {
            'func': func,
            'label': escapejs(label),
            'url': url,
        }

        data = {
            'button_name': label,
            'on_select_after': on_select_after,
            'on_click': on_click,
        }

        return data

    def get_actions(self):

        actions = OrderedDict()
        actions['Changewd'] = self._action_builder(
            "passwd",
            label=_('Change Password'),
        )
        actions['Edit'] = self._action_builder(
            "edit",
            label=_('Modify User'),
        )
        actions['Remove'] = self._action_builder(
            "delete",
            label=_('Remove User'),
            builtin=False,
        )
        actions['Auxiliary'] = self._action_builder(
            "auxiliary",
            label=_('Auxiliary Groups'),
        )
        actions['E-mail'] = self._action_builder(
            "email",
            label=_('Change E-mail'),
            builtin=True,
        )
        return actions


class BsdGroupFAdmin(BaseFreeAdmin):

    delete_form = "DeleteGroupForm"
    object_filters = {'bsdgrp_builtin__exact': False}
    object_num = -1

    icon_object = u"GroupIcon"
    icon_model = u"GroupsIcon"
    icon_add = u"AddGroupIcon"
    icon_view = u"ViewAllGroupsIcon"

    resource_mixin = BsdGroupResourceMixin

    def _action_builder(self, name, label=None, url=None, builtin=None):
        func = "editObject"

        if url is None:
            url = "_%s_url" % (name, )

        if builtin is False:
            hide = "row.data.bsdgrp_builtin == true"
        elif builtin is True:
            hide = "row.data.bsdgrp_builtin == false"
        else:
            hide = "false"

        on_select_after = """function(evt, actionName, action) {
                for(var i=0;i < evt.rows.length;i++) {
                    var row = evt.rows[i];
                    if((%(hide)s)) {
                      query(".grid" + actionName).forEach(function(item, idx) {
                          domStyle.set(item, "display", "none");
                      });
                      break;
                    }
                }
            }""" % {
            'hide': hide,
            }

        on_click = """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    %(func)s('%(label)s', data.%(url)s, [mybtn,]);
                }
            }""" % {
            'func': func,
            'label': escapejs(label),
            'url': url,
        }

        data = {
            'button_name': label,
            'on_select_after': on_select_after,
            'on_click': on_click,
        }

        return data

    def get_actions(self):

        actions = OrderedDict()
        actions['Members'] = self._action_builder(
            "members",
            label=_('Members'),
        )
        actions['Modify'] = self._action_builder(
            "edit",
            label=_('Modify Group'),
            builtin=False,
        )
        actions['Remove'] = self._action_builder(
            "delete",
            label=_('Delete Group'),
            builtin=False,
        )
        return actions


site.register(models.bsdUsers, BsdUserFAdmin)
site.register(models.bsdGroups, BsdGroupFAdmin)
