import os, sys
sys.path.insert(0, '/usr/local/www')
sys.path.insert(0, '/usr/local/www/freenasUI')
os.environ['DJANGO_SETTINGS_MODULE'] = 'freenasUI.settings'

import django.core.handlers.wsgi

application = django.core.handlers.wsgi.WSGIHandler()
