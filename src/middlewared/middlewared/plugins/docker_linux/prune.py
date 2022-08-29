from middlewared.schema import accepts, Bool, Dict, returns
from middlewared.service import job, Service

from .utils import get_docker_client


class ContainerService(Service):

    class Config:
        cli_namespace = 'app.container.config'

    @accepts(Dict(
        'prune_options',
        Bool('remove_unused_images', default=False),
        Bool('remove_stopped_containers', default=False),
    ))
    @returns(Dict(
        'pruned_resources',
        Dict('containers', additional_attrs=True),
        Dict('images', additional_attrs=True),
        example={
            'containers': {
                'ContainersDeleted': [
                  'ba6a2e3bccd8f0226272ff8b0672721269ed695f5cf6037b749b51552445f006',
                  '2a13667cd847caedfea874c5ad50955a12acd945a9831b1809a21722c7da2580',
                  'fdb68742ca7ef4a8b60971231ed2407cc13322884acc0baf5f3c0ddc64c67b7b',
                  '22647bb88ce29e46273b2f1d29ffceecadf3e987c5b887b9c68cce6f7dbbb08f',
                  'f3cbabc98ac3828c587d33646a6e6ee91e0a15b357b89a7ecb81382cc528dc79',
                  'ba7d45fc635af25988b2803b246487d4114062220f96780c3e9b1eb1f0111d30',
                  '240cbdf098ea64052a85b95b5c987fd63fc3f6a33c795ec6fb6b80eff6f63de6',
                  'f148b6d91777b47a932cbc4e2f39bcfc8560253a841d5ebda26c5d40f835d3dd',
                  'bc0aa6981c9bf00b817eff7389c68d81db9623db71c76a13bc9cfbcecdd31f62',
                  '47c4d4c38e28d050c557034f10c7d8f8f31043a0552921bc2d1ef1a036d8eacb',
                  'd6595c638986bfadb2a578a1cc7357f2867f4b3317f7e5af2b653c217fba0bf0',
                  '6b66856209511cb7823e00bc86adf2d397cc8a8cbc2a203faac17ddc3d8ec27f',
                  '8fb78236d379967db9d2649ff8a10c9f84074e7344b21107da38c5707f1591a5'
                ],
                'SpaceReclaimed': 0
            },
            'images': {
                'ImagesDeleted': [
                  {
                    'Untagged': 'quay.io/skopeo/stable:latest'
                  },
                  {
                    'Deleted': 'sha256:883e787c00d4208d75fc3e85d100ce64b517e49a2468f0e7f084cf05d16f3e46'
                  },
                  {
                    'Untagged': 'busybox:latest'
                  },
                  {
                    'Untagged': 'busybox@sha256:caa382c432891547782ce7140fb3b7304613d3b0438834dce1cad68896ab110a'
                  },
                  {
                    'Deleted': 'sha256:2fb6fc2d97e10c79983aa10e013824cc7fc8bae50630e32159821197dda95fe3'
                  },
                  {
                    'Deleted': 'sha256:797ac4999b67d8c38a596919efa5b7b6a4a8fd5814cb8564efa482c5d8403e6d'
                  }
                ],
                'SpaceReclaimed': 260858493
            }
        }
    ))
    @job(lock='container_prune')
    def prune(self, job, options):
        """
        Prune unused images/containers. This will by default remove any dangling images.

        `prune_options.remove_unused_images` when set will remove any docker image which is not being used by any
        container.

        `prune_options.remove_stopped_containers` when set will remove any containers which are stopped.
        """
        pruned_objects = {'containers': {}, 'images': {}}
        client = get_docker_client()
        if options['remove_stopped_containers']:
            pruned_objects['containers'] = client.containers.prune()
            job.set_progress(50, 'Stopped containers pruned')

        # Reasoning for the parameters to image prune
        # https://github.com/docker/docker-py/issues/1939#issuecomment-392112015
        pruned_objects['images'] = client.images.prune({'dangling': not options['remove_unused_images']})
        job.set_progress(100, 'Successfully pruned images/containers')
        return pruned_objects
