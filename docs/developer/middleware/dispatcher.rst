dispatcher server
=================

Basic information
-----------------

dispatcher runs as an UNIX service and handles incoming WebSocket
connections on port 5000 by default (that can be changed in
configuration file).

Three basic kinds of animals living inside are:

Data providers
~~~~~~~~~~~~~~

Data providers can supply informations about running system to the
clients. They should not change any system state (tasks are designed for
that purpose). Data provider is a single Python class, deriving from
``task.Provider``.

Event sources
~~~~~~~~~~~~~

Event sources are threads running an event loop inside (for example,
endless loop reading events from file descriptor) and pushing events to
dispatcher router.

Task handlers
~~~~~~~~~~~~~

`Task handlers specification <tasks.md>`__

Configuration file
------------------

Whole middleware ecosystem use single configuration file for getting
database credentials and basic configuration settings. It's a JSON file
stored under path ``/usr/local/etc/middleware.conf`` and can look like
that:

.. code-block:: javascript

    {
        "datastore": {
            "driver": "mongodb",
            "dsn": "mongodb://localhost"
        },

        "dispatcher": {
            "pidfile": "/var/run/dispatcher.pid",
            "websocket-port": 5000,
            "frontend-port": 8180,
            "tls": false,
            "logging": "syslog",
            "plugin-dirs": [
                "/usr/local/lib/dispatcher/plugins",
                "/opt/dispatcher-plugins"
            ]
        },

        "etcd": {
            "pidfile": "/var/run/etcd.pid",
            "logging": "syslog",
            "plugin-dirs": [
                "/usr/local/lib/etcd/plugins"
            ]
        },

        "cli": {
            "plugin-dirs": [
                "/usr/local/lib/freenascli/plugins"
            ]
        }
    }

Debug mode server
-----------------

By default, dispatcher starts "debug mode" server on port 8180. It
allows user to play with offered data providers, watch generated events
and submit tasks.

Plugin writing guidelines
-------------------------

JSON schemas
~~~~~~~~~~~~

Arguments and return values of RPC calls and tasks can be (and should be) validated using
JSON schema. It's easier and simpler than manually checking validity of input
arguments. There are following decorators which can be used to attach JSON schema
information:

.. py:function:: @accepts(schemas...)

.. py:function:: @returns(schema)

.. py:function:: @description(descr)

Plugin interface
~~~~~~~~~~~~~~~~

Plugin should be contained in single Python module (either .py, .pyc or .so).
Plugin should define following global functions:

.. py:function:: _depends()

    Should return a list of other plugin names required for that particular
    plugin. dispatcher will ensure that dependent plugins will be loaded
    first.

.. py:function:: _init(dispatcher)

    Initialization method, is called on startup or reload and should
    register all plugin data providers, event sources, task handlers, JSON
    schema models, etc.

.. py:function:: _cleanup(dispatcher)

    Finalization method, called on server exit or when server reloads
    plugin. Should unregister all the stuff registered in :func:`_init()`

.. py:function:: _metadata()

    This function can be implemented to attach any arbitrary metadata to
    plugin instance. By convention, it should return Python dictionary.


dispatcher public interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:function:: dispatcher.register_provider(name, impl_class)

    Registers new RPC interface under namespace ``name``. ``impl_class``
    should be reference to Python class (not instance) derived from ``tasks.Provider``.
    Single instance of that class will be created and managed by server.
    That said, all exposed methods should be thread-safe.

.. py:function:: dispatcher.unregister_provider(name)

    Unregisters RPC interface previously registered under namespace ``name``.

.. py:function:: dispatcher.register_event_source(name, impl_class)

    Registers new event source under name ``name``. ``impl_class`` should
    be reference to Python class (not instance) derived from ``events.EventSource``.

.. py:function:: dispatcher.unregister_event_source(name)

    Stops and unregisters previously registered event source ``name``.

.. py:function:: dispatcher.register_task_handler(name, impl_class)

    Registers new task under name ``name``. ``impl_class`` should be
    reference to Python class derived from ``task.Task``.

.. py:function:: dispatcher.unregister_task_handler(name)

    Unregisters previously registered task ``name``.

.. py:function:: dispatcher.register_schema_definition(name, schema)

.. py:function:: dispatcher.unregister_schema_definition(name)

.. py:function:: dispatcher.register_event_handler(event_name, func)

.. py:function:: dispatcher.unregister_event_handler(event_name, func)

.. py:function:: dispatcher.emit_event(name, properties)

.. py:function:: dispatcher.call_sync(method, args...)


