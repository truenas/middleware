import logging

log = logging.getLogger('freeadmin.apppool')


class AppPool(object):

    def __init__(self):
        self._registered = {}

    def __iter__(self):
        for i in self._registered.values():
            yield i

    def register(self, hook):
        self._registered[hook.name] = hook()

    def _get_array(self, fname, *args, **kwargs):
        method = kwargs.pop('_method', list.extend)
        arr = []
        for i in self:
            func = getattr(i, fname, None)
            if func and callable(func):
                method(arr, func(*args, **kwargs))
        return arr

    def get_base_css(self, request):
        return self._get_array("base_css", request)

    def get_base_js(self, request):
        return self._get_array("base_js", request)

    def get_top_menu(self, request):
        return self._get_array("top_menu", request)

    def get_system_info(self, request):
        return self._get_array("system_info", request)

    def hook_app_tabs(self, name, request):
        return self._get_array('hook_app_tabs_%s' % name, request)

    def hook_class_new(self, name, bases, attrs):
        return self._get_array(
            'hook_class_new_%s' % name, bases, attrs,
            _method=list.append
        )

    def hook_datagrid_actions(self, rname, admin, actions):
        return self._get_array(
            'hook_datagrid_actions_%s' % rname, admin, actions,
            _method=list.append
        )

    def hook_datagrid_buttons(self, rname, admin):
        return self._get_array(
            'hook_datagrid_buttons_%s' % rname, admin,
        )

    def hook_form_init(self, fname, form, *args, **kwargs):
        kwargs['_method'] = list.append
        return self._get_array(
            'hook_form_init_%s' % fname, form, *args, **kwargs
        )

    def hook_form_delete(self, fname, form, request, events):
        return self._get_array(
            'hook_form_delete_%s' % fname, form, request, events,
            _method=list.append
        )

    def hook_form_done(self, fname, request, events):
        return self._get_array(
            'hook_form_done_%s' % fname, request, events,
            _method=list.append
        )

    def hook_model_new(self, name, bases, attrs):
        return self._get_array(
            'hook_model_new_%s' % name, bases, attrs,
            _method=list.append
        )

    def hook_nav_init(self, app, tree_roots, nav, request):
        return self._get_array(
            'hook_nav_init_%s' % app, tree_roots, nav, request,
            _method=list.append
        )

    def hook_resource_bundle(self, rname, resource, bundle):
        return self._get_array(
            'hook_resource_bundle_%s' % rname, resource, bundle,
            _method=list.append
        )


appPool = AppPool()
