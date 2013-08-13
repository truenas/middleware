#+
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
import json
import logging
import re

from django.conf import settings
from django.core.urlresolvers import NoReverseMatch, resolve
from django.db import models
from django.forms import ModelForm
from django.utils.translation import ugettext_lazy as _

import eventlet
from eventlet.green import urllib2
from freenasUI.common.log import log_traceback
from freenasUI.common.warden import (
    WARDEN_STATUS_RUNNING, WARDEN_TYPE_PLUGINJAIL
)
from freenasUI.freeadmin.tree import (
    tree_roots, TreeRoot, TreeNode, unserialize_tree
)
from freenasUI.jails.models import Jails
from freenasUI.middleware.notifier import notifier
from freenasUI.plugins.models import Plugins
from freenasUI.plugins.utils import get_base_url

log = logging.getLogger('freeadmin.navtree')


class ModelFormsDict(dict):

    def get(self, item, default=None):
        if item in self:
            return self[item]
        else:
            return default

    def __getitem__(self, item):
        item = item.__module__ + '.' + item._meta.object_name
        if not item.startswith('freenasUI'):
            item = 'freenasUI.' + item
        return dict.__getitem__(self, item)

    def __setitem__(self, item, val):
        item = item.__module__ + '.' + item._meta.object_name
        if not item.startswith('freenasUI'):
            item = 'freenasUI.' + item
        dict.__setitem__(self, item, val)

    def __contains__(self, key):
        key = key.__module__ + '.' + key._meta.object_name
        if not key.startswith('freenasUI'):
            key = 'freenasUI.' + key
        isin = dict.__contains__(self, key)
        return isin

    def update(self, d):
        for key, val in d.items():
            self[key] = val


