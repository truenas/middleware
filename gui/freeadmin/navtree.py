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
# $FreeBSD$
#####################################################################
import re

from django.conf import settings
from django.db import models
from django.forms import ModelForm
from django.core.urlresolvers import resolve
from django.http import Http404
from django.utils.translation import ugettext_lazy as _

from freeadmin.tree import tree_roots, TreeRoot, TreeNode, TreeRoots

class NavTree(object):

    def __init__(self):
        self._modelforms = {}
        self._options = {}
        self._navs = {}
        self._generated = False

    def isGenerated(self):
        return self._generated

    def _get_module(self, where, name):
        try:
            mod = __import__('%s.%s' % (where,name), globals(), locals(), [name], -1)
            return mod
        except ImportError, e:
            return None

    """
    This is used for Mneu Item replacement

    Every option added to the tree register its name in a dict
    If the name was already registered before it can be replaced or not

    Return Value: Item has been added to the tree or not
    """
    def register_option(self, opt, parent, replace=False):

        if self._options.has_key(opt.gname) and opt.gname is not None:
            if replace is True:
                _opt = self._options[opt.gname]
                _opt.parent.remove_child(_opt)

                opt.attrFrom(_opt)
                parent.append_child(opt)
                self._options[opt.gname] = opt
                return True

        else:
            parent.append_child(opt)
            self._options[opt.gname] = opt
            return True

        return False

    def replace_navs(self, nav):

        if nav.gname is not None and self._navs.has_key(nav.gname) and \
                hasattr(self._navs[nav.gname], 'append_app') and \
                self._navs[nav.gname].append_app is False:
            if self._options.has_key(nav.gname):
                old  = self._options[nav.gname]
                self.register_option(self._navs[nav.gname], old.parent, True) 

        for subnav in nav:
            self.replace_navs(subnav)

    def register_option_byname(self, opt, name, replace=False):
        if self._options.has_key(name):
            nav = self._options[name]
            return self.register_option(opt, nav, replace)
        return False

    def titlecase(self, s):
        return re.sub(r"[A-Za-z]+('[A-Za-z]+)?",
                      lambda mo: mo.group(0)[0].upper() +
                                 mo.group(0)[1:],
                    s)

    def sort_navoption(self, nav):

        if not (hasattr(nav, 'order_child') and nav.order_child is False):

            new = {}
            order = {}
            opts = []
            for opt in nav:
                if hasattr(opt, 'order'):
                    order[opt.order] = opt
                else:
                    new[opt.name] = opt

            sort = new.keys()
            sort.sort()

            for opt in sort:
                opts.append(new[opt])
            nav._children = opts

            inserts = 0
            for opt in nav:
                if len(opt) == 0:
                    nav.remove_child(opt)
                    nav.insert_child(inserts, opt)
                    inserts += 1

            # TODO better order based on number attribute
            sort = order.keys()
            sort.sort()
            for key in sort:
                nav.insert_child(0, order[key])


        for opt in nav:
            self.sort_navoption(opt)

    """
    Tree Menu Auto Generate

    Every app listed at INSTALLED_APPS is scanned
    1st - app_name.forms is imported. All its objects/classes are scanned
        looking for ModelForm classes
    2nd - app_name.nav is imported. TreeNode classes are scanned for hard-coded
        menu entries or overwriting
    3rd - app_name.models is imported. models.Model classes are scanned, 
        if a related ModelForm is found several entries are Added to the Menu 
            - Objects
            - Add (Model)
            - View All (Model)
    """
    def auto_generate(self):

        self._generated = True
        self._modelforms.clear()
        self._options.clear()
        tree_roots.clear()
        for app in settings.INSTALLED_APPS:

            # If the app is listed at settings.BLACKLIST_NAV, skip it!
            if app in getattr(settings, 'BLACKLIST_NAV', []):
                continue

            # Thats the root node for the app tree menu
            nav = TreeRoot(app)
            nav.nav_group = 'main'
            tree_roots.register(nav) # We register it to the tree root

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

            """
            BEGIN
            This piece of code lookup all ModelForm classes from forms.py and record
            models as a dict key
            """
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
                        if _models.has_key(form._meta.model):
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
            """
            END
            """

            self._navs.clear()
            if modnav:
                modname = "%s.nav" % app
                for c in dir(modnav):
                    navc = getattr(modnav, c)
                    try:
                        subclass = issubclass(navc, TreeNode)
                    except TypeError:
                        continue
                    if navc.__module__ == modname and subclass:
                        obj = navc()
                        self._navs[navc.gname] = obj

                        if not( hasattr(navc, 'append_app') and navc.append_app is False ):
                            self.register_option(obj, nav, True)
                            #nav.append_child( navc() )
                            #continue

            modmodels = self._get_module(app, 'models')
            if modmodels:

                modname = '%s.models' % app
                for c in dir(modmodels):
                    if c in BLACKLIST:
                        continue
                    model = getattr(modmodels, c)
                    try:
                        subclass = issubclass(model, models.Model) 
                    except TypeError:
                        continue

                    if not(model.__module__ == modname and subclass \
                            and _models.has_key(model)
                          ):
                        continue

                    if model._admin.deletable is False:
                        navopt = TreeNode(u'%s.%s' % (app, str(model._meta.object_name)))
                        navopt.name = model._meta.verbose_name
                        navopt.model = c
                        navopt.app_name = app
                        try:
                            navopt.kwargs = {'app': app, 'model': c, 'oid': \
                                model.objects.order_by("-id")[0].id}
                            navopt.type = 'editobject'
                            navopt.view = 'freeadmin_model_edit'
                        except:
                            navopt.type = 'object'
                            navopt.view = 'freeadmin_model_add'
                            navopt.kwargs = {'app': app, 'model': c}

                        navopt.app = app
                    else:
                        navopt = TreeNode(u'%s.%s' % (app, str(model._meta.object_name)))
                        navopt.name = model._meta.verbose_name_plural
                        navopt.model = c
                        navopt.app_name = app
                        navopt.order_child = False
                        navopt.app = app
                    for key in model._admin.nav_extra.keys():
                        navopt.__setattr__(key, model._admin.nav_extra.get(key))
                    if model._admin.icon_model is not None:
                        navopt.icon = model._admin.icon_model

                    if model._admin.menu_child_of is not None:
                        reg = self.register_option_byname(navopt, model._admin.menu_child_of)
                    else:
                        reg = self.register_option(navopt, nav)

                    if reg and not hasattr(navopt, 'type'):

                        qs = model.objects.filter(**model._admin.object_filters).order_by('-id')
                        if qs.count() > 0:
                            if model._admin.object_num > 0:
                                qs = qs[:model._admin.object_num]
                            for e in qs:
                                subopt = TreeNode('%s.%s.Edit' % (app, str(model._meta.object_name)))
                                subopt.type = 'editobject'
                                subopt.view = u'freeadmin_model_edit'
                                if model._admin.icon_object is not None:
                                    subopt.icon = model._admin.icon_object
                                subopt.model = c
                                subopt.app_name = app
                                subopt.kwargs = {'app': app, 'model': c, 'oid': e.id}
                                try:
                                    subopt.name = unicode(e)
                                except:
                                    subopt.name = 'Object'
                                navopt.append_child(subopt)

                        # Node to add an instance of model
                        subopt = TreeNode('%s.%s.Add' % (app, str(model._meta.object_name)))
                        subopt.name = _(u'Add %s') % model._meta.verbose_name
                        subopt.view = u'freeadmin_model_add'
                        subopt.kwargs = {'app': app, 'model': c}
                        subopt.type = 'object'
                        if model._admin.icon_add is not None:
                            subopt.icon = model._admin.icon_add
                        subopt.model = c
                        subopt.app_name = app
                        self.register_option(subopt, navopt)

                        # Node to view all instances of model
                        subopt = TreeNode('%s.%s.View' % (app, str(model._meta.object_name)))
                        subopt.name = _(u'View All %s') % model._meta.verbose_name_plural
                        subopt.view = u'freeadmin_model_datagrid'
                        if model._admin.icon_view is not None:
                            subopt.icon = model._admin.icon_view
                        subopt.model = c
                        subopt.app_name = app
                        subopt.kwargs = {'app': app, 'model': c}
                        subopt.type = 'viewmodel'
                        self.register_option(subopt, navopt)

                        for child in model._admin.menu_children:
                            if self._navs.has_key(child):
                                self.register_option(self._navs[child], navopt)


            self.replace_navs(nav)
            self.sort_navoption(nav)

        nav = TreeRoot('Display')
        nav.name = _('Display System Processes')
        nav.nav_group = 'main'
        nav.action = 'displayprocs'
        nav.icon = 'TopIcon'
        tree_roots.register(nav)

        nav = TreeRoot('Shell')
        nav.name = _('Shell')
        nav.nav_group = 'main'
        nav.icon = 'TopIcon'
        nav.action = 'shell'
        tree_roots.register(nav)

        nav = TreeRoot('Reboot')
        nav.name = _('Reboot')
        nav.nav_group = 'main'
        nav.action = 'reboot'
        nav.icon = u'RebootIcon'
        tree_roots.register(nav)

        nav = TreeRoot('Shutdown')
        nav.name = _('Shutdown')
        nav.nav_group = 'main'
        nav.icon = 'ShutdownIcon'
        nav.action = 'shutdown'
        tree_roots.register(nav)

    def _build_nav(self):
        navs = []
        for nav in tree_roots['main']:
            nav.option_list = self.build_options(nav)
            nav.get_absolute_url()
            navs.append(nav)
        return navs

    def build_options(self, nav):
        options = []
        for option in nav:
            try:
                option = option()
            except:
                pass
            option.get_absolute_url()
            option.option_list = self.build_options(option)
            options.append(option)
        return options

    def dehydrate(self, o, level, uid):

        # info about current node
        my = {
            'id': str(uid.new()),
            'view': o.get_absolute_url(),
        }
        if hasattr(o, 'append_url'):
            my['view'] += o.append_url
        my['name'] = unicode(getattr(o, "rename", o.name))
        my['gname'] = getattr(o, "gname", my['name'])
        for attr in ('model', 'app', 'type', 'app_name', 'icon', 'action'):
            if hasattr(o, attr):
                my[attr] = getattr(o, attr)

        # this node has no childs
        if not o.option_list:
            return my
        else:
            my['children'] = []

        for i in o.option_list:
            opt = self.dehydrate(i, level+1, uid)
            my['children'].append(opt)

        return my

    def dijitTree(self):

        class ByRef(object):
            def __init__(self, val):
                self.val = val
            def new(self):
                old = self.val
                self.val += 1
                return old
        items = []
        uid = ByRef(1)
        for n in self._build_nav():
            items.append(self.dehydrate(n, level=0, uid=uid))
        return items

