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
        arr = []
        for i in self:
            arr.extend(getattr(i, fname)(*args, **kwargs))
        return arr

    def get_base_css(self, request):
        return self._get_array("base_css", request)

    def get_base_js(self, request):
        return self._get_array("base_js", request)

    def get_top_menu(self, request):
        return self._get_array("top_menu", request)


appPool = AppPool()