class NavTree(object):

    def __init__(self):
        self._modelforms = ModelFormsDict()
        self._navs = {}
        self._generated = False

    def isGenerated(self):
        return self._generated

    def _get_module(self, where, name):
        try:
            mod = __import__(
                '%s.%s' % (where, name),
                globals(),
                locals(),
                [name],
                -1)
            return mod
        except ImportError:
            return None

    def register_option(self, opt, parent, replace=False, evaluate=True):
        """
        This is used for Menu Item replacement

        Every option added to the tree register its name in a dict
        If the name was already registered before it can be replaced or not

        Returns::
            bool: Item has been added to the tree or not
        """

        exists = False
        for i in parent:
            if i.gname == opt.gname:
                exists = i

        if exists is not False and replace is True:
            parent.remove_child(exists)
            opt.attrFrom(exists)
            parent.append_child(opt)
            return True

        elif exists is False:
            parent.append_child(opt)
            return True

        return False

    def replace_navs(self, root):

        for gname, opt in self._navs.items():

            for nav in root:
                find = nav.find_gname(gname)
                if find is not False:
                    parent = find.parent
                    parent.remove_child(find)
                    opt.attrFrom(find)
                    parent.append_child(opt)
                    break

    def titlecase(self, s):
        return re.sub(
            r"[A-Za-z]+('[A-Za-z]+)?",
            lambda mo: mo.group(0)[0].upper() + mo.group(0)[1:],
            s)

    def prepare_modelforms(self):
        """
        This piece of code lookup all ModelForm classes from forms.py
        and record models as a dict key
        """
        self._modelforms.clear()
        for app in settings.INSTALLED_APPS:

            _models = {}
            modforms = self._get_module(app, 'forms')

            if modforms:
                modname = "%s.forms" % app
                for c in dir(modforms):
                    form = getattr(modforms, c)
                    try:
                        subclass = issubclass(form, ModelForm)
                    except TypeError:
                        continue

                    if form.__module__ == modname and subclass:
                        if form._meta.model in _models:
                            if isinstance(_models[form._meta.model], dict):
                                _models[form._meta.model][form.__name__] = form
                            else:
                                tmp = _models[form._meta.model]
                                _models[form._meta.model] = {
                                    tmp.__name__: tmp,
                                    form.__name__: form,
                                }
                        else:
                            _models[form._meta.model] = form
            self._modelforms.update(_models)

    def generate(self, request=None):
        """
        Tree Menu Auto Generate

        Every app listed at INSTALLED_APPS is scanned
        1st - app_name.forms is imported. All its objects/classes are scanned
            looking for ModelForm classes
        2nd - app_name.nav is imported. TreeNode classes are scanned for
            hard-coded menu entries or overwriting
        3rd - app_name.models is imported. models.Model classes are scanned,
        if a related ModelForm is found several entries are Added to the Menu
                - Objects
                - Add (Model)
                - View (Model)
        """

        self._generated = True
        self._navs.clear()
        tree_roots.clear()
        childs_of = []
        for app in settings.INSTALLED_APPS:

            # If the app is listed at settings.BLACKLIST_NAV, skip it!
            if app in getattr(settings, 'BLACKLIST_NAV', []):
                continue

            try:
                self._generate_app(app, request, tree_roots, childs_of)
            except Exception, e:
                log.error(
                    "Failed to generate navtree for app %s: %s",
                    app,
                    e)
                log_traceback(log=log)

        nav = TreeRoot(
            'support',
            name=_('Request Support'),
            action='opensupport',
            icon='SupportIcon')
        tree_roots.register(nav)

        nav = TreeRoot(
            'display',
            name=_('Display System Processes'),
            action='displayprocs',
            icon='TopIcon')
        tree_roots.register(nav)

        nav = TreeRoot(
            'shell',
            name=_('Shell'),
            icon='ShellIcon',
            action='shell')
        tree_roots.register(nav)

        nav = TreeRoot(
            'reboot',
            name=_('Reboot'),
            action='reboot',
            icon='RebootIcon',
            type='scary_dialog',
            view='system_reboot_dialog')
        tree_roots.register(nav)

        nav = TreeRoot(
            'shutdown',
            name=_('Shutdown'),
            icon='ShutdownIcon',
            type='scary_dialog',
            view='system_shutdown_dialog')
        tree_roots.register(nav)

        for opt, model in childs_of:
            for nav in tree_roots:
                exists = nav.find_gname(model._admin.menu_child_of)
                if exists is not False:
                    exists.append_child(opt)
                    break
            if exists is False:
                log.debug(
                    "Could not find %s to attach %r",
                    model._admin.menu_child_of,
                    opt)

        self.replace_navs(tree_roots)

        jails = []
        #FIXME: use .filter
        for j in Jails.objects.all():
            if j.jail_type == WARDEN_TYPE_PLUGINJAIL and \
                j.jail_status == WARDEN_STATUS_RUNNING:
                jails.append(j)
        self._get_plugins_nodes(request, jails)

    def _generate_app(self, app, request, tree_roots, childs_of):

        # Thats the root node for the app tree menu
        nav = TreeRoot(app.split(".")[-1])

        modnav = self._get_module(app, 'nav')
        if hasattr(modnav, 'BLACKLIST'):
            BLACKLIST = modnav.BLACKLIST
        else:
            BLACKLIST = []

        if hasattr(modnav, 'ICON'):
            nav.icon = modnav.ICON

        if hasattr(modnav, 'NAME'):
            nav.name = modnav.NAME
        else:
            nav.name = self.titlecase(app)

        if hasattr(modnav, 'TYPE'):
            nav.type = modnav.TYPE

        if modnav:
            modname = "%s.nav" % app
            for c in dir(modnav):
                navc = getattr(modnav, c)
                try:
                    subclass = issubclass(navc, TreeNode)
                except TypeError:
                    continue
                if navc.__module__ == modname and subclass:
                    obj = navc(request=request)

                    if obj.skip is True:
                        continue
                    if not obj.append_to:
                        self.register_option(obj, nav, replace=True)
                    else:
                        self._navs[obj.append_to + '.' + obj.gname] = obj

            tree_roots.register(nav)  # We register it to the tree root
            if hasattr(modnav, 'init'):
                modnav.init(tree_roots, nav, request)

        else:
            log.debug("App %s has no nav.py module, skipping", app)
            return

        modmodels = self._get_module(app, 'models')
        if modmodels:

            modname = '%s.models' % app
            for c in dir(modmodels):

                model = getattr(modmodels, c)
                try:
                    if issubclass(model, models.Model):
                        if model._meta.app_label == app:
                            continue
                    else:
                        continue
                except TypeError, e:
                    continue

                if c in BLACKLIST:
                    log.debug(
                        "Model %s from app %s blacklisted, skipping",
                        c,
                        app,
                    )
                    continue

                if not (
                    model.__module__ in (
                        modname,
                        'freenasUI.' + modname,
                    )
                    and
                    model in self._modelforms
                ):
                    log.debug("Model %s does not have a ModelForm", model)
                    continue

                if model._admin.deletable is False:
                    navopt = TreeNode(
                        str(model._meta.object_name),
                        name=model._meta.verbose_name,
                        model=c, app_name=app, type='dialog')
                    try:
                        navopt.kwargs = {
                            'oid': model.objects.order_by("-id")[0].id,
                        }
                        navopt.view = 'freeadmin_%s_%s_edit' % (
                            model._meta.app_label,
                            model._meta.module_name,
                        )
                    except:
                        navopt.view = 'freeadmin_%s_%s_add' % (
                            model._meta.app_label,
                            model._meta.module_name,
                        )

                else:
                    navopt = TreeNode(str(model._meta.object_name))
                    navopt.name = model._meta.verbose_name_plural
                    navopt.model = c
                    navopt.app_name = app
                    navopt.order_child = False

                for key in model._admin.nav_extra.keys():
                    navopt.__setattr__(
                        key,
                        model._admin.nav_extra.get(key))
                if model._admin.icon_model is not None:
                    navopt.icon = model._admin.icon_model

                if model._admin.menu_child_of is not None:
                    childs_of.append((navopt, model))
                    reg = True
                else:
                    reg = self.register_option(navopt, nav)

                if reg and not navopt.type:

                    qs = model.objects.filter(
                        **model._admin.object_filters).order_by('-id')
                    if qs.count() > 0:
                        if model._admin.object_num > 0:
                            qs = qs[:model._admin.object_num]
                        for e in qs:
                            subopt = TreeNode('Edit')
                            subopt.type = 'editobject'
                            subopt.view = 'freeadmin_%s_%s_edit' % (
                                model._meta.app_label,
                                model._meta.module_name,
                            )
                            if model._admin.icon_object is not None:
                                subopt.icon = model._admin.icon_object
                            subopt.model = c
                            subopt.app_name = app
                            subopt.kwargs = {
                                'oid': e.id,
                            }
                            subopt.gname = e.id
                            try:
                                subopt.name = unicode(e)
                            except:
                                subopt.name = 'Object'
                            navopt.append_child(subopt)

                    # Node to add an instance of model
                    subopt = TreeNode('Add')
                    subopt.name = _(u'Add %s') % model._meta.verbose_name
                    subopt.view = 'freeadmin_%s_%s_add' % (
                        model._meta.app_label,
                        model._meta.module_name,
                    )
                    subopt.order = 500
                    subopt.type = 'dialog'
                    if model._admin.icon_add is not None:
                        subopt.icon = model._admin.icon_add
                    subopt.model = c
                    subopt.app_name = app
                    self.register_option(subopt, navopt)

                    # Node to view all instances of model
                    subopt = TreeNode('View')
                    subopt.name = _(u'View %s') % (
                        model._meta.verbose_name_plural,
                    )
                    subopt.view = u'freeadmin_%s_%s_datagrid' % (
                        model._meta.app_label,
                        model._meta.module_name,
                    )
                    if model._admin.icon_view is not None:
                        subopt.icon = model._admin.icon_view
                    subopt.model = c
                    subopt.app_name = app
                    subopt.order = 501
                    subopt.type = 'viewmodel'
                    self.register_option(subopt, navopt)

    def _plugin_fetch(self, args):
        plugin, host, request = args
        data = None
        url = "%s/plugins/%s/%d/_s/treemenu" % (host, plugin.plugin_name, plugin.id)
        try:
            opener = urllib2.build_opener()
            opener.addheaders = [(
                'Cookie', 'sessionid=%s' % (
                    request.COOKIES.get("sessionid", ''),
                )
            )]
            #TODO: Increase timeout based on number of plugins
            response = opener.open(url, None, 5)
            data = response.read()
            if not data:
                log.warn(_("Empty data returned from %s") % (url,))
        except Exception, e:
            log.warn(_("Couldn't retrieve %(url)s: %(error)s") % {
                'url': url,
                'error': e,
            })
        return plugin, url, data

    def _get_plugins_nodes(self, request, jails):

        host = get_base_url(request)
        args = map(
            lambda y: (y, host, request),
            Plugins.objects.filter(plugin_enabled=True, plugin_jail__in=[jail.jail_host for jail in jails]))

        pool = eventlet.GreenPool(20)
        for plugin, url, data in pool.imap(self._plugin_fetch, args):

            if not data:
                continue

            try:
                data = json.loads(data)

                nodes = unserialize_tree(data)
                for node in nodes:
                    #We have our TreeNode's, find out where to place them

                    found = False
                    if node.append_to:
                        log.debug(
                            "Plugin %s requested to be appended to %s",
                            plugin.plugin_name, node.append_to)
                        places = node.append_to.split('.')
                        places.reverse()
                        for root in tree_roots:
                            find = root.find_place(list(places))
                            if find is not None:
                                find.append_child(node)
                                found = True
                                break
                    else:
                        log.debug(
                            "Plugin %s didn't request to be appended "
                            "anywhere specific",
                            plugin.plugin_name)

                    if not found:
                        tree_roots.register(node)

            except Exception, e:
                log.warn(_(
                    "An error occurred while unserializing from "
                    "%(url)s: %(error)s") % {'url': url, 'error': e})
                log.debug(_(
                    "Error unserializing %(url)s (%(error)s), data "
                    "retrieved:") % {
                        'url': url,
                        'error': e,
                    })
                continue

    def _build_nav(self, user):
        navs = []
        for nav in tree_roots['main']:
            nav.option_list = self.build_options(nav, user)
            nav.get_absolute_url()
            navs.append(nav)
        return navs

    def build_options(self, nav, user):
        options = []
        for option in nav:
            try:
                option = option()
            except:
                pass

            if not option.perm:
                try:
                    url = option.get_absolute_url()
                except NoReverseMatch, e:
                    log.warn(_(
                        "Could not reverse url, skipping node %(node)s: "
                        "%(error)s") % {
                            'node': repr(option),
                            'error': repr(e),
                        })
                    continue
                try:
                    view, args, kwargs = resolve(url)
                    if hasattr(view, 'permission'):
                        perm = view.permission
                    else:
                        raise
                except:
                    perm = None
            else:
                perm = option.perm

            valid = True
            if perm and not user.has_perm(perm):
                valid = False

            if valid and option.permission(user):
                option.get_absolute_url()
                option.option_list = self.build_options(option, user)
                options.append(option)
        return options

    def dehydrate(self, o, uid, gname=None):

        o.pre_dehydrate()

        # info about current node
        my = {
            'id': str(uid.new()),
            'name': unicode(getattr(o, "rename", o.name)),
        }
        if gname:
            my['gname'] = "%s.%s" % (gname, o.gname)
        else:
            my['gname'] = getattr(o, "gname", my['name'])

        if not o.option_list:
            my['type'] = getattr(o, 'type', None)
            my['url'] = o.get_absolute_url()
            if o.append_url:
                my['url'] += o.append_url
        for attr in ('model', 'app_name', 'icon', 'action'):
            value = getattr(o, attr)
            if value:
                my[attr] = value

        # this node has no children
        if not o.option_list:
            return my

        my['children'] = []
        for i in o.option_list:
            opt = self.dehydrate(i, uid, gname=my['gname'])
            my['children'].append(opt)

        return my

    def dijitTree(self, user):

        class ByRef(object):
            def __init__(self, val):
                self.val = val

            def new(self):
                old = self.val
                self.val += 1
                return old
        items = []
        uid = ByRef(1)
        for n in self._build_nav(user):
            items.append(self.dehydrate(n, uid=uid))
        return items

navtree = NavTree()
