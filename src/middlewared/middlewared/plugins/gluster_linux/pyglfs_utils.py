import errno
import fcntl
import functools
import pyglfs
import threading

from contextlib import contextmanager
from copy import deepcopy
from middlewared.service_exception import CallError

DEFAULT_GLFS_OPTIONS = {"volfile_servers": None, "translators": []}


class GlfsHdl:
    handles = {}

    def init_volume_mount(self, name, options):
        """
        Initialize a pyglfs gluster volume virtual mount.
        Resources will be automatically deallocated / unmounted
        when returned object is deallocated.
        """
        if not options['volfile_servers']:
            volfile_servers = [{'host': '127.0.0.1', 'proto': 'tcp', 'port': 0}]
        else:
            volfile_servers = options['volfile_servers']

        xlators = []

        # Normalization of values
        for s in volfile_servers:
            s['proto'] = s['proto'].lower()

        for entry in options.get('translators', []):
            xlators.append((entry['xlator_name'], entry['key'], entry['value']))

        kwargs = {
            'volume_name': name,
            'volfile_servers': volfile_servers
        }

        if options.get('translators'):
            kwargs['translators'] = xlators

        return pyglfs.Volume(**kwargs)

    @contextmanager
    def get_volume_handle(self, name, options=DEFAULT_GLFS_OPTIONS):
        """
        Get / store glusterfs volume handle virtual mount.
        We want to keep these around because unmount can be rather
        slow to complete (taking up to 10 seconds in some poorly-resourced VMs).

        If a task is expected to be extremely long-running i.e. a `job` then,
        it's a better idea to `init_volume_mount()` for a temporary virtual mount
        and use that (since we're already commited in that case for a non-immediate response).
        """
        entry = self.handles.setdefault(name, {
            'name': name,
            'lock': threading.RLock(),
            'handle_internal': None,
            'options': deepcopy(options)
        })

        if options != entry['options']:
            raise CallError(f'{name}: Internal Error - volume options mismatch', errno.EINVAL)

        with entry['lock']:
            if entry['handle_internal'] is None:
                entry['handle_internal'] = self.init_volume_mount(name, options)

            yield entry['handle_internal']


glfs = GlfsHdl()


@contextmanager
def lock_file_open(object_hdl, open_flags, lock_flags=fcntl.F_WRLCK, blocking=True, mode=None, owners=None):
    fd = object_hdl.open(open_flags)
    try:
        fd.posix_lock(fcntl.F_SETLKW if blocking else fcntl.F_SETLK, fcntl.F_WRLCK)
        if mode is not None:
            fd.fchmod(mode)

        if owners is not None:
            fd.fchown(*owners)

        yield fd

    finally:
        fd.posix_lock(fcntl.F_SETLK, fcntl.F_UNLCK)


def glusterfs_volume(fn):
    @functools.wraps(fn)
    def get_volume_handle(*args, **kwargs):
        with glfs.get_volume_handle(
            args[1]['volume_name'],
            args[1].get('gluster-volume-options', DEFAULT_GLFS_OPTIONS)
        ) as vol:
            args = list(args)
            args.insert(1, vol)
            return fn(*args, **kwargs)

    return get_volume_handle
