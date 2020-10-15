import gzip
import json

from base64 import b64decode
from collections import defaultdict
from copy import deepcopy
from pkg_resources import parse_version

from middlewared.service import private, Service

from .utils import CHART_NAMESPACE_PREFIX, get_namespace


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    def releases_secrets(self, options=None):
        options = options or {}
        namespace_filter = options.get('namespace_filter') or ['metadata.namespace', '^', CHART_NAMESPACE_PREFIX]

        release_secrets = defaultdict(lambda: dict({'untagged': [], 'releases': [], 'history': {}}))
        secrets = self.middleware.call_sync(
            'k8s.secret.query', [['type', '=', 'helm.sh/release.v1'], namespace_filter]
        )
        for release_secret in secrets:
            data = release_secret.pop('data')
            release = json.loads(gzip.decompress(b64decode(b64decode(data['release']))).decode())
            name = release['name']
            if any(k not in release_secret['metadata']['labels'] for k in ('catalog', 'catalog_train')):
                release_secrets[name]['untagged'].append(release_secret)

            release.pop('manifest')
            release.update({
                'chart_metadata': release.pop('chart')['metadata'],
                'id': name,
                'catalog': release_secret['metadata']['labels'].get(
                    'catalog', self.middleware.call_sync('catalog.official_catalog_label')
                ),
                'catalog_train': release_secret['metadata']['labels'].get('catalog_train', 'test'),
            })
            if options.get('retrieve_secret_metadata'):
                release['secret_metadata'] = deepcopy(release_secret['metadata'])

            release_secrets[name]['releases'].append(release)

        for release in release_secrets:
            release_secrets[release]['releases'].sort(key=lambda d: d['version'], reverse=True)
            if not options.get('history'):
                continue

            cur_version = release_secrets[release]['releases'][0]['chart_metadata']['version']
            for rel in release_secrets[release]['releases']:
                rel_chart_version = rel['chart_metadata']['version']
                if rel_chart_version != cur_version and rel_chart_version not in release_secrets[release]['history']:
                    release_secrets[release]['history'][rel_chart_version] = deepcopy(rel)

        return release_secrets

    @private
    async def sync_secrets_for_release(self, release, catalog, catalog_train):
        secrets_data = await self.middleware.call(
            'chart.release.releases_secrets', {
                'namespace_filter': ['metadata.namespace', '=', get_namespace(release)],
                'retrieve_secret_metadata': True,
            }
        )
        await self.label_unlabelled_secrets(secrets_data[release]['untagged'], catalog, catalog_train)
        # We want to delete any secret which only contains configuration changes for the same chart version.
        # Helm right now by default tracks only past 10 changes for a chart release. This means if user changes
        # any value 10 ten times, that's the only history we have. Ideally we would like to only keep history for
        # last version to which we can rollback to or in other words only keep track of history for secrets which
        # have a different chart version.
        to_remove = []
        seen_versions = set()
        current_version = secrets_data[release]['releases'][0]['chart_metadata']['version']
        for release_data in secrets_data[release]['releases']:
            rel_version = release_data['chart_metadata']['version']
            if parse_version(rel_version) > parse_version(current_version) or rel_version in seen_versions:
                to_remove.append(release_data['secret_metadata']['name'])

            seen_versions.add(rel_version)

        for remove_secret in to_remove:
            await self.middleware.call('k8s.secret.delete', remove_secret, {'namespace': get_namespace(release)})

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
