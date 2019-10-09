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

import argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    '--file', '-f', required=True
)
args = parser.parse_args()

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': args.file,
    }
}

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'freenasUI.freeadmin',
    'freenasUI.account',
    'freenasUI.directoryservice',
    'freenasUI.failover',
    'freenasUI.network',
    'freenasUI.services',
    'freenasUI.sharing',
    'freenasUI.storage',
    'freenasUI.support',
    'freenasUI.system',
    'freenasUI.tasks',
    'freenasUI.truenas',
    'freenasUI.vm',
]

SECRET_KEY = '.'

"""

# Django settings for FreeNAS project.
import argparse
import os
import sys

defaultdb = os.environ.get('93_DATABASE_PATH')


class DummyArgs():
    def __init__(self, file=None, secret=None):
        self.file = file
        self.secret = secret


if defaultdb:
    args = DummyArgs(file=defaultdb)
else:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--file', '-f', help='Path to 9.3 database file', required=True
    )
    parser.add_argument(
        '--secret', '-s', help='Path to 9.3 password encryption seed', required=False
    )
    args = parser.parse_args()

sys.path.append('/usr/local/lib')

HERE = os.path.abspath(os.path.dirname(__file__))

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
     ('iXsystems, Inc.', 'freenas@ixsystems.com'),
)

MANAGERS = ADMINS

DATABASE_PATH = args.file
PWENC_FILE_SECRET = args.secret or '/data/pwenc_secret'

SOUTH_DATABASE_ADAPTERS = {
    'default': 'south.db.sqlite3',
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DATABASE_PATH,
        'TEST_NAME': ':memory:',
    }
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = None

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(HERE, 'media')
MEDIA_URL = '/media/'

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = os.path.join(HERE, "static")

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

ROOT_URLCONF = 'freenasUI.urls'

SESSION_ENGINE = 'django.contrib.sessions.backends.file'

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'south',
    'freenasUI.account',
    'freenasUI.api',
    'freenasUI.jails',
    'freenasUI.plugins',
    'freenasUI.support',
    'freenasUI.directoryservice',
    'freenasUI.network',
    'freenasUI.services',
    'freenasUI.sharing',
    'freenasUI.storage',
    'freenasUI.system',
    'freenasUI.tasks',
    'freenasUI.vcp'
]

if os.path.exists('/etc/version'):
    with open('/etc/version', 'r') as f:
        version = f.read().lower()
    if 'truenas' in version:
        INSTALLED_APPS += [
            'freenasUI.truenas',
            'freenasUI.failover',
        ]

FORCE_SCRIPT_NAME = ''

ALLOWED_HOSTS = ['*']

SOUTH_TESTS_MIGRATE = False

FILE_UPLOAD_MAX_MEMORY_SIZE = 33554432
FILE_UPLOAD_TEMP_DIR = "/var/tmp/firmware/"

if 'DJANGO_LOGGING_DISABLE' in os.environ:
    LOGGING_CONFIG = None

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
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
    }
}

# Django 1.5 requires it prior to run wsgi
SECRET_KEY = "."

try:
    from local_settings import *
except:
    pass
"""