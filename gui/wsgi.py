"""
WSGI config for haha project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/howto/deployment/wsgi/
"""

import os
import sys

sys.path.insert(0, '/usr/local/www')

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "freenasUI.settings")

application = get_wsgi_application()
try:
    # Fake a request so most modules are imported at this time
    # instead of the first user request.
    application({'REQUEST_METHOD': 'HEAD', 'wsgi.input': 'DUMMY', 'SERVER_NAME': 'localhost', 'SERVER_PORT': 80}, lambda x, y: None)
except Exception:
    pass
