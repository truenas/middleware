from django_nav import Nav, NavOption

BLACKLIST = ['services','UPS']
ICON = u'ServicesIcon'

class ISCSI(NavOption):

        name = u'ISCSI'
        type = u'iscsi'
        icon = u'iSCSIIcon'
        options = []
