from dataclasses import dataclass


@dataclass(slots=True)
class Lifecycle:
    SYSTEM_BOOT_ID: str | None = None
    SYSTEM_FIRST_BOOT: bool = False
    # Flag telling whether the system completed boot and is ready to use
    SYSTEM_READY: bool = False
    # Flag telling whether the system is shutting down
    SYSTEM_SHUTTING_DOWN: bool = False
    # Flag telling whether API endpoints are readonly for user interactive sessions
    SYSTEM_READONLY: bool = True


lifecycle_conf = Lifecycle()
