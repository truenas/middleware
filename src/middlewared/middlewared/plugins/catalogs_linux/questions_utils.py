import itertools


def normalise_questions(version_data: dict, context: dict) -> None:
    version_data['required_features'] = set()
    for question in version_data['schema']['questions']:
        normalise_question(question, version_data, context)
    version_data['required_features'] = list(version_data['required_features'])


def normalise_question(question: dict, version_data: dict, context: dict) -> None:
    schema = question['schema']
    for attr in itertools.chain(*[schema.get(k, []) for k in ('attrs', 'items', 'subquestions')]):
        normalise_question(attr, version_data, context)

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
            data['attrs'] = [
                {
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
                } for gpu, quantity in context['gpus'].items()
            ]
        elif ref == 'definitions/timezone':
            data.update({
                'enum': [{'value': t, 'description': f'{t!r} timezone'} for t in context['timezones']],
                'default': context['system.general.config']['timezone']
            })
        elif ref == 'definitions/nodeIP':
            data['default'] = context['node_ip']
        elif ref == 'definitions/certificate':
            get_cert_ca_options(schema, data, {'value': None, 'description': 'No Certificate'})
            data['enum'] += [
                {'value': i['id'], 'description': f'{i["name"]!r} Certificate'}
                for i in context['certificates']
            ]
        elif ref == 'definitions/certificateAuthority':
            get_cert_ca_options(schema, data, {'value': None, 'description': 'No Certificate Authority'})
            data['enum'] += [{'value': None, 'description': 'No Certificate Authority'}] + [
                {'value': i['id'], 'description': f'{i["name"]!r} Certificate Authority'}
                for i in context['certificate_authorities']
            ]

    schema.update(data)


def get_cert_ca_options(schema: dict, data: dict, default_entry: dict):
    if schema.get('null', True):
        data.update({
            'enum': [default_entry],
            'default': None,
            'null': True,
        })
    else:
        data.update({
            'enum': [],
            'required': True,
        })
