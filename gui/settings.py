#+
# Copyright 2010-2012 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

# Django settings for FreeNAS project.

import os
import sys

sys.path.append('/usr/local/lib')

HERE = os.path.abspath(os.path.dirname(__file__))

DEBUG = False

MANAGERS = ADMINS = ()

DATABASE_PATH = os.environ.get('DATABASE_ROOT', '/data') + '/freenas-v1.db'

# Workaround bug in database name for migrate
if 'FREENAS_FACTORY' in os.environ:
    DATABASE_PATH += '.factory'

DATABASES = {
    'default': {
        'ENGINE': 'freenasUI.freeadmin.sqlite3_ha',
        'NAME': DATABASE_PATH,
        'TEST_NAME': ':memory:',
        'OPTIONS': {
            'timeout': 60,
        }
    },
}

"""
Make sure the database is never world readable
"""
if os.path.exists(DATABASE_PATH) and os.environ.get('FREENAS_INSTALL', '').lower() != 'yes':
    stat = os.stat(DATABASE_PATH)
    #TODO use pwd.getpwnam/grp.getgrnam?
    #0 - root
    #5 - operator
    if stat.st_uid != 0 or stat.st_gid != 5:
        os.chown(DATABASE_PATH, 0, 5)
    mode = stat.st_mode & 0xfff
    if mode != 0o640:
        os.chmod(DATABASE_PATH, 0o640)

TIME_ZONE = None

LANGUAGE_CODE = 'en-us'

SITE_ID = 1

ROOT_URLCONF = 'freenasUI.urls'

LOCALE_PATHS = (
    os.path.join(HERE, "locale"),
)

SESSION_ENGINE = 'django.contrib.sessions.backends.file'

DIR_BLACKLIST = [
    '__pycache__',
    'middleware',
    'contrib',
    'common',
    'locale',
    'tools',
    'freeadmin',
    'static',
]
APP_MODULES = []

for entry in os.listdir(HERE):
    if entry in DIR_BLACKLIST:
        continue
    if entry.startswith('.'):
        continue
    if os.path.isdir(os.path.join(HERE, entry)):
        APP_MODULES.append('freenasUI.%s' % entry)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'freenasUI.freeadmin',
) + tuple(APP_MODULES)

BLACKLIST_NAV = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'freeadmin',
)

AUTH_USER_MODEL = 'account.bsdUsers'
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

# Do not set up logging if its being imported from middlewared
if 'MIDDLEWARED' in os.environ:
    LOGGING_CONFIG = False

# the site admins on every HTTP 500 error.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '[%(name)s:%(lineno)s] %(message)s'
        },
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': [],
        },
        'syslog': {
            'level': 'DEBUG',
            'class': 'freenasUI.freeadmin.handlers.SysLogHandler',
            'formatter': 'simple',
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'ws4py': {
            'handlers': ['syslog'],
            'level': 'WARN',
            'propagate': True,
        },
        '': {
            'handlers': ['syslog'],
            'level': 'DEBUG',
            'propagate': True,
        },
    }
}

# Django 1.5 requires it prior to run wsgi
SECRET_KEY = "."

try:
    from .local_settings import *
except:
    pass
