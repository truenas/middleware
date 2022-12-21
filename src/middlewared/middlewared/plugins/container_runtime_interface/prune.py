from middlewared.schema import accepts, Bool, Dict, returns
from middlewared.service import job, Service

from .client import ContainerdClient


class ContainerService(Service):

    class Config:
        cli_namespace = 'app.container.config'

    @accepts(Dict(
        'prune_options',
        Bool('remove_unused_images', default=False),
    ))
    @returns(Dict(
        'pruned_resources',
        Dict('images', additional_attrs=True),
        example={
            'images': {
                'ImagesDeleted': [
                    {
                        'id': 'sha256:883e787c00d4208d75fc3e85d100ce64b517e49a2468f0e7f084cf05d16f3e46',
                        'Untagged': 'quay.io/skopeo/stable:latest',
                    },
                    {
                        'id': 'sha256:883e787c00d4208d75fc3e85d100ce64b517e49a2468f0e7f084cf05d16f3e46',
                        'Untagged': 'quay.io/skopeo/stable:latest2',
                    },
                ],
                'SpaceReclaimed': 260858493
            }
        }
    ))
    @job(lock='container_prune')
    def prune(self, job, options):
        """
        Prune unused images/containers. This will by default remove any dangling images.

        `prune_options.remove_unused_images` when set will remove any container image which is not being used by any
        container.
        """
        pruned_objects = {'images': {'ImagesDeleted': [], 'SpaceReclaimed': 0}}
        with ContainerdClient('container') as client:
            containers_image_refs = list(map(lambda container: container['imageRef'], client.list_containers()))

        with ContainerdClient('image') as client:
            for image in (
                map(
                    lambda i: {**i, 'repo_tags': i.get('repoTags') or []},
                    client.list_images()
                ) if options.get('remove_unused_images') else self.middleware.call_sync(
                    'container.image.query', [['dangling', '=', True]]
                )
            ):
                if image['id'] not in containers_image_refs:
                    client.remove_image(image['id'])
                    pruned_objects['images']['ImagesDeleted'].append({
                        'id': image['id'],
                        'repo_tags': image['repo_tags'],
                    })
                    pruned_objects['images']['SpaceReclaimed'] += int(image['size'])

        job.set_progress(100, 'Successfully pruned images/containers')
        return pruned_objects
