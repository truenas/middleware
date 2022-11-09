from middlewared.schema import accepts, Dict, List, Str
from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import api_client
from .k8s_new import PersistentVolume


class KubernetesPersistentVolumesService(CRUDService):

    class Config:
        namespace = 'k8s.pv'
        private = True
        datastore_primary_key_type = 'string'

    @filterable
    async def query(self, filters, options):
        return filter_list((await PersistentVolume.query())['items'], filters, options)

    @accepts(
        Dict(
            'pv_create',
            Dict(
                'metadata',
                Str('name', required=True),
                Dict(
                    'annotations',
                    Str('pv.kubernetes.io/provisioned-by', default='zfs.csi.openebs.io'),
                ),
                additional_attrs=True,
            ),
            Dict(
                'spec',
                List('accessModes', enum=['ReadWriteOnce'], default=['ReadWriteOnce']),
                Dict(
                    'capacity',
                    Str('storage', required=True),
                ),
                Dict(
                    'claimRef',
                    Str('kind', default='PersistentVolumeClaim'),
                    Str('name', required=True),
                    Str('namespace', required=True),
                ),
                Dict(
                    'csi',
                    Str('driver', default='zfs.csi.openebs.io'),
                    Str('fsType', default='zfs'),
                    Dict(
                        'volumeAttributes',
                        Str('openebs.io/poolname', required=True),
                        additional_attrs=True
                    ),
                    Str('volumeHandle', required=True),
                ),
                Str('persistentVolumeReclaimPolicy', default='Retain', enum=['Retain', 'Recycle', 'Delete']),
                Str('storageClassName', required=True),
                Str('volumeMode', default='Filesystem'),
            ),
        )
    )
    async def do_create(self, data):
        await PersistentVolume.create(data)

    async def do_delete(self, pv_name):
        await PersistentVolume.delete(pv_name)
