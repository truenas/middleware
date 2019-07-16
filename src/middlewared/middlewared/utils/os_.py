try:
    import apt
except ImportError:
    apt = None

try:
    from bsd.threading import set_thread_name as bsd_set_thread_name
except ImportError:
    bsd_set_thread_name = None

try:
    from bsd import closefrom
except ImportError:
    closefrom = None

import os
import platform
import resource
import sys


class OS(object):

    @staticmethod
    def close_fds(low_fd, max_fd=None):
        if closefrom and not max_fd:
            closefrom(low_fd)
            return
        if max_fd is None:
            max_fd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
            # Avoid infinity as thats not practical
            if max_fd == resource.RLIM_INFINITY:
                max_fd = 8192
        os.closerange(low_fd, max_fd)

    @staticmethod
    def set_thread_name(name):
        if bsd_set_thread_name:
            bsd_set_thread_name(name)

    def get_app_version(self):
        raise NotImplementedError


class FreeBSD(OS):

    def get_app_version(self):
        if '/usr/local/lib' not in sys.path:
            sys.path.append('/usr/local/lib')
        # Lazy import to avoid freenasOS configure logging for us
        from freenasOS import Configuration
        conf = Configuration.Configuration()
        sys_mani = conf.SystemManifest()
        if sys_mani:
            buildtime = sys_mani.TimeStamp()
            version = sys_mani.Version()
        else:
            buildtime = version = None
        train = conf.CurrentTrain()
        stable = bool(train and 'stable' in train.lower())
        return {
            'stable': stable,
            'version': version.split('-')[1],
            'fullname': version,
            'buildtime': buildtime,
        }


class Linux(OS):

    def get_app_version(self):
        cache = apt.Cache()
        # FIXME: use virtual package
        package = cache.get('apt')
        return {
            'stable': 'git' not in package.installed.version,
            'version': package.installed.version,
            'fullname': f'TrueNAS-{package.installed.version.split("+")[0]}',
            'buildtime': None,
        }


system = platform.system().lower()
osc = None
if system == 'linux':
    osc = Linux()
elif system == 'freebsd':
    osc = FreeBSD()
