import errno
import os
import pyglfs
import threading

from base64 import b64encode, b64decode
from contextlib import contextmanager
from copy import deepcopy
from middlewared.service import (Service, CallError, job,
                                 accepts, Dict, Str, Int, Bool, List,
                                 Ref, private)
from middlewared.schema import Path
from middlewared.validators import UUID


class GlusterFilesystemService(Service):

    """
    Current todo list:
    * add xattr support
    * lookup of volfile servers from gluster volume info
    * add wrapper for handle.fts_open() method to iterate fs path
    """
    class Config:
        namespace = 'gluster.filesystem'
        cli_namespace = 'service.gluster.filesystem'
        private = True

    handles = {}

    @private
    def init_volume_mount(self, name, options):
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

    @private
    @contextmanager
    def get_volume_handle(self, name, options):
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

    @private
    def glfs_object_handle_to_dict(self, obj):
        # Name will not be available for handles opened by UUID
        return {
            'uuid': obj.uuid,
            'file_type': obj.file_type,
            'stat': {
                'st_mode': obj.cached_stat.st_mode,
                'st_ino': obj.cached_stat.st_ino,
                'st_dev': obj.cached_stat.st_dev,
                'st_nlink': obj.cached_stat.st_nlink,
                'st_size': obj.cached_stat.st_size,
                'st_uid': obj.cached_stat.st_uid,
                'st_gid': obj.cached_stat.st_gid,
            }
        }

    @private
    def get_object_handle(self, vol, uuid):
        if uuid is None:
            hdl = vol.get_root_handle()
        else:
            hdl = vol.open_by_uuid(uuid)

        return hdl

    @accepts(Dict(
        'glfs-lookup',
        Str('volume_name', required=True),
        Str('parent_uuid', null=True, default=None, validators=[UUID()]),
        Str('path', required=True),
        Dict(
            'options',
            Bool('symlink_follow', default=False)
        ),
        Dict(
            'gluster-volume-options',
            List(
                'volfile_servers',
                null=True, default=None,
                items=[Dict(
                    Str('host', required=True),
                    Str('proto', enum=['TCP', 'RDMA'], default='TCP'),
                    Int('port', default=0),
                )],
            ),
            List(
                'translators',
                items=[Dict(
                    Str('xlator_name', required=True),
                    Str('key', required=True),
                    Str('value', required=True)
                )],
            ),
            Path('log_file'),
            Int('log_level'),
            register=True
        )
    ))
    def lookup(self, data):
        with self.get_volume_handle(data['volume_name'], data['gluster-volume-options']) as vol:
            parent = self.get_object_handle(vol, data['parent_uuid'])
            obj = parent.lookup(data['path'], **data['options'])
            return self.glfs_object_handle_to_dict(obj)

    @accepts(Dict(
        'glfs-create-file',
        Str('volume_name', required=True),
        Str('parent_uuid', null=True, default=None, validators=[UUID()]),
        Str('path', required=True),
        Dict(
            'options',
            Bool('symlink_follow', default=False),
            Int('flags', default=os.O_CREAT | os.O_RDWR),
            Int('mode', default=0o644),
        ),
        Ref('gluster-volume-options')
    ))
    def create_file(self, data):
        with self.get_volume_handle(data['volume_name'], data['gluster-volume-options']) as vol:
            parent = self.get_object_handle(vol, data['parent_uuid'])
            obj = parent.create(data['path'], **data['options'])
            return self.glfs_object_handle_to_dict(obj)

    @accepts(Dict(
        'glfs-mkdir',
        Str('volume_name', required=True),
        Str('parent_uuid', null=True, default=None, validators=[UUID()]),
        Str('path', required=True),
        Dict(
            'options',
            Bool('symlink_follow', default=False),
            Int('flags', default=os.O_DIRECTORY),
            Int('mode', default=0o755)
        ),
        Ref('gluster-volume-options')
    ))
    def mkdir(self, data):
        with self.get_volume_handle(data['volume_name'], data['gluster-volume-options']) as vol:
            parent = self.get_object_handle(vol, data['parent_uuid'])
            obj = parent.mkdir(data['path'], **data['options'])
            return self.glfs_object_handle_to_dict(obj)

    @accepts(Dict(
        'glfs-unlink',
        Str('volume_name', required=True),
        Str('parent_uuid', null=True, default=None, validators=[UUID()]),
        Str('path', required=True),
        Ref('gluster-volume-options')
    ))
    def unlink(self, data):
        with self.get_volume_handle(data['volume_name'], data['gluster-volume-options']) as vol:
            parent = self.get_object_handle(vol, data['parent_uuid'])
            parent.unlink(data['path'])

    @accepts(Dict(
        'glfs-contents',
        Str('volume_name', required=True),
        Str('uuid', required=True, validators=[UUID()]),
        Dict(
            'options',
            Str('file_output_type', enum=['STRING', 'BINARY'], default='STRING')
        ),
        Ref('gluster-volume-options')
    ))
    def contents(self, data):
        with self.get_volume_handle(data['volume_name'], data['gluster-volume-options']) as vol:
            target = self.get_object_handle(vol, data['uuid'])
            contents = target.contents()
            if target.file_type['parsed'] == 'FILE':
                if data['options']['file_output_type'] == 'STRING':
                    output = contents.decode()

                elif data['options']['file_output_type'] == 'BINARY':
                    output = b64encode(contents).decode()

            else:
                output = contents

            return output

    @accepts(Dict(
        'glfs-setattrs',
        Str('volume_name', required=True),
        Str('uuid', required=True, validators=[UUID()]),
        Dict(
            'options',
            Int('uid', default=-1),
            Int('gid', default=-1),
            Int('mode'),
            Bool('recursive', default=False)
        ),
        Ref('gluster-volume-options')
    ))
    @job()
    def setattrs(self, job, data):
        if data['options']['recursive']:
            # Trade-off for recursive jobs. These may be _very_ long-running and so
            # execute under dedicated virtual mount. This will add a few seconds for
            # temporary mount teardown, but should be acceptable for a long-running job.
            tmp_vol = self.init_volume_mount(data['volume_name'], data['gluster-volume-options'])
            target = self.get_object_handle(tmp_vol, data['uuid'])
            target.stat()
            if target.file_type['parsed'] != 'DIRECTORY':
                raise CallError('Gluster filesystem object is not a directory.', errno.ENOTDIR)

            target.setattrs(**data['options'])
            target.stat()
            return self.glfs_object_handle_to_dict(target)

        with self.get_volume_handle(data['volume_name'], data['gluster-volume-options']) as vol:
            target = self.get_object_handle(vol, data['uuid'])
            target.setattrs(**data['options'])
            target.stat()
            return self.glfs_object_handle_to_dict(target)

    @accepts(Dict(
        'glfs-pread',
        Str('volume_name', required=True),
        Str('uuid', required=True, validators=[UUID()]),
        Dict(
            'options',
            Int('offset', required=True),
            Int('cnt', required=True)
        ),
        Ref('gluster-volume-options')
    ))
    def pread(self, data):
        with self.get_volume_handle(data['volume_name'], data['gluster-volume-options']) as vol:
            fd = self.get_object_handle(vol, data['uuid']).open(os.O_RDONLY)
            bytes = fd.pread(**data['options'])
            return b64encode(bytes).decode()

    @accepts(Dict(
        'glfs-pwrite',
        Str('volume_name', required=True),
        Str('uuid', required=True, validators=[UUID()]),
        Str('payload', required=True),
        Str('payload_type', enum=['STRING', 'BINARY'], default='STRING'),
        Dict(
            'options',
            Int('offset', default=0),
        ),
        Ref('gluster-volume-options')
    ))
    def pwrite(self, data):
        with self.get_volume_handle(data['volume_name'], data['gluster-volume-options']) as vol:
            if data['payload_type'] == 'STRING':
                payload = data['payload'].encode()
            elif data['payload_type'] == 'BINARY':
                payload = b64decode(data['payload'])

            fd = self.get_object_handle(vol, data['uuid']).open(os.O_RDWR)
            fd.pwrite(buf=payload, **data['options'])
