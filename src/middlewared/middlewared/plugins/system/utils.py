import enum


class VMProvider(enum.Enum):
    AZURE = 'AZURE'
    NONE = 'NONE'


class Lifecycle:
    def __init__(self):
        self.SYSTEM_BOOT_ID = None
        self.SYSTEM_FIRST_BOOT = False
        # Flag telling whether the system completed boot and is ready to use
        self.SYSTEM_READY = False
        # Flag telling whether the system is shutting down
        self.SYSTEM_SHUTTING_DOWN = False


lifecycle_conf = Lifecycle()
