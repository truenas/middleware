from .custom_object_api import CustomObject


class OPENEBSBase(CustomObject):

    GROUP = NotImplementedError
    PLURAL = NotImplementedError
    VERSION = NotImplementedError

    @classmethod
    async def query(cls, **kwargs):
        return await super().query(cls.GROUP, cls.VERSION, cls.PLURAL, **kwargs)

    @classmethod
    async def create(cls, data: dict, **kwargs):
        return await super().create(cls.GROUP, cls.VERSION, cls.PLURAL, data, **kwargs)

    @classmethod
    async def delete(cls, name: str,  **kwargs):
        return await super().delete(cls.GROUP, cls.VERSION, cls.PLURAL, name, **kwargs)


class ZFSVolume(OPENEBSBase):

    GROUP = 'zfs.openebs.io'
    OBJECT_HUMAN_NAME = 'Openebs ZFS Volume'
    PLURAL = 'zfsvolumes'
    VERSION = 'v1'


class ZFSVolumeSnapshotClass(OPENEBSBase):

    GROUP = 'snapshot.storage.k8s.io'
    OBJECT_HUMAN_NAME = 'Openebs ZFS Volume Snapshotclass'
    PLURAL = 'volumesnapshotclasses'
    VERSION = 'v1'


class ZFSVolumeSnapshot(OPENEBSBase):

    GROUP = 'snapshot.storage.k8s.io'
    OBJECT_HUMAN_NAME = 'Openebs ZFS Volume Snapshot'
    PLURAL = 'volumesnapshots'
    VERSION = 'v1'


class ZFSSnapshot(OPENEBSBase):

    GROUP = 'zfs.openebs.io'
    OBJECT_HUMAN_NAME = 'Openebs ZFS Snapshot'
    PLURAL = 'zfssnapshots'
    VERSION = 'v1'
