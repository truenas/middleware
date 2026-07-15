from __future__ import annotations

import os
import typing

from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote
from middlewared.utils.plugins import load_classes, load_modules
from middlewared.utils.python import get_middlewared_dir

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware

REMOTES = {}


remote_classes = []
for module in load_modules(os.path.join(get_middlewared_dir(), "plugins", "cloud", "rclone", "remote")):
    for cls in load_classes(module, BaseRcloneRemote, []):
        remote_classes.append(cls)


def setup(middleware: Middleware) -> None:
    for cls in remote_classes:
        remote = cls(middleware)
        REMOTES[remote.name] = remote
