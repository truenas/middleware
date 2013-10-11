import logging

log = logging.getLogger('freeadmin.hook')


class AppHook(object):

    name = None

    def base_css(self, request):
        """
        List of css files to be appended to the base template
        Path within STATIC_URL
        """
        return []

    def base_js(self, request):
        """
        List of javascript files to be appended to the base template
        Path within STATIC_URL
        """
        return []

    def top_menu(self, request):
        """
        Items to be placed in the top menu bar

        Returns: list(dict)
          - name - name to be displayed
          - icon - path to the icon, within STATIC_URL
          - onclick - javascript code to run on mouse click
          - weight - order of the menu
        """
        return []

    def system_menu(self, request):
        """
        Items to be placed in the system info screen

        Returns: list(dict)
         - name: name to be displayed
         - value: value to show
        """
        return []

    """
    def hook_form_done_<FormName>(self, request, events):
        pass
    """

    """
    def hook_form_delete_<FormName>(self, form, request, events):
        pass
    """

    """
    def hook_resource_bundle_<ResourceName>(self, resource, bundle):
        pass
    """
