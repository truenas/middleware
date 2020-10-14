import itertools
import markdown
import os
import yaml

from middlewared.schema import Bool, Dict, Str
from middlewared.service import accepts, private, Service


ITEM_KEYS = ['icon_url']


class CatalogService(Service):

    @accepts(
        Str('label'),
        Dict(
            'options',
            Bool('cache', default=True),
        )
    )
    def items(self, label, options):
        catalog = self.middleware.call_sync('catalog.get_instance', label)

        if options['cache'] and self.middleware.call_sync('cache.has_key', f'catalog_{label}_train_details'):
            return self.middleware.call_sync('cache.get', f'catalog_{label}_train_details')
        else:
            self.middleware.call_sync('catalog.update_git_repository', catalog, True)

        trains = {'charts': {}, 'test': {}}
        for train in filter(lambda c: os.path.exists(os.path.join(catalog['location'], c)), trains):
            category_path = os.path.join(catalog['location'], train)
            for item in filter(lambda p: os.path.isdir(os.path.join(category_path, p)), os.listdir(category_path)):
                item_location = os.path.join(category_path, item)
                trains[train][item] = {
                    'name': item,
                    'location': item_location,
                    **self.item_details(item_location)
                }

        self.middleware.call_sync('cache.put', f'catalog_{label}_train_details', trains, 86400)

        return trains

    @private
    def item_details(self, item_path):
        # Each directory under item path represents a version of the item and we need to retrieve details
        # for each version available under the item
        item_data = {'versions': {}}
        with open(os.path.join(item_path, 'item.yaml'), 'r') as f:
            item_data.update(yaml.load(f.read()))

        item_data.update({k: item_data.get(k) for k in ITEM_KEYS})

        for version in filter(lambda p: os.path.isdir(os.path.join(item_path, p)), os.listdir(item_path)):
            item_data['versions'][version] = self.item_version_details(
                os.path.join(item_path, version), item_data,
            )
        return item_data

    @private
    def item_version_details(self, version_path):
        version_data = {'location': version_path, 'required_features': []}
        for key, filename, parser in (
            ('version_config', 'item.yaml', yaml.load),
            ('values', 'values.yaml', yaml.load),
            ('schema', 'questions.yaml', yaml.load),
            ('app_readme', 'app-readme.md', markdown.markdown),
            ('detailed_readme', 'README.md', markdown.markdown),
        ):
            if not os.path.exists(os.path.join(version_path, filename)):
                continue

            with open(os.path.join(version_path, filename), 'r') as f:
                version_data[key] = parser(f.read())

        # We will normalise questions now so that if they have any references, we render them accordingly
        # like a field referring to available interfaces on the system
        self.normalise_questions(version_data)

        version_data['supported'] = self.middleware.call_sync('catalog.version_supported', version_data)

        return version_data

    @private
    def normalise_questions(self, version_data):
        for question in version_data['schema']['questions']:
            self._normalise_question(question, version_data)

    def _normalise_question(self, question, version_data):
        schema = question['schema']
        for attr in itertools.chain(
            *[d.get(k, []) for d, k in zip((schema, schema, question), ('attrs', 'items', 'subquestions'))]
        ):
            self._normalise_question(attr, version_data)

        if '$ref' not in question['schema']:
            return

        data = {}
        for ref in question['schema']['$ref']:
            version_data['required_features'].append(ref)
            if ref == 'definitions/interface':
                data['enum'] = [d['id'] for d in self.middleware.call_sync('interface.query')]

        question['schema'].update(data)
