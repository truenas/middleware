import copy
import itertools
import json
import markdown
import os
import yaml

from catalog_validation.utils import VALID_TRAIN_REGEX
from pkg_resources import parse_version

from middlewared.schema import Bool, Dict, List, returns, Str
from middlewared.service import accepts, job, private, Service, ValidationErrors

from .utils import get_cache_key


ITEM_KEYS = ['icon_url']


class CatalogService(Service):

    class Config:
        cli_namespace = 'app.catalog'

    @private
    def cached(self, label, retrieve_versions):
        return self.middleware.call_sync('cache.has_key', get_cache_key(label, retrieve_versions))

    @accepts(
        Str('label'),
        Dict(
            'options',
            Bool('cache', default=True),
            Bool('cache_only', default=False),
            Bool('retrieve_all_trains', default=True),
            Bool('retrieve_versions', default=False),
            List('trains', items=[Str('train_name')]),
        )
    )
    @returns(Dict(
        'trains',
        additional_attrs=True,
        example={
            'charts': {
                'chia': {
                    'name': 'chia',
                    'categories': ['storage', 'crypto'],
                    'app_readme': 'app readme here',
                    'location': '/mnt/evo/ix-applications/catalogs/github_com_truenas_charts_git_master/charts/chia',
                    'healthy': True,
                    'healthy_error': False,
                    'latest_version': '1.2.0',
                    'latest_app_version': '1.1.6',
                    'icon_url': 'https://www.chia.net/img/chia_logo.svg',
                }
            }
        }
    ))
    @job(lock=lambda args: f'{args[0]}_catalog_item_retrieval_{json.dumps(args[1])}')
    def items(self, job, label, options):
        """
        Retrieve item details for `label` catalog.

        `options.cache` is a boolean which when set will try to get items details for `label` catalog from cache
        if available.

        `options.cache_only` is a boolean which when set will force usage of cache only for retrieving catalog
        information. If the content for the catalog in question is not cached, no content would be returned. If
        `options.cache` is unset, this attribute has no effect.

        `options.retrieve_all_trains` is a boolean value which when set will retrieve information for all the trains
        present in the catalog ( it is set by default ).

        `options.trains` is a list of train name(s) which will allow selective filtering to retrieve only information
        of desired trains in a catalog. If `options.retrieve_all_trains` is set, it has precedence over `options.train`.

        `options.retrieve_versions` can be unset to skip retrieving version details of each catalog item. This
        can help in cases to optimize performance. Retrieving versions would be deprecated in the next major
        release from this endpoint.
        """
        catalog = self.middleware.call_sync('catalog.get_instance', label)
        all_trains = options['retrieve_all_trains']
        cache_available = False
        cache_key = get_cache_key(label, options['retrieve_versions'])
        if options['cache']:
            cache_available = self.middleware.call_sync('cache.has_key', cache_key)
            if not cache_available and not options['retrieve_versions']:
                cache_key = get_cache_key(label, True)
                cache_available = self.middleware.call_sync('cache.has_key', cache_key)
            if not cache_available and options['cache_only']:
                return {}

        if options['cache'] and cache_available:
            job.set_progress(10, 'Retrieving cached content')
            orig_data = self.middleware.call_sync('cache.get', cache_key)
            job.set_progress(60, 'Normalizing cached content')
            questions_context = None if not options['retrieve_versions'] else self.middleware.call_sync(
                'catalog.get_normalised_questions_context'
            )
            cached_data = {}
            for train in orig_data:
                if not all_trains and train not in options['trains']:
                    continue

                train_data = {}
                for catalog_item in orig_data[train]:
                    train_data[catalog_item] = {
                        k: v for k, v in orig_data[train][catalog_item].items()
                        if k != 'versions' or options['retrieve_versions']
                    }
                    if not options['retrieve_versions']:
                        continue

                    for version in train_data[catalog_item]['versions']:
                        version_data = train_data[catalog_item]['versions'][version]
                        if not version_data.get('healthy'):
                            continue
                        self.normalise_questions(version_data, questions_context)

                cached_data[train] = train_data

            job.set_progress(100, 'Retrieved catalog item(s) details successfully')
            return cached_data
        elif not os.path.exists(catalog['location']):
            job.set_progress(5, f'Cloning {label!r} catalog repository')
            self.middleware.call_sync('catalog.update_git_repository', catalog, True)

        if all_trains:
            # We can only safely say that the catalog is healthy if we retrieve data for all trains
            self.middleware.call_sync('alert.oneshot_delete', 'CatalogNotHealthy', label)

        trains = self.get_trains(job, catalog, options)

        if all_trains:
            # We will only update cache if we are retrieving data of all trains for a catalog
            # which happens when we sync catalog(s) periodically or manually
            # We cache for 90000 seconds giving system an extra 1 hour to refresh it's cache which
            # happens after 24h - which means that for a small amount of time it's possible that user
            # come with a case where system is trying to access cached data but it has expired and it's
            # reading again from disk hence the extra 1 hour.
            if options['retrieve_versions']:
                self.middleware.call_sync('cache.put', get_cache_key(label, True), trains, 90000)
                trains_copy = {}
                for train in trains:
                    trains_copy[train] = {}
                    for item in trains[train]:
                        item_data = copy.deepcopy(trains[train][item])
                        item_data.pop('versions')
                        trains_copy[train][item] = item_data
            else:
                trains_copy = trains
            self.middleware.call_sync('cache.put', get_cache_key(label, False), trains_copy, 90000)

        if label == self.middleware.call_sync('catalog.official_catalog_label'):
            # Update feature map cache whenever official catalog is updated
            self.middleware.call_sync('catalog.get_feature_map', False)

        job.set_progress(100, f'Successfully retrieved {label!r} catalog information')
        return trains

    @private
    def retrieve_train_names(self, location, all_trains=True, trains_filter=None):
        train_names = []
        trains_filter = trains_filter or []
        for train in os.listdir(location):
            if (
                not (all_trains or train in trains_filter) or not os.path.isdir(
                    os.path.join(location, train)
                ) or train.startswith('.') or train in ('library', 'docs') or not VALID_TRAIN_REGEX.match(train)
            ):
                continue
            train_names.append(train)
        return train_names

    @private
    def get_trains(self, job, catalog, options):
        # We make sure we do not dive into library and docs folders and not consider those a train
        # This allows us to use these folders for placing helm library charts and docs respectively
        trains = {'charts': {}, 'test': {}}
        location = catalog['location']
        questions_context = self.middleware.call_sync('catalog.get_normalised_questions_context')
        unhealthy_apps = set()
        preferred_trains = catalog['preferred_trains']

        trains_to_traverse = self.retrieve_train_names(location, options['retrieve_all_trains'], options['trains'])
        # In order to calculate job progress, we need to know number of items we would be traversing
        items = {}
        for train in trains_to_traverse:
            trains[train] = {}
            items.update({
                f'{i}_{train}': train for i in os.listdir(os.path.join(location, train))
                if os.path.isdir(os.path.join(location, train, i))
            })

        job.set_progress(8, f'Retrieving {", ".join(trains_to_traverse)!r} train(s) information')

        total_items = len(items)
        for index, item_key in enumerate(items):
            train = items[item_key]
            item = item_key.removesuffix(f'_{train}')
            item_location = os.path.join(location, train, item)
            job.set_progress(
                int((index / total_items) * 80) + 10,
                f'Retrieving information of {item!r} item from {train!r} train'
            )

            trains[train][item] = self.retrieve_item_details(item_location, {
                'questions_context': questions_context,
                'retrieve_versions': options['retrieve_versions'],
            })
            if train in preferred_trains and not trains[train][item]['healthy']:
                unhealthy_apps.add(f'{item} ({train} train)')

        if unhealthy_apps:
            self.middleware.call_sync(
                'alert.oneshot_create', 'CatalogNotHealthy', {
                    'catalog': catalog['id'], 'apps': ', '.join(unhealthy_apps)
                }
            )

        job.set_progress(90, f'Retrieved {", ".join(trains_to_traverse)} train(s) information')
        return trains

    @private
    def retrieve_item_details(self, item_location, options=None):
        item = item_location.rsplit('/', 1)[-1]
        train = item_location.rsplit('/', 2)[-2]
        options = options or {}
        questions_context = options.get('questions_context') or self.middleware.call_sync(
            'catalog.get_normalised_questions_context'
        )
        retrieve_versions = options.get('retrieve_versions', True)
        item_data = {
            'name': item,
            'categories': [],
            'app_readme': None,
            'location': item_location,
            'healthy': False,  # healthy means that each version the item hosts is valid and healthy
            'healthy_error': None,  # An error string explaining why the item is not healthy
            'versions': {},
            'latest_version': None,
            'latest_app_version': None,
            'latest_human_version': None,
        }

        schema = f'{train}.{item}'
        try:
            self.middleware.call_sync('catalog.validate_catalog_item', item_location, schema, False)
        except ValidationErrors as verrors:
            item_data['healthy_error'] = f'Following error(s) were found with {item!r}:\n'
            for verror in verrors:
                item_data['healthy_error'] += f'{verror[0]}: {verror[1]}'

            # If the item format is not valid - there is no point descending any further into versions
            if not retrieve_versions:
                item_data.pop('versions')
            return item_data

        item_data.update(self.item_details(item_location, schema, {
            'retrieve_latest_version': not retrieve_versions,
            'questions_context': questions_context,
        }))
        unhealthy_versions = []
        for k, v in sorted(item_data['versions'].items(), key=lambda v: parse_version(v[0]), reverse=True):
            if not v['healthy']:
                unhealthy_versions.append(k)
            else:
                if not item_data['app_readme']:
                    item_data['app_readme'] = v['app_readme']
                if not item_data['latest_version']:
                    item_data['latest_version'] = k
                    item_data['latest_app_version'] = v['chart_metadata'].get('appVersion')
                    item_data['latest_human_version'] = ''
                    if item_data['latest_app_version']:
                        item_data['latest_human_version'] = f'{item_data["latest_app_version"]}_'
                    item_data['latest_human_version'] += k

        if unhealthy_versions:
            item_data['healthy_error'] = f'Errors were found with {", ".join(unhealthy_versions)} version(s)'
        else:
            item_data['healthy'] = True
        if not retrieve_versions:
            item_data.pop('versions')

        return item_data

    @private
    def item_details(self, item_path, schema, options):
        # Each directory under item path represents a version of the item and we need to retrieve details
        # for each version available under the item
        questions_context = options['questions_context']
        retrieve_latest_version = options.get('retrieve_latest_version')
        item_data = {'versions': {}}
        with open(os.path.join(item_path, 'item.yaml'), 'r') as f:
            item_data.update(yaml.safe_load(f.read()))

        item_data.update({k: item_data.get(k) for k in ITEM_KEYS})

        for version in sorted(
            filter(lambda p: os.path.isdir(os.path.join(item_path, p)), os.listdir(item_path)),
            reverse=True, key=parse_version,
        ):
            item_data['versions'][version] = version_details = {
                'healthy': False,
                'supported': False,
                'healthy_error': None,
                'location': os.path.join(item_path, version),
                'required_features': [],
                'human_version': version,
                'version': version,
            }
            try:
                self.middleware.call_sync(
                    'catalog.validate_catalog_item_version', version_details['location'], f'{schema}.{version}'
                )
            except ValidationErrors as verrors:
                version_details['healthy_error'] = f'Following error(s) were found with {schema}.{version!r}:\n'
                for verror in verrors:
                    version_details['healthy_error'] += f'{verror[0]}: {verror[1]}'

                # There is no point in trying to see what questions etc the version has as it's invalid
                continue

            version_details.update({
                'healthy': True,
                **self.item_version_details(version_details['location'], questions_context)
            })
            if retrieve_latest_version:
                break

        return item_data

    @private
    def item_version_details(self, version_path, questions_context=None):
        if not questions_context:
            questions_context = self.middleware.call_sync('catalog.get_normalised_questions_context')
        version_data = {'location': version_path, 'required_features': set()}
        for key, filename, parser in (
            ('chart_metadata', 'Chart.yaml', yaml.safe_load),
            ('schema', 'questions.yaml', yaml.safe_load),
            ('app_readme', 'app-readme.md', markdown.markdown),
            ('detailed_readme', 'README.md', markdown.markdown),
            ('changelog', 'CHANGELOG.md', markdown.markdown),
        ):
            if os.path.exists(os.path.join(version_path, filename)):
                with open(os.path.join(version_path, filename), 'r') as f:
                    version_data[key] = parser(f.read())
            else:
                version_data[key] = None

        # We will normalise questions now so that if they have any references, we render them accordingly
        # like a field referring to available interfaces on the system
        self.normalise_questions(version_data, questions_context)

        version_data['supported'] = self.middleware.call_sync('catalog.version_supported', version_data)
        version_data['required_features'] = list(version_data['required_features'])
        version_data['values'] = self.middleware.call_sync(
            'chart.release.construct_schema_for_item_version', version_data, {}, False
        )['new_values']
        chart_metadata = version_data['chart_metadata']
        if chart_metadata['name'] != 'ix-chart' and chart_metadata.get('appVersion'):
            version_data['human_version'] = f'{chart_metadata["appVersion"]}_{chart_metadata["version"]}'

        return version_data

    @private
    async def get_normalised_questions_context(self):
        k8s_started = await self.middleware.call('service.started', 'kubernetes')
        return {
            'nic_choices': await self.middleware.call('chart.release.nic_choices'),
            'gpus': await self.middleware.call('k8s.gpu.available_gpus') if k8s_started else {},
            'timezones': await self.middleware.call('system.general.timezone_choices'),
            'node_ip': await self.middleware.call('kubernetes.node_ip'),
            'certificates': await self.middleware.call('chart.release.certificate_choices'),
            'certificate_authorities': await self.middleware.call('chart.release.certificate_authority_choices'),
            'system.general.config': await self.middleware.call('system.general.config'),
        }

    @private
    def normalise_questions(self, version_data, context):
        version_data['required_features'] = set()
        for question in version_data['schema']['questions']:
            self._normalise_question(question, version_data, context)
        version_data['required_features'] = list(version_data['required_features'])

    def _normalise_question(self, question, version_data, context):
        schema = question['schema']
        for attr in itertools.chain(*[schema.get(k, []) for k in ('attrs', 'items', 'subquestions')]):
            self._normalise_question(attr, version_data, context)

        if '$ref' not in schema:
            return

        data = {}
        for ref in schema['$ref']:
            version_data['required_features'].add(ref)
            if ref == 'definitions/interface':
                data['enum'] = [
                    {'value': i, 'description': f'{i!r} Interface'} for i in context['nic_choices']
                ]
            elif ref == 'definitions/gpuConfiguration':
                data['attrs'] = []
                for gpu, quantity in context['gpus'].items():
                    data['attrs'].append({
                        'variable': gpu,
                        'label': f'GPU Resource ({gpu})',
                        'description': 'Please enter the number of GPUs to allocate',
                        'schema': {
                            'type': 'int',
                            'max': int(quantity),
                            'enum': [
                                {'value': i, 'description': f'Allocate {i!r} {gpu} GPU'}
                                for i in range(int(quantity) + 1)
                            ],
                            'default': 0,
                        }
                    })
            elif ref == 'definitions/timezone':
                data.update({
                    'enum': [{'value': t, 'description': f'{t!r} timezone'} for t in context['timezones']],
                    'default': context['system.general.config']['timezone']
                })
            elif ref == 'definitions/nodeIP':
                data['default'] = context['node_ip']
            elif ref == 'definitions/certificate':
                data.update({
                    'enum': [{'value': None, 'description': 'No Certificate'}] + [
                        {'value': i['id'], 'description': f'{i["name"]!r} Certificate'}
                        for i in context['certificates']
                    ],
                    'default': None,
                    'null': True,
                })
            elif ref == 'definitions/certificateAuthority':
                data.update({
                    'enum': [{'value': None, 'description': 'No Certificate Authority'}] + [
                        {'value': i['id'], 'description': f'{i["name"]!r} Certificate Authority'}
                        for i in context['certificate_authorities']
                    ],
                    'default': None,
                    'null': True,
                })

        schema.update(data)
