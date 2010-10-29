import os, sys
sys.path.append('/usr/local/www')
os.environ['DJANGO_SETTINGS_MODULE'] = 'freenasUI.settings'

import django.core.handlers.wsgi

application = django.core.handlers.wsgi.WSGIHandler()
