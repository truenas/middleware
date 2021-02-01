import itertools
import markdown
import os
import yaml

from pkg_resources import parse_version

from middlewared.schema import Bool, Dict, Str
from middlewared.service import accepts, private, Service, ValidationErrors


ITEM_KEYS = ['icon_url']


class CatalogService(Service):

    class Config:
        cli_namespace = 'app.catalog'

    @accepts(
        Str('label'),
        Dict(
            'options',
            Bool('cache', default=True),
            Bool('retrieve_unusable_apps', default=False),
        )
    )
    def items(self, label, options):
        """
        Retrieve item details for `label` catalog.

        `options.cache` is a boolean which when set will try to get items details for `label` catalog from cache
        if available.
        """
        catalog = self.middleware.call_sync('catalog.get_instance', label)

        if options['cache'] and self.middleware.call_sync('cache.has_key', f'catalog_{label}_train_details'):
            return self.middleware.call_sync('cache.get', f'catalog_{label}_train_details')
        elif not os.path.exists(catalog['location']):
            self.middleware.call_sync('catalog.update_git_repository', catalog, True)

        # TODO: Let's please add alerts for malformed catalogs
        #  1) No train
        #  2) Empty trains
        #  3) Empty catalog item with no version
        #  4) Malformed catalog item in a train
        #  5) Unable to clone / pull the catalog
        # We make sure we do not dive into library folder and not consider it a train
        # This allows us to use this folder for placing helm library charts
        trains = {'charts': {}, 'test': {}}
        trains.update({
            t: {} for t in os.listdir(catalog['location'])
            if os.path.isdir(os.path.join(catalog['location'], t)) and not t.startswith('.') and t != 'library'
        })
        for train in filter(lambda c: os.path.exists(os.path.join(catalog['location'], c)), trains):
            category_path = os.path.join(catalog['location'], train)
            for item in filter(lambda p: os.path.isdir(os.path.join(category_path, p)), os.listdir(category_path)):
                item_location = os.path.join(category_path, item)
                trains[train][item] = item_data = {
                    'name': item,
                    'location': item_location,
                    'healthy': False,  # healthy means that each version the item hosts is valid and healthy
                    'healthy_error': None,  # An error string explaining why the item is not healthy
                    'versions': {},
                }

                schema = f'{train}.{item}'
                try:
                    self.middleware.call_sync('catalog.validate_catalog_item', item_location, schema, False)
                except ValidationErrors as verrors:
                    item_data['healthy_error'] = f'Following error(s) were found with {item!r}:\n'
                    for verror in verrors:
                        item_data['healthy_error'] += f'{verror[0]}: {verror[1]}'

                    # If the item format is not valid - there is no point descending any further into versions
                    continue

                item_data.update(self.item_details(item_location, schema))
                unhealthy_versions = [k for k, v in item_data['versions'].items() if not v['healthy']]
                if unhealthy_versions:
                    item_data['healthy_error'] = f'Errors were found with {", ".join(unhealthy_versions)} version(s)'
                else:
                    item_data['healthy'] = True

        self.middleware.call_sync('cache.put', f'catalog_{label}_train_details', trains, 86400)
        if label == self.middleware.call_sync('catalog.official_catalog_label'):
            # Update feature map cache whenever official catalog is updated
            self.middleware.call_sync('catalog.get_feature_map', False)

        return trains

    @private
    def item_details(self, item_path, schema):
        # Each directory under item path represents a version of the item and we need to retrieve details
        # for each version available under the item
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
                'healthy_error': None,
                'location': os.path.join(item_path, version),
                'required_features': [],
            }
            try:
                self.middleware.call_sync(
                    'catalog.validation_catalog_item_version', version_details['location'], f'{schema}.{version}'
                )
            except ValidationErrors as verrors:
                version_details['healthy_error'] = f'Following error(s) were found with {version!r}:\n'
                for verror in verrors:
                    version_details['healthy_error'] += f'{verror[0]}: {verror[1]}'

                # There is no point in trying to see what questions etc the version has as it's invalid
                continue

            version_details.update({'healthy': True, **self.item_version_details(version_details['location'])})

        return item_data

    @private
    def item_version_details(self, version_path):
        version_data = {'location': version_path, 'required_features': set()}
        for key, filename, parser in (
            ('values', 'values.yaml', yaml.safe_load),
            ('schema', 'questions.yaml', yaml.safe_load),
            ('app_readme', 'app-readme.md', str.strip),
            ('detailed_readme', 'README.md', markdown.markdown),
        ):
            with open(os.path.join(version_path, filename), 'r') as f:
                version_data[key] = parser(f.read())

        # We will normalise questions now so that if they have any references, we render them accordingly
        # like a field referring to available interfaces on the system
        self.normalise_questions(version_data)

        version_data['supported'] = self.middleware.call_sync('catalog.version_supported', version_data)
        version_data['required_features'] = list(version_data['required_features'])
        version_data['values'] = self.middleware.call_sync(
            'chart.release.construct_schema_for_item_version', version_data, version_data['values'], False
        )['new_values']

        return version_data

    @private
    def normalise_questions(self, version_data):
        for question in version_data['schema']['questions']:
            self._normalise_question(question, version_data)

    def _normalise_question(self, question, version_data):
        schema = question['schema']
        for attr in itertools.chain(*[schema.get(k, []) for k in ('attrs', 'items', 'subquestions')]):
            self._normalise_question(attr, version_data)

        if '$ref' not in schema:
            return

        data = {}
        for ref in schema['$ref']:
            version_data['required_features'].add(ref)
            if ref == 'definitions/interface':
                data['enum'] = [
                    {'value': i, 'description': f'{i!r} Interface'}
                    for i in self.middleware.call_sync('chart.release.nic_choices')
                ]
            elif ref == 'definitions/gpuConfiguration':
                data['attrs'] = []
                for gpu, quantity in self.middleware.call_sync('k8s.gpu.available_gpus').items():
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
                data['enum'] = [
                    {'value': t, 'description': f'{t!r} timezone'}
                    for t in self.middleware.call_sync('system.general.timezone_choices')
                ]
            elif ref == 'definitions/nodeIP':
                data['default'] = self.middleware.call_sync('kubernetes.node_ip')

        schema.update(data)
