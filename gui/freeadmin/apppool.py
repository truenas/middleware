import logging

log = logging.getLogger('freeadmin.apppool')


class AppPool(object):

    def __init__(self):
        self._registered = {}

    def __iter__(self):
        for i in list(self._registered.values()):
            yield i

    def register(self, hook):
        self._registered[hook.name] = hook()

    def get_app(self, name):
        return self._registered[name]

    def _get_array(self, fname, cname, *args, **kwargs):
        method = kwargs.pop('_method', list.extend)
        arr = []
        for i in self:
            func = getattr(i, '%s_%s' % (fname, cname), None)
            if func and callable(func):
                method(arr, func(*args, **kwargs))
                continue

            func = getattr(i, fname, None)
            if func and callable(func):
                if cname:
                    method(arr, func(cname, *args, **kwargs))
                else:
                    method(arr, func(*args, **kwargs))
        return arr

    def get_base_css(self, request):
        return self._get_array("base_css", None, request)

    def get_base_js(self, request):
        return self._get_array("base_js", None, request)

    def get_top_menu(self, request):
        arr = self._get_array("top_menu", None, request)
        arr = sorted(arr, key=lambda x: x.get('weight'))
        return arr

    def get_system_info(self, request):
        return self._get_array("system_info", None, request)

    def hook_app_index(self, name, request):
        return self._get_array(
            'hook_app_index', name, request,
            _method=list.append
        )

    def hook_view_context(self, name, request):
        return self._get_array(
            'hook_view_context', name, request,
        )

    def hook_app_tabs(self, name, request):
        return self._get_array('hook_app_tabs', name, request)

    def hook_class_new(self, name, bases, attrs):
        return self._get_array(
            'hook_class_new', name, bases, attrs,
            _method=list.append
        )

    def hook_datagrid_actions(self, rname, admin, actions):
        return self._get_array(
            'hook_datagrid_actions', rname, admin, actions,
            _method=list.append
        )

    def hook_datagrid_buttons(self, rname, admin):
        return self._get_array(
            'hook_datagrid_buttons', rname, admin,
        )

    def hook_feature_disabled(self, name):
        return True in self._get_array(
            'hook_feature_disabled', name,
            _method=list.append
        )

    def hook_form_buttons(self, fname, form, action, *args, **kwargs):
        return self._get_array(
            'hook_form_buttons', fname, form, action, *args, **kwargs
        )

    def hook_form_delete(self, fname, form, request, events):
        return self._get_array(
            'hook_form_delete', fname, form, request, events,
            _method=list.append
        )

    def hook_form_done(self, fname, form, request, events):
        return self._get_array(
            'hook_form_done', fname, form, request, events,
            _method=list.append
        )

    def hook_form_init(self, fname, form, *args, **kwargs):
        kwargs['_method'] = list.append
        return self._get_array(
            'hook_form_init', fname, form, *args, **kwargs
        )

    def hook_model_new(self, name, bases, attrs):
        return self._get_array(
            'hook_model_new', name, bases, attrs,
            _method=list.append
        )

    def hook_nav_init(self, app, tree_roots, nav, request):
        return self._get_array(
            'hook_nav_init', app, tree_roots, nav, request,
            _method=list.append
        )

    def hook_resource_bundle(self, rname, resource, bundle):
        return self._get_array(
            'hook_resource_bundle', rname, resource, bundle,
            _method=list.append
        )

    def hook_tool_run(self, name):
        return self._get_array(
            'hook_tool_run', name,
            _method=list.append
        )


appPool = AppPool()
