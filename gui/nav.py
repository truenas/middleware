import os
import re
import copy

from django.conf import settings
#from django_nav.base import NavGroups
from django_nav import nav_groups, Nav, NavOption, NavGroups
from django.db import models
from django.forms import ModelForm
from django.core.urlresolvers import resolve
from django.http import Http404

_modelforms = {}
_options = {}

def _get_module(where, name):
    try:
        mod = __import__('%s.%s' % (where,name), globals(), locals(), [name], -1)
        #return getattr(mod, name)
        return mod
    except ImportError:
        return None

"""
If a model is delete it may dissapear from menu
so we must check oit and regenerate if necessary!
"""
def on_model_delete(**kwargs):
    model = kwargs['sender']
    instance = kwargs['instance']
    for nav in nav_groups['main']:
        if nav.name == model._meta.app_label:
            for subnav in nav.options:
                if subnav.name == model.__name__:
                    for subsubnav in subnav.options:
                        if subsubnav.kwargs.get('oid',-1) == instance.id:
                            #subnav.options.remove(subsubnav)
                            auto_generate()

from django.db.models.signals import post_delete
post_delete.connect(on_model_delete)


"""
This is used for Mneu Item replacement

Every option added to the tree register its name in a dict
If the name was already registered before it can be replaced or not

Return Value: Item has been added to the tree or not
"""
def register_option(opt, parent, replace=False):

    if _options.has_key(opt.name):
        if replace is True:
            _opt, _parent = _options[opt.name]
            _parent.options.remove(_opt)

            parent.options.append(opt)
            _options[opt.name] = opt, parent
            return True

    else:
        parent.options.append(opt)
        _options[opt.name] = opt, parent
        return True

    return False

def register_option_byname(opt, name, replace=False):
    if _options.has_key(name):
        nav, par = _options[name]
        return register_option(opt, nav, replace)
    return False

def titlecase(s):
    return re.sub(r"[A-Za-z]+('[A-Za-z]+)?",
                  lambda mo: mo.group(0)[0].upper() +
                             mo.group(0)[1:],
                s)

def sort_navoption(nav):


    if not (hasattr(nav, 'order_child') and nav.order_child is False):

        new = {}
        opts = []
        for opt in nav.options:
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

    for opt in nav.options:
        sort_navoption(opt)

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
def auto_generate():

    _modelforms.clear()
    _options.clear()
    nav_groups._groups = {}
    for app in settings.INSTALLED_APPS:

        # If the app is listed at settings.BLACKLIST_NAV, skip it!
        if app in getattr(settings, 'BLACKLIST_NAV', []):
            continue

        # Thats the root node for the app tree menu
        nav = Nav()
        nav.name = titlecase(app)
        nav.nav_group = 'main'
        nav.options = []
        nav_groups.register(nav) # We register it to the tree root


        modnav = _get_module(app, 'nav')
        if hasattr(modnav, 'BLACKLIST'):
            BLACKLIST = modnav.BLACKLIST
        else:
            BLACKLIST = []

        """
        BEGIN
        This piece of code lookup all ModelForm classes from forms.py and record
        models as a dict key
        """
        _models = {}
        modforms = _get_module(app, 'forms')

        if modforms:
            modname = "freenasUI.%s.forms" % app
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
        _modelforms.update(_models)
        """
        END
        """

        #_navs = {}
        if modnav:
            modname = "freenasUI.%s.nav" % app
            for c in dir(modnav):
                navc = getattr(modnav, c)
                if hasattr(navc, 'append_app') and navc.append_app is False:
                    continue
                try:
                    subclass = issubclass(navc, NavOption)
                except TypeError:
                    continue
                if navc.__module__ == modname and subclass:
                    register_option(navc(), nav, True)
                    #nav.options.append( navc() )
                    #_navs[navc.name] = navc()

        modmodels = _get_module(app, 'models')
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

                        if hasattr(model, 'FreeAdmin') and \
                                hasattr(model.FreeAdmin, 'deletable') and \
                                model.FreeAdmin.deletable is False:
                            navopt = NavOption()
                            navopt.name = titlecase(unicode(model._meta.verbose_name))
                            navopt.model = c
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
                            navopt.name = titlecase(unicode(model._meta.verbose_name_plural))
                            navopt.model = c
                            navopt.order_child = False
                            navopt.app = app
                            navopt.options = []

                        if hasattr(model, 'FreeAdmin') and \
                                hasattr(model.FreeAdmin, 'menu_child_of'):
                            print model.FreeAdmin.menu_child_of, model
                            reg = register_option_byname(navopt, model.FreeAdmin.menu_child_of)
                        else:
                            reg = register_option(navopt, nav)
                        #nav.options.append(navopt)
                        if reg and not hasattr(navopt, 'type'):

                            qs = model.objects.all().order_by('-id')
                            if qs.count() > 0:
                                for e in qs[:2]:
                                    subopt = NavOption()
                                    subopt.type = 'editobject'
                                    subopt.view = u'freeadmin_model_edit'
                                    subopt.kwargs = {'app': app, 'model': c, 'oid': e.id}
                                    try:
                                        subopt.name = str(e)
                                    except:
                                        subopt.name = 'Object'
                                    navopt.options.append(subopt)
                                    #register_option(subopt, navopt)

                            subopt = NavOption()
                            subopt.name = 'Add %s' % titlecase(unicode(model._meta.verbose_name))
                            subopt.view = u'freeadmin_model_add'
                            subopt.kwargs = {'app': app, 'model': c}
                            subopt.type = 'object'
                            #navopt.options.append(subopt)
                            register_option(subopt, navopt)

                            subopt = NavOption()
                            subopt.name = 'View All %s' % titlecase(unicode(model._meta.verbose_name_plural))
                            subopt.view = u'freeadmin_model_datagrid'
                            subopt.kwargs = {'app': app, 'model': c}
                            subopt.type = 'viewmodel'
                            #navopt.options.append(subopt)
                            register_option(subopt, navopt)

                    else:
                        print "ModelForm not found for", model

        sort_navoption(nav)


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
