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

HERE = os.path.abspath(os.path.dirname(__file__))

DEBUG = False
#DEBUG = True
#TASTYPIE_FULL_DEBUG = True
TEMPLATE_DEBUG = DEBUG
LOGIN_REDIRECT_URL = '/'
LOGIN_URL = '/account/login/'
LOGOUT_URL = '/account/logout/'

ADMINS = (
     ('iXsystems, Inc.', 'freenas@ixsystems.com'),
)

MANAGERS = ADMINS

DATABASE_PATH = '/data/freenas-v1.db'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DATABASE_PATH,
        'TEST_NAME': ':memory:',
    }
}

"""
Make sure the database is never world readable
"""
if os.path.exists(DATABASE_PATH):
    stat = os.stat(DATABASE_PATH)
    #TODO use pwd.getpwnam/grp.getgrnam?
    #0 - root
    #5 - operator
    if stat.st_uid != 0 or stat.st_gid != 5:
        os.chown(DATABASE_PATH, 0, 5)
    mode = stat.st_mode & 0xfff
    if mode != 0o640:
        os.chmod(DATABASE_PATH, 0o640)

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

STATICFILES_DIRS = (
    os.path.join(HERE, "fnstatic"),
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    #'freenasUI.freeadmin.middleware.ProfileMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'freenasUI.freeadmin.middleware.LocaleMiddleware',
    'freenasUI.freeadmin.middleware.CatchError',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'freenasUI.freeadmin.middleware.RequireLoginMiddleware',
)

DOJANGO_DOJO_PROFILE = 'local_release'
DOJANGO_DOJO_VERSION = '1.9.1'
#DOJANGO_DOJO_BUILD_VERSION = '1.6.0b1'
DOJANGO_DOJO_DEBUG = True

ROOT_URLCONF = 'freenasUI.urls'

TEMPLATE_DIRS = (
    os.path.join(HERE, 'templates'),
)

TEMPLATE_CONTEXT_PROCESSORS = (
        'django.core.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        "django.core.context_processors.i18n",
        "django.core.context_processors.media",
        "django.core.context_processors.static",
        'dojango.context_processors.config',
        )

LOCALE_PATHS = (
    os.path.join(HERE, "locale"),
)

SESSION_ENGINE = 'django.contrib.sessions.backends.file'

DIR_BLACKLIST = [
    'templates',
    'fnstatic',
    'middleware',
    'contrib',
    'common',
    'locale',
    'dojango',
    'tools',
    'api',
    'freeadmin',
    'static',
]
APP_MODULES = []

for entry in os.listdir(HERE):
    if entry in DIR_BLACKLIST:
        continue
    if os.path.isdir(os.path.join(HERE, entry)):
        APP_MODULES.append('freenasUI.%s' % entry)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'south',
    'dojango',
    'freenasUI.api',
    'freenasUI.freeadmin',
) + tuple(APP_MODULES)

BLACKLIST_NAV = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'south',
    'dojango',
    'freeadmin',
)

FORCE_SCRIPT_NAME = ''

#TODO: Revisit me against cache posion attacks
#      Maybe offer as an option in the GUI
ALLOWED_HOSTS = ['*']

AUTH_USER_MODEL = 'account.bsdUsers'

SOUTH_TESTS_MIGRATE = False

FILE_UPLOAD_MAX_MEMORY_SIZE = 33554432
FILE_UPLOAD_TEMP_DIR = "/var/tmp/firmware/"

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
    from local_settings import *
except:
    pass
