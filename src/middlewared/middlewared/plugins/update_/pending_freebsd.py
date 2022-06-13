# -*- coding=utf-8 -*-
import json
import os

from freenasOS import Update
from freenasOS.Exceptions import (
    UpdateIncompleteCacheException, UpdateInvalidCacheException,
    UpdateBusyCacheException,
)

from middlewared.service import private, Service


class UpdateService(Service):
    @private
    def get_pending_in_path(self, path):
        scale_flag = os.path.join(path, 'scale')
        if os.path.exists(scale_flag):
            with open(scale_flag) as f:
                new_manifest = json.load(f)

            old_version = self.middleware.call_sync('system.version').split('-', 1)[1]
            return [
                {
                    "operation": "upgrade",
                    "old": {
                        "name": "TrueNAS",
                        "version": old_version,
                    },
                    "new": {
                        "name": "TrueNAS",
                        "version": new_manifest["version"],
                    }
                }
            ]

        data = []
        try:
            changes = Update.PendingUpdatesChanges(path)
        except (
            UpdateIncompleteCacheException, UpdateInvalidCacheException,
            UpdateBusyCacheException,
        ):
            changes = []
        if changes:
            if changes.get("Reboot", True) is False:
                for svc in changes.get("Restart", []):
                    data.append({
                        'operation': svc,
                        'name': Update.GetServiceDescription(svc),
                    })
            for new, op, old in changes['Packages']:
                if op == 'upgrade':
                    name = '%s-%s -> %s-%s' % (
                        old.Name(),
                        old.Version(),
                        new.Name(),
                        new.Version(),
                    )
                elif op == 'install':
                    name = '%s-%s' % (new.Name(), new.Version())
                else:
                    # Its unclear why "delete" would feel out new
                    # instead of old, sounds like a pkgtools bug?
                    if old:
                        name = '%s-%s' % (old.Name(), old.Version())
                    else:
                        name = '%s-%s' % (new.Name(), new.Version())

                data.append({
                    'operation': op,
                    'name': name,
                })
        return data
