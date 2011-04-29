from django_nav import Nav, NavOption
from django.utils.translation import ugettext as _

ICON = u'SharingIcon'

class ViewUNIX(NavOption):

        name = _(u'View All UNIX Shares')
        type = 'openunixshares'
        icon = u'ViewAllUNIXSharesIcon'
        app_name = 'sharing'
        model = 'NFS_Share'
        append_app = False
        options = []

class ViewApple(NavOption):

        name = _(u'View All Apple Shares')
        type = 'openappleshares'
        icon = u'ViewAllAppleSharesIcon'
        app_name = 'sharing'
        model = 'AFP_Share'
        append_app = False
        options = []

class ViewWin(NavOption):

        name = _(u'View All Windows Shares')
        type = 'openwinshares'
        icon = u'ViewAllWindowsSharesIcon'
        app_name = 'sharing'
        model = 'CIFS_Share'
        append_app = False
        options = []
