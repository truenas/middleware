# dispatcher server

## Basic information

dispatcher runs as an UNIX service and handles incoming WebSocket connections on port 5000 by default (that can be changed in configuration file).

Three basic kinds of animals living inside are:

### Data providers

Data providers can supply informations about running system to the clients. They should not change any system state (tasks are designed for that purpose). Data provider is a single Python class, deriving from `task.Provider`.

### Event sources

Event sources are threads running an event loop inside (for example, endless loop reading events from file descriptor) and pushing events to dispatcher router.

### Task handlers

[Task handlers specification](tasks.md)

## Configuration file

Whole middleware ecosystem use single configuration file for getting database credentials and basic configuration settings. It's a JSON file stored under path `/usr/local/etc/middleware.conf` and can look like that:

```
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
```

## Debug mode server

By default, dispatcher starts "debug mode" server on port 8180. It allows user to play with offered data providers, watch generated events and submit tasks.

## Plugin writing guidelines

### Plugin interface

Plugin should be contained in single Python file (either .py or .pyc). Plugin should define following global functions:

#### `_depends()`

Should return a list of other plugin names required for that particular plugin. dispatcher will ensure that dependent plugins will be loaded first.

#### `_init(dispatcher)`

Initialization method, is called on startup or reload and should register all plugin data providers, event sources, task handlers, JSON schema models, etc.

#### `_cleanup(dispatcher)`

### dispatcher interface

#### `dispatcher.register_provider(name, impl_class)`

#### `dispatcher.unregister_provider(name)`

#### `dispatcher.register_event_source(name, impl_class)`

#### `dispatcher.unregister_event_source(name)`

#### `dispatcher.register_task_handler(name, impl_class)`

#### `dispatcher.unregister_task_handler(name)`

#### `dispatcher.register_schema_definition(name, schema)`

#### `dispatcher.unregister_schema_definition(name)`

#### `dispatcher.register_event_handler(event_name, func)`

#### `dispatcher.unregister_event_handler(event_name, func)`

#### `dispatcher.emit_event(name, properties)`

## Protocol specification

See [Protocol specification](protocol.md) document.