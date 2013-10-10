import logging

log = logging.getLogger('freeadmin.hook')


class AppHook(object):

    def base_css(self, request):
        return []

    def base_js(self, request):
        return []
