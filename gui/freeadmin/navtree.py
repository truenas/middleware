import os
import re

from django.conf import settings
from django_nav import nav_groups, Nav, NavOption, NavGroups
from django.db import models
from django.forms import ModelForm
from django.core.urlresolvers import resolve
from django.http import Http404
from django.utils.translation import ugettext as _

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
            #return getattr(mod, name)
            return mod
        except ImportError:
            return None

    """
    This is used for Mneu Item replacement
    
    Every option added to the tree register its name in a dict
    If the name was already registered before it can be replaced or not
    
    Return Value: Item has been added to the tree or not
    """
    def register_option(self, opt, parent, replace=False):
    
        if self._options.has_key(opt.name):
            if replace is True:
                _opt, _parent = self._options[opt.name]
                _parent.options.remove(_opt)
    
                parent.options.append(opt)
                self._options[opt.name] = opt, parent
                return True
    
        else:
            parent.options.append(opt)
            self._options[opt.name] = opt, parent
            return True
    
        return False
    
    def replace_navs(self, nav):
    
        if self._navs.has_key(nav.name) and \
                hasattr(self._navs[nav.name], 'append_app') and \
                self._navs[nav.name].append_app is False:
            if self._options.has_key(nav.name):
                old, parent = self._options[nav.name]
                self.register_option(self._navs[nav.name], parent, True) 
    
        for subnav in list(nav.options):
            self.replace_navs(subnav)
    
    def register_option_byname(self, opt, name, replace=False):
        if self._options.has_key(name):
            nav, par = self._options[name]
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
            for opt in nav.options:
                if hasattr(opt, 'order'):
                    order[opt.order] = opt
                else:
                    new[opt.name] = opt
    
            sort = new.keys()
            sort.sort()
    
            for opt in sort:
                opts.append(new[opt])
            nav.options = opts
    
            inserts = 0
            for opt in nav.options:
                if len(opt.options) == 0:
                    nav.options.remove(opt)
                    nav.options.insert(inserts, opt)
                    inserts += 1
    
            # TODO better order based on number attribute
            sort = order.keys()
            sort.sort()
            for key in sort:
                nav.options.insert(0, order[key])
    
    
        for opt in nav.options:
            self.sort_navoption(opt)
    
    """
    Tree Menu Auto Generate
    
    Every app listed at INSTALLED_APPS is scanned
    1st - app_name.forms is imported. All its objects/classes are scanned
        looking for ModelForm classes
    2nd - app_name.nav is imported. NavOption classes are scanned for hard-coded
        menu entries or overwriting
    3rd - app_name.models is imported. models.Model classes are scanned, 
        if a related ModelForm is found several entries are Added to the Menu 
            - Add (Model)
            - View All (Model)
            - First 2 entries
    """
    def auto_generate(self):
    
        self._generated = True
        self._modelforms.clear()
        self._options.clear()
        nav_groups._groups = {}
        for app in settings.INSTALLED_APPS:
    
            # If the app is listed at settings.BLACKLIST_NAV, skip it!
            if app in getattr(settings, 'BLACKLIST_NAV', []):
                continue
    
            # Thats the root node for the app tree menu
            nav = Nav()
            nav.name = self.titlecase(app)
            nav.nav_group = 'main'
            nav.options = []
            nav_groups.register(nav) # We register it to the tree root
    
            modnav = self._get_module(app, 'nav')
            if hasattr(modnav, 'BLACKLIST'):
                BLACKLIST = modnav.BLACKLIST
            else:
                BLACKLIST = []

            if hasattr(modnav, 'ICON'):
                nav.icon = modnav.ICON
    
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
                        subclass = issubclass(navc, NavOption)
                    except TypeError:
                        continue
                    if navc.__module__ == modname and subclass:
                        obj = navc()
                        self._navs[navc.name] = obj
    
                        if not( hasattr(navc, 'append_app') and navc.append_app is False ):
                            self.register_option(obj, nav, True)
                            #nav.options.append( navc() )
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
    
                    if model.__module__ == modname and subclass:
    
                        if _models.has_key(model):
    
                            if model._admin.deletable is False:
                                navopt = NavOption()
                                navopt.name = self.titlecase(unicode(model._meta.verbose_name))
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
                                navopt.options = []
                            else:
                                navopt = NavOption()
                                navopt.name = self.titlecase(unicode(model._meta.verbose_name_plural))
                                navopt.model = c
                                navopt.app_name = app
                                navopt.order_child = False
                                navopt.app = app
                                navopt.options = []
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
                                        subopt = NavOption()
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
                                        navopt.options.append(subopt)
                                        #register_option(subopt, navopt)
    
                                subopt = NavOption()
                                subopt.name = 'Add %s' % self.titlecase(unicode(model._meta.verbose_name))
                                subopt.view = u'freeadmin_model_add'
                                subopt.kwargs = {'app': app, 'model': c}
                                subopt.type = 'object'
                                if model._admin.icon_add is not None:
                                    subopt.icon = model._admin.icon_add
                                subopt.model = c
                                subopt.app_name = app
                                #navopt.options.append(subopt)
                                self.register_option(subopt, navopt)
    
                                subopt = NavOption()
                                subopt.name = 'View All %s' % self.titlecase(unicode(model._meta.verbose_name_plural))
                                subopt.view = u'freeadmin_model_datagrid'
                                if model._admin.icon_view is not None:
                                    subopt.icon = model._admin.icon_view
                                subopt.model = c
                                subopt.app_name = app
                                subopt.kwargs = {'app': app, 'model': c}
                                subopt.type = 'viewmodel'
                                #navopt.options.append(subopt)
                                self.register_option(subopt, navopt)
    
                        else:
                            pass
                            #print "ModelForm not found for", model
    
            self.replace_navs(nav)
            self.sort_navoption(nav)
    
        nav = Nav()
        nav.name = _('Display System Processes')
        nav.nav_group = 'main'
        nav.action = 'displayprocs'
        nav.icon = 'TopIcon'
        nav.options = []
        nav_groups.register(nav)
    
        nav = Nav()
        nav.name = _('Reboot')
        nav.nav_group = 'main'
        nav.action = 'reboot'
        nav.icon = u'RebootIcon'
        nav.options = []
        nav_groups.register(nav)
    
        nav = Nav()
        nav.name = _('Shutdown')
        nav.nav_group = 'main'
        nav.icon = 'ShutdownIcon'
        nav.action = 'shutdown'
        nav.options = []
        nav_groups.register(nav)

    def getmfs(self):
        print self._modelforms

    def _build_nav(self):

        navs = []
        for nav in nav_groups['main']:

            nav.option_list = self.build_options(nav.options)
            nav.active = True
            url = nav.get_absolute_url()
            navs.append(nav)

        return navs

    def build_options(self, nav_options):
        options = []
        for option in nav_options:
            try:
                option = option()
            except:
                pass
            url = option.get_absolute_url()
            #option.active = option.active_if(url, request.path)
            option.option_list = self.build_options(option.options)
            options.append(option)
        return options

    def sernav(self, o, **kwargs):

        items = []

        # info about current node
        my = {
            'id': str(kwargs['uid'].new()),
            'view': o.get_absolute_url(),
        }
        if hasattr(o, 'append_url'):
            my['view'] += o.append_url
        if hasattr(o, 'rename'):
            my['name'] = o.rename
        else:
            my['name'] = o.name
        for attr in ('model', 'app', 'type', 'app_name', 'icon', 'action'):
            if hasattr(o, attr):
                my[attr] = getattr(o, attr)

        # root nodes identified as type app
        if kwargs['level'] == 0:
            my['type'] = 'app'

        if not kwargs['parents'].has_key(kwargs['level']):
            kwargs['parents'][kwargs['level']] = []

        if kwargs['level'] > 0:
            kwargs['parents'][kwargs['level']].append(my['id'])

        # this node has no childs
        if o.option_list is None:
            return items

        for i in o.option_list:
            kwargs['level'] += 1
            opts = self.sernav(i, **kwargs)
            kwargs['level'] -= 1
            items += opts

        # if this node has childs
        # then we may found then in [parents][level+1]
        if len(o.option_list) > 0:
        
            my['children'] = []
            for all in kwargs['parents'][ kwargs['level']+1 ]:
                my['children'].append( {'_reference': all } )
                #kwargs['parents'][ kwargs['level']+1 ].remove(all)
            kwargs['parents'][ kwargs['level']+1 ] = []

        items.append(my)

        return items

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
            items += self.sernav(n, level=0, uid=uid, parents={})
        final = {
            'items': items,
            'label': 'name',
            'identifier': 'id',
        }
        return final

