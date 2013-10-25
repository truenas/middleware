from freenasUI.freeadmin.apppool import appPool
from .hook import JailsHook
appPool.register(JailsHook)
