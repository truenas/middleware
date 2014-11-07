# Middleware protocol specification

### Preliminary information

All interaction with middleware is done using WebSockets connection.
Messages are formatted as JSON objects and sent encoded as UTF-8 strings.
Connection could be either plain WebSockets (ws:// prefix) or secured
using the TLS (wss:// prefix).

### Basic frame format

Every frame should have following format:
```
{
    "namespace": "<string>",
    "name": "<string>",
    "id": "<uuid>",
    "args": "<object or array>"
}
```

That applies also to responses from the sever.

Client is supposed to generate unique ID in UUID dashed format with every
call. ID will be reused in response message (if any), so client code could
associate request with asynchronous response.

UUID in desired format could be generated using Javascript function shown
below:
```javascript
function uuid()
{
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c)
    {
        var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}
```

### Logging in

After establishing a connection, client needs to authenticate itself to
the server.

Login frame:
```
{
    "namespace": "rpc",
    "name": "auth",
    "id": "<uuid>",
    "args": {
        "username": "<user name>",
        "password": "<user password in plain text>"
    }
}
```

Server should response with following frame when authentication succeeds:
```
{
    "namespace": "rpc",
    "name": "response",
    "id": "<uuid>",
    "args": []
}
```

and following on authentication fails:
```
{
    "namespace": "rpc",
    "name": "error",
    "id": "<uuid>",
    "args": {
        "code": <integer errno code>,
        "message": "<error description>"
    }
}
```

### Listening for the events

Subscribe frame:
```
{
    "namespace": "events",
    "name": "subscribe",
    "id": "<uuid>",
    "args": ["<event-mask-1>", "<event-mask-2>", ...]
}
```

Unsubscribing is done by sending exactly the same frame, but with the
"unsubscribe" value in the "name" field.

Providing ["*"] as the "args" value would effectively subscribe to all
events generated.

When an event is generated, following frame is sent from server to the
client:

```
{
    "namespace": "events",
    "name": "event",
    "id:" null,
    "args": {
        "name": "<event name>",
        "args": {
            <event properties...>
        }
    }
}
```

### Obtaining data (RPC calls)

Reading data from the middleware is done using RPC-style call.
Call consists of method name and arguments. Method name is composed
from interface name and actual method name, separated by dots.
Interface name can also contain dots.

Here are some examples of method names:
+ discovery.get_services
+ task.submit
+ foo.shmoo.bar.baz.quux

In the last case, "foo.shmoo.bar.baz" is the interface name and "quux"
is the method name.

RPC call frame:
```
{
    "namespace": "rpc",
    "name": "call",
    "id": "<uuid>",
    "args": {
        "method": "<interface and method path>",
        "args": "<object or array>"
    }
}
```

RPC call response:
```
{
    "namespace": "rpc",
    "name": "error",
    "id": "<uuid>",
    "args": "<object or array with returned values>"
}
```

RPC call erroneous response:
```
{
    "namespace": "rpc",
    "name": "error",
    "id": "<uuid>",
    "args": {
        "code": <integer errno code>,
        "message": "<error description>"
    }
}
```

### Interface enumeration

Middleware server supports interface enumeration. That is, it's possible to
programatically discover what interfaces and methods are supported.

Enumeration methods are contained in interface named "discovery".

###### discovery.get_services

Returns a list of services (interfaces) on the server. Pass empty
array or empty object as "args"

Returns args formatted as follows:
```
[
    {
        "name": "<service/interface name>",
        "description: "<blah blah blah...",
    },
    ...
]
```

###### discovery.get_methods

Returns a list of methods inside given interface. Pass one-element
array with interface/service name as it's only argument.

Returns args formatted as follows:
```
[
    {
        "name": "<method name>",
        "description: "<blah blah blah...",
        "schema": {
            <json-schema of expected args format>
        }
    },
    ...
]
```

###### discovery.get_tasks

Returns a list of available task classes on the server. Pass empty
array or empty object as "args"

Returns list in same format as in discovery.get_methods

### Submitting tasks

Interface for managing a task queue is called "tasks". It offers following
methods:

###### task.submit

args format:
```
["<task class name>", <args object>]
```

returns:
```
[<task id]
```

###### task.abort

TBD

###### task.get_status

TBD

###### task.list

TBD