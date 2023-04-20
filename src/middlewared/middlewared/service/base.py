def service_config(klass, config):
    namespace = klass.__name__
    if namespace.endswith('Service'):
        namespace = namespace[:-7]
    namespace = namespace.lower()

    config_attrs = {
        'datastore': None,
        'datastore_prefix': '',
        'datastore_extend': None,
        'datastore_extend_context': None,
        'datastore_primary_key': 'id',
        'datastore_primary_key_type': 'integer',
        'event_register': True,
        'event_send': True,
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
        return klass
