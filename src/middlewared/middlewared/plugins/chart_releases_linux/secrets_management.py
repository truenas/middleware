import gzip
import json

from base64 import b64decode
from collections import defaultdict

from middlewared.service import private, Service

from .utils import CHART_NAMESPACE


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def releases_secrets(self):
        release_secrets = defaultdict(lambda: dict({'untagged': [], 'secrets': [], 'releases': []}))
        secrets = await self.middleware.call(
            'k8s.secret.query', [['type', '=', 'helm.sh/release.v1'], ['metadata.namespace', '=', CHART_NAMESPACE]]
        )
        for release_secret in secrets:
            data = release_secret.pop('data')
            release = await self.middleware.run_in_thread(lambda: json.loads(
                gzip.decompress(b64decode(b64decode(data['release']))).decode()
            ))
            name = release['name']
            if any(k not in release_secret['metadata']['labels'] for k in ('catalog', 'catalog_train')):
                release_secrets[name]['untagged'].append(release_secret)

            release.pop('manifest')
            release.update({
                'chart_metadata': release.pop('chart')['metadata'],
                'id': name,
            })

            release_secrets[name]['secrets'].append(release_secret)
            release_secrets[name]['releases'].append(release)

        for release in release_secrets:
            release_secrets[release]['releases'].sort(key=lambda d: d['version'], reverse=True)
            release_secrets[release]['secrets'].sort(
                key=lambda d: int(d['metadata']['labels']['version']), reverse=True
            )

        return release_secrets

    @private
    async def update_unlabelled_secrets_for_release(self, release, catalog, catalog_train):
        await self.label_unlabelled_secrets(
            (await self.middleware.call('chart.release.releases_secrets'))[release]['untagged'],
            catalog, catalog_train,
        )

    @private
    async def label_unlabelled_secrets(self, secrets, catalog, catalog_train):
        for secret in secrets:
            name = secret['metadata']['name']
            namespace = secret['metadata']['namespace']
            labels = secret['metadata']['labels']
            labels.update({
                'catalog': catalog,
                'catalog_train': catalog_train,
            })
            await self.middleware.call(
                'k8s.secret.update', name, {'namespace': namespace, 'body': {'metadata': {'labels': labels}}}
            )
