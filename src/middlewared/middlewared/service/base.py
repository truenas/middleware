import inspect


def service_config(klass, config):
    namespace = klass.__name__
    if namespace.endswith('Service'):
        namespace = namespace[:-7]
    namespace = namespace.lower()

    config_attrs = {
        'datastore': None,
        'datastore_prefix': '',
        'datastore_extend': None,
        'datastore_extend_fk': None,
        'datastore_extend_context': None,
        'datastore_primary_key': 'id',
        'datastore_primary_key_type': 'integer',
        'entry': None,
        'event_register': True,
        'event_send': True,
        'events': [],
        'event_sources': {},
        'service': None,
        'service_verb': 'reload',
        'service_verb_sync': True,
        'namespace': namespace,
        'namespace_alias': None,
        'private': False,
        'thread_pool': None,
        'process_pool': None,
        'cli_namespace': None,
        'cli_private': False,
        'cli_description': None,
        'role_prefix': None,
        'role_separate_delete': False,
        'verbose_name': klass.__name__.replace('Service', ''),
    }
    config_attrs.update({
        k: v
        for k, v in list(config.items())
        if not k.startswith('_')
    })

    return type('Config', (), config_attrs)


def validate_api_method_schema_class_names(klass):
    """
    Validate that API method argument class names follow the required format:
    - accepts class should be named f"{ServiceName}{MethodName}Args"
    - returns class should be named f"{ServiceName}{MethodName}Result"
    where MethodName is the method name converted from snake_case to CamelCase
    """
    service_name = klass.__name__
    if service_name.endswith('Service'):
        service_name = service_name[:-7]

    errors = []
    for name, method in inspect.getmembers(klass, predicate=inspect.isfunction):
        if name.startswith('_') or getattr(method, '_private', False) or klass._config.private:
            continue

        methods_will_be_wrapped_later = {
            "ConfigService": {"config", "update"},
            "CRUDService": {"query", "get_instance", "create", "update", "delete"},
        }
        methods_will_be_wrapped_later["SystemServiceService"] = methods_will_be_wrapped_later["ConfigService"]
        methods_will_be_wrapped_later["SharingService"] = methods_will_be_wrapped_later["CRUDService"]
        methods_will_be_wrapped_later["SharingTaskService"] = methods_will_be_wrapped_later["CRUDService"]
        methods_will_be_wrapped_later["TaskPathService"] = methods_will_be_wrapped_later["CRUDService"]
        will_be_wrapped_later = False
        for base in (klass,) + klass.__bases__:
            if name in methods_will_be_wrapped_later.get(base.__name__, set()):
                will_be_wrapped_later = True
                break
        if will_be_wrapped_later:
            continue

        if not hasattr(method, 'new_style_accepts'):
            raise RuntimeError(
                f"API method {method!r} is public, but has no @api_method."
            )

        # Remove do_ prefix only for do_create, do_update, do_delete
        method_name = name[3:] if name in ('do_create', 'do_update', 'do_delete') else name

        # Convert snake_case to CamelCase
        method_name = ''.join(word.capitalize() for word in method_name.split('_'))
        expected_accepts = f"{service_name}{method_name}Args"
        expected_returns = f"{service_name}{method_name}Result"

        if method.new_style_accepts.__name__ != 'QueryArgs':
            if method.new_style_accepts.__name__ != expected_accepts:
                errors.append(
                    f"API method {method!r} has incorrect accepts class name. "
                    f"Expected {expected_accepts}, got {method.new_style_accepts.__name__}."
                )

        if method.new_style_returns.__name__ != expected_returns:
            errors.append(
                f"API method {method!r} has incorrect returns class name. "
                f"Expected {expected_returns}, got {method.new_style_returns.__name__}."
            )

    if errors:
        raise RuntimeError(
            f"Service {klass.__name__} has API method schema class name validation errors:\n" + '\n'.join(errors)
        )


def validate_event_schema_class_names(klass):
    errors = []
    for event in klass._config.events:
        for event_type, model in event.models.items():
            model_name = ''.join(
                word.capitalize()
                for word in event.name.replace('.', '_').split('_') + [event_type, 'Event']
            )
            if model.__name__ != model_name:
                errors.append(
                    f"Event {event.name!r} has incorrect {event_type} model class name. "
                    f"Expected {model_name}, got {model.__name__}."
                )

    if errors:
        raise RuntimeError(
            f"Service {klass.__name__} has API event schema class name validation errors:\n" + '\n'.join(errors)
        )


class ServiceBase(type):
    """
    Metaclass of all services

    This metaclass instantiates a `_config` attribute in the service instance
    from options provided in a Config class, e.g.

    class MyService(Service):

        class Meta:
            namespace = 'foo'
            private = False

    Currently the following options are allowed:
      - datastore: name of the datastore mainly used in the service
      - datastore_extend: datastore `extend` option used in common `query` method
      - datastore_extend_fk: datastore `extend_fk` option used in common `query` method
      - datastore_prefix: datastore `prefix` option used in helper methods
      - service: system service `name` option used by `SystemServiceService`
      - service_verb: verb to be used on update (default to `reload`)
      - namespace: namespace identifier of the service
      - namespace_alias: another namespace identifier of the service, mostly used to rename and
                         slowly deprecate old name.
      - private: whether or not the service is deemed private
      - verbose_name: human-friendly singular name for the service
      - thread_pool: thread pool to use for threaded methods
      - process_pool: process pool to run service methods
      - cli_namespace: replace namespace identifier for CLI
      - cli_private: if the service is not private, this flags whether or not the service is visible in the CLI
    """

    def __new__(cls, name, bases, attrs):
        super_new = super(ServiceBase, cls).__new__
        if name == 'Service' and bases == ():
            return super_new(cls, name, bases, attrs)

        config = attrs.pop('Config', None)
        klass = super_new(cls, name, bases, attrs)

        if config:
            klass._config_specified = {k: v for k, v in config.__dict__.items() if not k.startswith('_')}
        else:
            klass._config_specified = {}

        klass._config = service_config(klass, klass._config_specified)
        klass._register_models = sum([getattr(getattr(klass, m), '_register_models', []) for m in dir(klass)], [])

        # Validate API method argument class names
        validate_api_method_schema_class_names(klass)
        # Validate event schemas class names
        validate_event_schema_class_names(klass)

        return klass
