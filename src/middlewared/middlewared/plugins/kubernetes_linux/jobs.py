from middlewared.schema import Dict, Str
from middlewared.service import accepts, CRUDService, filterable
from middlewared.utils import filter_list

from .k8s_new import Job


class KubernetesJobService(CRUDService):

    class Config:
        namespace = 'k8s.job'
        private = True

    @filterable
    async def query(self, filters, options):
        return filter_list((await Job.query())['items'], filters, options)

    @accepts(
        Str('name'),
        Dict(
            'k8s_job_delete_options',
            Str('namespace', required=True),
        )
    )
    async def do_delete(self, name, options):
        await Job.delete(name, **options)