navtree = NavTree()

def _get_or_create(name, groups):

    for nav in groups['root']:
        if nav.name == name:
            return nav

    nav = Nav()
    nav.name = name
    nav.nav_group = 'main'
    nav.options = []
    groups.register(nav)
    return nav

def json2nav(jdata):
    import json
    data = json.loads(jdata)

    group = NavGroups()
    #group = nav_groups

    navs = {}
    for item in data['items']:
        
        navopt = NavOption()
        for attr in item:
            
            if attr in ['children', 'app']:
                continue

            if attr == 'view':
                try:
                    func, args, kwargs = resolve(item['view'])
                    navopt.view = func.__name__
                    navopt.args = args
                    navopt.kwargs = kwargs
                    pass
                except Http404:
                    pass
            else:
                navopt.__setattr__(attr, item[attr])

        navs[navopt.id] = navopt

        if item.has_key('children'):
            for dic in item['children']:
                id = dic["_reference"]
                navopt.options.append( navs[id] )
        if item.has_key('app'):
            app = _get_or_create(item['app'], group)
            app.options.append(navopt)

    return group


"""
If a model is delete it may dissapear from menu
so we must check oit and regenerate if necessary!
"""
def on_model_delete(**kwargs):
    if not navtree.isGenerated():
        return None
    model = kwargs['sender']
    instance = kwargs['instance']
    if model._meta.app_label in [app.split('.')[-1] for app in settings.BLACKLIST_NAV]:
        return None

    for nav in nav_groups['main']:
        handle_delete(nav, model, instance)

def handle_delete(nav, model, instance):
    for subnav in nav.options:
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
    instance = kwargs['instance']
    if model._meta.app_label in [app.split('.')[-1] for app in settings.BLACKLIST_NAV]:
        return None
    navtree.auto_generate()

from django.db.models.signals import post_delete, post_save
post_delete.connect(on_model_delete)
post_save.connect(on_model_save)
