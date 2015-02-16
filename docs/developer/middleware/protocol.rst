dispatcher protocol specification
=================================

Preliminary information
-----------------------

All interaction with dispatcher is done using WebSockets connection.
Messages are formatted as JSON objects and sent encoded as UTF-8
strings. Connection could be either plain WebSockets (ws:// prefix) or
secured using the TLS (wss:// prefix).

Event and RPC calls routing
---------------------------

dispatcher is merely an event and RPC calls router. Some exposed RPC
interfaces and events may originate directly from dispatcher and some
others may have been routed from external daemons (such as etcd or
networkd).

Basic frame format
------------------

Every frame should have following format:

::

    {
        "namespace": "<string>",
        "name": "<string>",
        "id": "<uuid>",
        "args": "<object or array>"
    }

That applies also to responses from the sever.

Client is supposed to generate unique ID in UUID dashed format with
every call. ID will be reused in response message (if any), so client
code could associate request with asynchronous response.

UUID in desired format could be generated using Javascript function
shown below:

.. code-block:: javascript

    function uuid()
    {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c)
        {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

Logging in
----------

After establishing a connection, client needs to authenticate itself to
the server. There are currently four different ways to authenticate
client to server.

Logging in as a user with login & password
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Login frame:

.. code-block:: javascript

    {
        "namespace": "rpc",
        "name": "auth",
        "id": "<uuid>",
        "args": {
            "username": "<user name>",
            "password": "<user password in plain text>"
        }
    }

Server should response with following frame when authentication
succeeds:

.. code-block:: javascript

    {
        "namespace": "rpc",
        "name": "response",
        "id": "<uuid>",
        "args": ["<token>", <token validity in seconds>]
    }

Logging in as a user with token
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

After first successful login using username & password, server returns a
token and number of seconds before token expires. That token can be used
to relogin user (eg. when refreshing page in the browser).

.. code-block:: javascript

    {
        "namespace": "rpc",
        "name": "auth_token",
        "id": "<uuid>",
        "args": {
            "token": "<token>",
        }
    }

Server should response with following frame when authentication
succeeds:

.. code-block:: javascript

    {
        "namespace": "rpc",
        "name": "response",
        "id": "<uuid>",
        "args": ["<new token>", <token validity in seconds>]
    }

Logging in as a user locally
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When connecting to localhost (127.0.0.1 or ::1), user can login
providing correct username, but with no password. Server will validate
login request by looking for socket opened by that user with matching
source port.

Logging in as a service
^^^^^^^^^^^^^^^^^^^^^^^

Services can login only locally (from localhost). There's no password
authentication. Login frame should look like that:

.. code-block:: javascript

    {
        "namespace": "rpc",
        "name": "auth_service",
        "id": "<uuid>",
        "args": {
            "name": "<service name>",
        }
    }

Authentication failures
^^^^^^^^^^^^^^^^^^^^^^^

Following frame is sent when authentication fails. That applies to all
authentication methods.

.. code-block:: javascript

    {
        "namespace": "rpc",
        "name": "error",
        "id": "<uuid>",
        "args": {
            "code": <integer errno code>,
            "message": "<error description>"
        }
    }

Listening for the events
~~~~~~~~~~~~~~~~~~~~~~~~

Subscribe frame:

.. code-block:: javascript

    {
        "namespace": "events",
        "name": "subscribe",
        "id": "<uuid>",
        "args": ["<event-mask-1>", "<event-mask-2>", ...]
    }

Unsubscribing is done by sending exactly the same frame, but with the
"unsubscribe" value in the "name" field.

Providing ["\*"] as the "args" value would effectively subscribe to all
events generated.

When an event is generated, following frame is sent from server to the
client:

.. code-block:: javascript

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

Logging out
-----------

Logging out basically consist of closing WebSocket connection. New user
can log in by creating new connection.

JSON Schema validation
----------------------

XXX

Obtaining data (RPC calls)
--------------------------

Reading data from the middleware is done using RPC-style call. Call
consists of method name and arguments. Method name is composed from
interface name and actual method name, separated by dots. Interface name
can also contain dots.

Here are some examples of method names:

-  discovery.get\_services
-  task.submit
-  foo.shmoo.bar.baz.quux

In the last case, "foo.shmoo.bar.baz" is the interface name and "quux"
is the method name.

Frame format
~~~~~~~~~~~~

RPC call frame:

.. code-block:: javascript

    {
        "namespace": "rpc",
        "name": "call",
        "id": "<uuid>",
        "args": {
            "method": "<interface and method path>",
            "args": "<object or array>"
        }
    }

RPC call response:

.. code-block:: javascript

    {
        "namespace": "rpc",
        "name": "error",
        "id": "<uuid>",
        "args": "<object or array with returned values>"
    }

RPC call erroneous response:

.. code-block:: javascript

    {
        "namespace": "rpc",
        "name": "error",
        "id": "<uuid>",
        "args": {
            "code": <integer errno code>,
            "message": "<error description>"
        }
    }

Universal query format
~~~~~~~~~~~~~~~~~~~~~~

Interfaces providing access to collections of objects should implement
method called ``query``. It has standarized protocol.

``query(filter=null, params=null)``

-  ``filter`` should be either ``null`` or array of 3-element arrays
   (3-element tuples in Python terminology).
-  ``params`` should be either ``null`` or object.

Semantics of ``filter`` and ``params`` arguments is the same as in
``datastore.query`` method. See `datastore
documentation <datastore.md>`__ for details.

Interface enumeration
---------------------

Middleware server supports interface enumeration. That is, it's possible
to programatically discover what interfaces and methods are supported.

Enumeration methods are contained in interface named "discovery".

discovery.get\_services
~~~~~~~~~~~~~~~~~~~~~~~

Returns a list of services (interfaces) on the server. Pass empty array
or empty object as "args"

Returns args formatted as follows:

.. code-block:: javascript

    [
        {
            "name": "<service/interface name>",
            "description: "<blah blah blah...>",
        },
        ...
    ]

discovery.get\_methods
~~~~~~~~~~~~~~~~~~~~~~

Returns a list of methods inside given interface. Pass one-element array
with interface/service name as it's only argument.

Returns args formatted as follows:

.. code-block:: javascript

    [
        {
            "name": "<method name>",
            "description: "<blah blah blah...>",
            "schema": {
                <json-schema of expected args format>
            }
        },
        ...
    ]

discovery.get\_tasks
~~~~~~~~~~~~~~~~~~~~

Returns a list of available task classes on the server. Pass empty array
or empty object as "args"

Returns list in same format as in discovery.get\_methods

Submitting tasks
----------------

Interface for managing a task queue is called "tasks". It offers
following methods:

``task.submit(class_name, args)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``task.abort(task_id)``
~~~~~~~~~~~~~~~~~~~~~~~

``task.status(task_id)``
~~~~~~~~~~~~~~~~~~~~~~~~

``task.query(filter=null, params=null)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``task.list_resources()``
~~~~~~~~~~~~~~~~~~~~~~~~~

Interacting with external services (daemons)
--------------------------------------------

External services may expose their interfaces and emit events through
dispatcher, so they can be consumed by the clients in uniform way. To do
so, service should connect to dispatcher and then login itself as a
service (see XXX).

plugin.register\_service
~~~~~~~~~~~~~~~~~~~~~~~~

plugin.unregister\_service
~~~~~~~~~~~~~~~~~~~~~~~~~~

plugin.wait\_for\_service
~~~~~~~~~~~~~~~~~~~~~~~~~

Spawning shell on server
------------------------

shell.execute
~~~~~~~~~~~~~

shell.spawn
~~~~~~~~~~~

