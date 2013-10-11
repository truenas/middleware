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

    def hook_resource_bundle(self, rname, resource, bundle):
        return self._get_array(
            'hook_resource_bundle_%s' % rname, resource, bundle,
            _method=list.append
        )


appPool = AppPool()
