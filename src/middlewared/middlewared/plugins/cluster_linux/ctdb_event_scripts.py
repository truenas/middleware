from pathlib import Path
from enum import Enum

from middlewared.service import CallError, Service, accepts
from middlewared.schema import Str
from middlewared.plugins.cluster_linux.utils import CTDBConfig


ETC_DIR = Path(CTDBConfig.CTDB_ETC_EVENT_SCRIPT_DIR.value)
USR_DIR = Path(CTDBConfig.CTDB_USR_EVENT_SCRIPT_DIR.value)


class CtdbAllowedEventScriptsEnum(Enum):
    """
    Many ctdb event scripts exist so we only want these to be exposed, for now.
    """
    INTERFACE = '10.interface.script'


class CtdbEventScriptsService(Service):

    class Config:
        namespace = 'ctdb.event.scripts'
        private = True

    async def init(self):
        # This is called after ctdb service has been started so
        # we need to make sure and try not to crash here. Instead
        # we'll catch any exceptions and log errors accordingly.
        # Furthermore, we always want to enable the ctdb public
        # event script because without it the public IP given to
        # us will not be allocated to an interface on any of the
        # nodes in the cluster
        try:
            await self.middleware.call('ctdb.event.scripts.enable', '10.interface.script')
        except Exception:
            self.logger.error('Failed to initialize ctdb event scripts', exc_info=True)

    def enabled(self):
        """Return the ctdb event scripts that have been enabled"""
        # the scripts are just symlink'ed from /etc/ctdb to /usr/share
        # which means they're "enabled"
        return [
            i.name for i in ETC_DIR.iterdir() if i.is_file() and i.resolve() == USR_DIR.joinpath(i.name)
        ]

    def disabled(self):
        """Return the ctdb event scripts that are disabled"""
        return [
            i.name for i in USR_DIR.iterdir() if i.is_file() and (
                i.name in self.middleware.call_sync('ctdb.event.scripts.enabled')
            )
        ]

    @accepts(Str('script', required=True, enum=[i.value for i in CtdbAllowedEventScriptsEnum]))
    def enable(self, script):
        if script in self.middleware.call_sync('ctdb.event.scripts.enabled'):
            return

        symlink_targ = ETC_DIR.joinpath(script)
        symlink_dest = USR_DIR.joinpath(script)
        try:
            symlink_targ.unlink(missing_ok=True)  # make sure we remove a non-symlink if it exists
            symlink_targ.symlink_to(symlink_dest)
        except Exception as e:
            raise CallError(f'Failed to enable {script}: {e}')

    @accepts(Str('script', required=True))
    def disable(self, script):
        if script in self.middleware.call_sync('ctdb.event.scripts.disabled'):
            return

        try:
            ETC_DIR.joinpath(script).unlink(missing_ok=True)
        except Exception as e:
            raise CallError(f'Failed to disable {script}: {e}')
