import os
from django.conf import settings

DEBUG = getattr(settings, "DEBUG", False)
DEFAULT_CHARSET = getattr(settings, 'DEFAULT_CHARSET', 'utf-8')

DOJO_VERSION = getattr(settings, "DOJANGO_DOJO_VERSION", "freenas-dojo-1.5.0")
DOJO_PROFILE = getattr(settings, "DOJANGO_DOJO_PROFILE", "local_release")

DOJO_MEDIA_URL = getattr(settings, "DOJANGO_DOJO_MEDIA_URL", 'dojo-media')
BASE_MEDIA_URL = getattr(settings, "DOJANGO_BASE_MEDIA_URL", '/dojango/%s' % DOJO_MEDIA_URL)
BUILD_MEDIA_URL = getattr(settings, "DOJANGO_BUILD_MEDIA_URL", '%s/release' % BASE_MEDIA_URL)
BASE_MEDIA_ROOT = getattr(settings, "DOJANGO_BASE_MEDIA_ROOT", os.path.abspath(os.path.dirname(__file__)+'/../dojo-media/'))
BASE_DOJO_ROOT = getattr(settings, "DOJANGO_BASE_DOJO_ROOT", BASE_MEDIA_ROOT + "/src")
# as default the dijit theme folder is used
DOJO_THEME_URL = getattr(settings, "DOJANGO_DOJO_THEME_URL", False)
DOJO_THEME = getattr(settings, "DOJANGO_DOJO_THEME", "claro")
DOJO_DEBUG = getattr(settings, "DOJANGO_DOJO_DEBUG", DEBUG) # using the default django DEBUG setting
DOJO_SECURE_JSON = getattr(settings, "DOJANGO_DOJO_SECURE_JSON", True) # if you are using dojo version < 1.2.0 you have set it to False
CDN_USE_SSL = getattr(settings, "DOJANGO_CDN_USE_SSL", False) # is dojo served via https from google? doesn't work for aol!

# set the urls for actual possible paths for dojo
# one dojo profile must at least contain a path that defines the base url of a dojo installation
# the following settings can be set for each dojo profile:
# - base_url: where do the dojo files reside (without the version folder!)
# - use_xd: use the crossdomain-build? used to build the correct filename (e.g. dojo.xd.js)
# - versions: this list defines all possible versions that are available in the defined profile
# - uncompressed: use the uncompressed version of dojo (dojo.xd.js.uncompressed.js)
# - use_gfx: there is a special case, when using dojox.gfx from aol (see http://dev.aol.com/dojo)
# - is_local: marks a profile being local. this is needed when using the dojo module loader
# - is_local_build: profile being a locally builded version
_aol_versions = ('0.9.0', '1.0.0', '1.0.2', '1.1.0', '1.1.1', '1.2.0', '1.2.3', '1.3', '1.3.0', '1.3.1', '1.3.2', '1.4', '1.4.0', '1.4.1', '1.4.3',)
_aol_gfx_versions = ('0.9.0', '1.0.0', '1.0.2', '1.1.0', '1.1.1',)
_google_versions = ('1.1.1', '1.2', '1.2.0', '1.2.3', '1.3', '1.3.0', '1.3.1', '1.3.2', '1.4', '1.4.0', '1.4.1', '1.4.3',)
DOJO_PROFILES = {
    'local': {'base_url': '%(BASE_MEDIA_URL)s', 'is_local':True}, # we don't have a restriction on version names, name them as you like
    'local_release': {'base_url': '%(BUILD_MEDIA_URL)s', 'is_local':True, 'is_local_build':True}, # this will be available after the first dojo build!
    #'local_release_uncompressed': {'base_url': '%(BUILD_MEDIA_URL)s', 'uncompressed':True, 'is_local':True, 'is_local_build':True} # same here
}

# we just want users to append/overwrite own profiles
DOJO_PROFILES.update(getattr(settings, "DOJANGO_DOJO_PROFILES", {}))

