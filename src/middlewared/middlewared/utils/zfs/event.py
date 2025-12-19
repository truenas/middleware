from dataclasses import dataclass
import typing


@dataclass(slots=True, frozen=True, kw_only=True)
class ZfsEvent:
    """Base class for all ZFS events."""
    class_: str  # The original event class/ID


@dataclass(slots=True, frozen=True, kw_only=True)
class ZfsResilverStartEvent(ZfsEvent):
    """sysevent.fs.zfs.resilver_start"""
    pool: str


@dataclass(slots=True, frozen=True, kw_only=True)
class ZfsResilverFinishEvent(ZfsEvent):
    """sysevent.fs.zfs.resilver_finish"""
    pool: str


@dataclass(slots=True, frozen=True, kw_only=True)
class ZfsScrubStartEvent(ZfsEvent):
    """sysevent.fs.zfs.scrub_start"""
    pool: str


@dataclass(slots=True, frozen=True, kw_only=True)
class ZfsScrubFinishEvent(ZfsEvent):
    """sysevent.fs.zfs.scrub_finish"""
    pool: str


@dataclass(slots=True, frozen=True, kw_only=True)
class ZfsScrubAbortEvent(ZfsEvent):
    """sysevent.fs.zfs.scrub_abort"""
    pool: str


@dataclass(slots=True, frozen=True, kw_only=True)
class ZfsStateChangeEvent(ZfsEvent):
    """resource.fs.zfs.statechange"""
    pool: str


@dataclass(slots=True, frozen=True, kw_only=True)
class ZfsChecksumErrorEvent(ZfsEvent):
    """ereport.fs.zfs.checksum"""


@dataclass(slots=True, frozen=True, kw_only=True)
class ZfsDataErrorEvent(ZfsEvent):
    """ereport.fs.zfs.data"""


@dataclass(slots=True, frozen=True, kw_only=True)
class ZfsIoErrorEvent(ZfsEvent):
    """ereport.fs.zfs.io"""


@dataclass(slots=True, frozen=True, kw_only=True)
class ZfsVdevClearEvent(ZfsEvent):
    """ereport.fs.zfs.vdev.clear"""


@dataclass(slots=True, frozen=True, kw_only=True)
class ZfsConfigSyncEvent(ZfsEvent):
    """sysevent.fs.zfs.config_sync"""
    pool: str
    guid: str | None


@dataclass(slots=True, frozen=True, kw_only=True)
class ZfsPoolImportEvent(ZfsEvent):
    """sysevent.fs.zfs.pool_import"""
    pool: str
    guid: str


@dataclass(slots=True, frozen=True, kw_only=True)
class ZfsPoolDestroyEvent(ZfsEvent):
    """sysevent.fs.zfs.pool_destroy"""
    pool: str
    guid: str


@dataclass(slots=True, frozen=True, kw_only=True)
class ZfsHistoryEvent(ZfsEvent):
    """sysevent.fs.zfs.history_event"""
    history_dsname: str
    history_internal_name: str


def parse_zfs_event(data: dict[str, typing.Any]) -> ZfsEvent | None:
    """
    Parse a ZFS event dictionary into a typed ZfsEvent object.

    Args:
        data: Dictionary containing ZFS event data with at least a 'class' key

    Returns:
        A typed ZfsEvent subclass instance, or None if the event class is not recognized
    """
    event_class = data.get('class')
    if not event_class:
        return None

    match event_class:
        case 'sysevent.fs.zfs.resilver_start':
            if pool := data.get('pool'):
                return ZfsResilverStartEvent(class_=event_class, pool=pool)

        case 'sysevent.fs.zfs.resilver_finish':
            if pool := data.get('pool'):
                return ZfsResilverFinishEvent(class_=event_class, pool=pool)

        case 'sysevent.fs.zfs.scrub_start':
            if pool := data.get('pool'):
                return ZfsScrubStartEvent(class_=event_class, pool=pool)

        case 'sysevent.fs.zfs.scrub_finish':
            if pool := data.get('pool'):
                return ZfsScrubFinishEvent(class_=event_class, pool=pool)

        case 'sysevent.fs.zfs.scrub_abort':
            if pool := data.get('pool'):
                return ZfsScrubAbortEvent(class_=event_class, pool=pool)

        case 'resource.fs.zfs.statechange':
            if pool := data.get('pool'):
                return ZfsStateChangeEvent(class_=event_class, pool=pool)

        case 'ereport.fs.zfs.checksum':
            return ZfsChecksumErrorEvent(class_=event_class)

        case 'ereport.fs.zfs.data':
            return ZfsDataErrorEvent(class_=event_class)

        case 'ereport.fs.zfs.io':
            return ZfsIoErrorEvent(class_=event_class)

        case 'ereport.fs.zfs.vdev.clear':
            return ZfsVdevClearEvent(class_=event_class)

        case 'sysevent.fs.zfs.config_sync':
            if pool := data.get('pool'):
                return ZfsConfigSyncEvent(class_=event_class, pool=pool, guid=data.get('guid'))

        case 'sysevent.fs.zfs.pool_import':
            if pool := data.get('pool'):
                return ZfsPoolImportEvent(class_=event_class, pool=pool, guid=data.get('guid'))

        case 'sysevent.fs.zfs.pool_destroy':
            if pool := data.get('pool'):
                return ZfsPoolDestroyEvent(class_=event_class, pool=pool, guid=data.get('guid'))

        case 'sysevent.fs.zfs.history_event':
            if (dsname := data.get('history_dsname')) and (internal_name := data.get('history_internal_name')):
                return ZfsHistoryEvent(
                    class_=event_class,
                    history_dsname=dsname,
                    history_internal_name=internal_name
                )

    return None
