import os

from middlewared.rclone.base import BaseRcloneRemote
from middlewared.utils.plugins import load_modules, load_classes
from middlewared.utils.python import get_middlewared_dir

REMOTES = {}


remote_classes = []
for module in load_modules(os.path.join(get_middlewared_dir(), "rclone", "remote")):
    for cls in load_classes(module, BaseRcloneRemote, []):
        remote_classes.append(cls)


async def setup(middleware):
    for cls in remote_classes:
        remote = cls(middleware)
        REMOTES[remote.name] = remote
