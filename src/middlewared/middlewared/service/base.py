from abc import ABCMeta
import inspect
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from middlewared.api.base import BaseModel
    from middlewared.api.base.handler.model_provider import ModelFactory


def service_config(klass: 'ServiceBase', config: dict):
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
        # Set this to `true` if you inherit from `CRUDService[EntryModel]` so that `query` and `get_instance` return
        # model classes. FIXME: eventually this will be true for all classes, and this setting must be removed.
        'generic': False,
    }
    config_attrs.update({
        k: v
        for k, v in list(config.items())
        if not k.startswith('_')
    })

    return type('Config', (), config_attrs)


def get_service_name(klass: type) -> str:
    service_name = klass.__name__
    if service_name.endswith('Service'):
        service_name = service_name[:-7]

    return service_name


def _validate_schema_name(service_name: str, method_name: str, method, errors: list) -> None:
    # Remove do_ prefix only for do_create, do_update, do_delete
    if method_name in ('do_create', 'do_update', 'do_delete'):
        method_name = method_name[3:]

    # Convert snake_case to CamelCase
    method_name = ''.join(word.capitalize() for word in method_name.split('_'))
    expected_accepts = f'{service_name}{method_name}Args'
    expected_returns = f'{service_name}{method_name}Result'

    accepts_name = method.new_style_accepts.__name__
    if accepts_name not in ('QueryArgs', expected_accepts):
        errors.append(
            f'API method {method!r} has incorrect accepts class name. '
            f'Expected {expected_accepts}, got {accepts_name}.'
        )

    returns_name = method.new_style_returns.__name__
    if returns_name != expected_returns:
        errors.append(
            f'API method {method!r} has incorrect returns class name. '
            f'Expected {expected_returns}, got {returns_name}.'
        )


def validate_api_method_schema_class_names(klass: 'ServiceBase') -> None:
    """
    Validate that API method argument class names follow the required format:
    - accepts class should be named f'{ServiceName}{MethodName}Args'
    - returns class should be named f'{ServiceName}{MethodName}Result'
    where MethodName is the method name converted from snake_case to CamelCase
    """
    if klass._config.private:
        return

    base_names = frozenset(b.__name__ for b in (klass,) + klass.__bases__)
    skip_methods = {'call2', 'call_sync2'}

    # These methods are wrapped later in their respective metaclasses
    if base_names & {'ConfigService', 'SystemServiceService'}:
        skip_methods |= {'config', 'update'}
    if base_names & {'CRUDService', 'SharingService', 'SharingTaskService', 'TaskPathService'}:
        skip_methods |= {'query', 'get_instance', 'create', 'update', 'delete'}

    errors = []
    service_name = get_service_name(klass)
    for name, method in inspect.getmembers(klass, predicate=inspect.isfunction):
        if (
            name.startswith('_')
            or getattr(method, '_private', False)
            or name in skip_methods
        ):
            continue

        if not hasattr(method, 'new_style_accepts'):
            raise RuntimeError(
                f'API method {method!r} is public, but has no @api_method.'
            )

        _validate_schema_name(service_name, name, method, errors)

    if errors:
        raise RuntimeError(
            f'Service {klass.__name__} has API method schema class name validation errors:\n' + '\n'.join(errors)
        )


def validate_entry_schema_class_names(klass: 'ServiceBase') -> None:
    """
    Validate that `Config.entry` model is named `{ServiceName}Entry`.

    Example: UserService must have entry model named UserEntry.
    """
    model = klass._config.entry
    if model is None:
        return

    service_name = get_service_name(klass)
    model_name = f'{service_name}Entry'
    if model.__name__ != model_name:
        raise RuntimeError(
            f'Service {klass.__name__} has incorrect entry schema class name. Expected {model_name}, '
            f'got {model.__name__}.'
        )


def validate_event_schema_class_names(klass: 'ServiceBase') -> None:
    """
    Validate that event model class names follow the required naming convention.

    Events are defined in `Config.events` with models for each event type (ADDED, CHANGED, REMOVED).
    This function ensures model class names follow the pattern:

    For events within the service namespace (event name starts with "{namespace}."):
        {ServiceName}{EventSuffix}{EventType}Event
        Example: AlertService with event "alert.list" expects:
            - AlertListAddedEvent
            - AlertListChangedEvent
            - AlertListRemovedEvent

    For events outside the service namespace:
        {FullEventName}{EventType}Event (all parts capitalized)
        Example: event "system.shutdown" expects SystemShutdownAddedEvent, etc.

    Called by `ServiceBase.__new__` during service class creation. Raises RuntimeError
    if any event models have incorrect names.
    """
    service_name = get_service_name(klass)
    prefix = f'{klass._config.namespace}.'

    errors = []
    for event in klass._config.events:
        for event_type, model in event.models.items():
            if event.name.startswith(prefix):
                model_name = service_name + ''.join(
                    word.capitalize()
                    for word in event.name.removeprefix(prefix).replace('.', '_').split('_') + [event_type, 'Event']
                )
            else:
                # We allow events to be defined outside its parent service namespace
                model_name = ''.join(
                    word.capitalize()
                    for word in event.name.replace('.', '_').split('_') + [event_type, 'Event']
                )

            if model.__name__ != model_name:
                errors.append(
                    f'Event {event.name!r} has incorrect {event_type} model class name. '
                    f'Expected {model_name}, got {model.__name__}.'
                )

    if errors:
        raise RuntimeError(
            f'Service {klass.__name__} has API event schema class name validation errors:\n' + '\n'.join(errors)
        )


class ServiceBase(ABCMeta):
    """
    Metaclass of all services

    This metaclass instantiates a `_config` attribute in the service instance
    from options provided in a Config class, e.g.

    class MyService(Service):

        class Config:
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
    _config: type
    """Full `Config` class generated by `service_config`."""
    _config_specified: dict
    """All non-private attributes explicitly set in the `Config` class. Used by `CompoundService`."""
    _register_models: list[tuple[type['BaseModel'], 'ModelFactory', str]]
    """
    List of models to register with API versions for backwards compatibility.

    Each tuple contains `(model_class, model_factory, entry_model_name)`. This list is
    populated by collecting `_register_models` from all methods decorated with `@api_method`,
    as well as from CRUD/Config service metaclasses. During middleware initialization in
    `main.py`, these are iterated over to call `api_version.register_model()` for each
    API version, enabling version-specific model transformations.
    """

    def __new__(cls, name: str, bases: tuple[type, ...], attrs: dict):
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

        validate_api_method_schema_class_names(klass)
        validate_entry_schema_class_names(klass)
        validate_event_schema_class_names(klass)

        return klass
