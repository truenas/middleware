import logging
import os
import platform
from freenasUI.jails.models import JailsConfiguration

log = logging.getLogger('jails.utils')

JAILS_INDEX = "http://download.freenas.org"


#
# get_jails_index()
#
# Get the proper CDN path for jail tarballs
#
def get_jails_index(release=None, arch=None):
    global JAILS_INDEX

    if arch is None:
        arch = platform.architecture()
        if arch[0] == '64bit':
            arch = 'x64'
        else:
            arch = 'x86'

    if release is None:
        release = "latest"

    index = "%s/%s/RELEASE/%s/jails" % (
        JAILS_INDEX, release, arch
    )

    return index


def jail_path_configured():
    """
    Check if there is the jail system is configured
    by looking at the JailsConfiguration model and
    jc_path field

    :Returns: boolean
    """
    try:
        jc = JailsConfiguration.objects.latest('id')
    except JailsConfiguration.DoesNotExist:
        jc = None

    return jc and jc.jc_path and os.path.exists(jc.jc_path)
