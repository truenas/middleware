import logging

log = logging.getLogger('freeadmin.hook')


class AppHook(object):

    name = None

    def base_css(self, request):
        return []

    def base_js(self, request):
        return []

    def top_menu(self, request):
        return []

    """
    def hook_form_done_<FormName>(self, request, events):
        passs
    """

    """
    def hook_form_delete_<FormName>(self, form, request, events):
        passs
    """