navtree = NavTree()

"""
If a model is delete it may dissapear from menu
so we must check it and regenerate if necessary!
"""
"""
### Disable automatic generation of menu based on events ###
def on_model_delete(**kwargs):
    if not navtree.isGenerated():
        return None
    model = kwargs['sender']
    instance = kwargs['instance']
    if model._meta.app_label in [app.split('.')[-1] for app in settings.BLACKLIST_NAV]:
        return None

    for nav in tree_roots['main']:
        handle_delete(nav, model, instance)

def handle_delete(nav, model, instance):
    for subnav in nav:
        if hasattr(subnav, 'kwargs') and hasattr(instance, 'id') and \
                subnav.kwargs.get('oid',-1) == instance.id and \
                subnav.kwargs.get('model', '-1') == model.__name__:
            navtree.auto_generate()
        else:
            handle_delete(subnav, model, instance)

def on_model_save(**kwargs):
    if not navtree.isGenerated():
        return None
    model = kwargs['sender']
    #instance = kwargs['instance']
    if model._meta.app_label in [app.split('.')[-1] for app in settings.BLACKLIST_NAV]:
        return None
    navtree.auto_generate()

from django.db.models.signals import post_delete, post_save
post_delete.connect(on_model_delete)
post_save.connect(on_model_save)
"""