# =============================================================================================
# =================================== NEEDED FOR DOJO BUILD ===================================
# =============================================================================================
# general doc: http://dojotoolkit.org/book/dojo-book-0-9/part-4-meta-dojo/package-system-and-custom-builds
# see http://www.sitepen.com/blog/2008/04/02/dojo-mini-optimization-tricks-with-the-dojo-toolkit/ for details
DOJO_BUILD_VERSION = getattr(settings, "DOJANGO_DOJO_BUILD_VERSION", '1.5.0')
# this is the default build profile, that is used, when calling "./manage.py dojobuild"
# "./manage.py dojobuild dojango" would have the same effect
DOJO_BUILD_PROFILE = getattr(settings, "DOJANGO_DOJO_BUILD_PROFILE", "dojango")
# This dictionary defines your build profiles you can use within the custom command "./manage.py dojobuild
# You can set your own build profile within the main settings.py of the project by defining a dictionary
# DOJANGO_DOJO_BUILD_PROFILES, that sets the following key/value pairs for each defined profile name:
#   profile_file: which dojo profile file is used for the build (see dojango.profile.js how it has to look)
#   options: these are the options that are passed to the build command (see the dojo doc for details)
#   OPTIONAL SETTINGS (see DOJO_BUILD_PROFILES_DEFAULT):
#   base_root: in which directory will the dojo version be builded to? 
#   used_src_version: which version should be used for the dojo build (e.g. 1.1.1)
#   build_version: what is the version name of the builded release (e.g. dojango1.1.1) - this option can be overwritten by the commandline parameter --build_version=...
#   minify_extreme_skip_files: a tupel of files/folders (each expressed as regular expression) that should be kept when doing a minify extreme (useful when you have several layers and don't want some files)
#                              this tupel will be appended to the default folders/files that are skipped: see SKIP_FILES in management/commands/dojobuild.py 
DOJO_BUILD_PROFILES = {
    'dojango': {
        'options': 'profileFile="%(BASE_MEDIA_ROOT)s/dojango.profile.js" action=release optimize=shrinksafe.keepLines cssOptimize=comments.keepLines',
    },
    'dojango_optimized': {
        'options': 'profileFile="%(BASE_MEDIA_ROOT)s/dojango_optimized.profile.js" action=release optimize=shrinksafe.keepLines cssOptimize=comments.keepLines',
        'build_version': '%(DOJO_BUILD_VERSION)s-dojango-optimized-with-dojo',
    },
}

# these defaults are mixed into each DOJO_BUILD_PROFILES element
# but you can overwrite each attribute within your own build profile element
# e.g. DOJANGO_BUILD_PROFILES = {'used_src_version': '1.2.2', ....}
DOJO_BUILD_PROFILES_DEFAULT = getattr(settings, "DOJANGO_DOJO_BUILD_PROFILES_DEFAULT", {
    # build the release in the media directory of dojango
    # use a formatting string, so this can be set in the project's settings.py without getting the dojango settings
    'base_root': '%(BASE_MEDIA_ROOT)s/release',
    'used_src_version': '%(DOJO_BUILD_VERSION)s',
    'build_version': '%(DOJO_BUILD_VERSION)s-dojango-with-dojo',
})
# TODO: we should also enable the already pre-delivered dojo default profiles

# you can add/overwrite your own build profiles
DOJO_BUILD_PROFILES.update(getattr(settings, "DOJANGO_DOJO_BUILD_PROFILES", {}))
DOJO_BUILD_JAVA_EXEC = getattr(settings, 'DOJANGO_DOJO_BUILD_JAVA_EXEC', 'java')
# a version string that must have the following form: '1.0.0', '1.2.1', ....
# this setting is used witin the dojobuild, because the build process changed since version 1.2.0
DOJO_BUILD_USED_VERSION = getattr(settings, 'DOJANGO_DOJO_BUILD_USED_VERSION', DOJO_BUILD_VERSION)
