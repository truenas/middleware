===========
middlewared
===========

middlewared is a central daemon written in Python which handles Remote Procedure Calls (RPCs) and event notification.

These are implemented through services which are part of a plugin system.

Services can be accessed through a WebSocket or a RESTful API.


 -----------  ---------  ----------
| WebSocket || RESTful || API Docs |
 -----------  ---------  ----------
|     Service A  |    Service B    |
 ----------------------------------
|            middlewared           |
 ----------------------------------


Services
--------

Currently we defined 3 types of services: "service", "config" and "crud".

 - service: The base of all services, defined in `middlewared.service.Service`.

 - config: It inherits "service", defined in `middlewared.service.ConfigService`. Represents a single entity, in other words, exposes at least two methods: "config" to retrieve the service configuration and "update" to update the service configuration.

 - crud: It inherits "service", defined in `middleware.service.CRUDService`.  Represents a collection and usually exposes at least four methods: "query" to retrieve a collection, "create" to create an item, "update" to update an item and "delete" to delete an item.

Each public method of these classes is a remote procedure.


e.g.

    class FooService(Service):
    
        class Config:
            namespace = 'foo'
            private = False
    
        def bar(self):
            return 'bar'

Jobs
~~~~

Methods can be special and be treated as a job. Job is a long running method which can be queried for status and progress.

Jobs are put in a single queue, processed as a FIFO, and can share an exclusive lock.

Job is a decorator and takes the following parameters:

 - lock: a string or a callable for the shared lock name
 - process: a boolean on whether the job should run as a standalone process or a green thread.

e.g.
    @job(lock='update', process=True)
    def update(self, job):
        job.set_progress(0, 'Fetching')


Getting jobs status is done through the method `core.get_jobs`.


WebSocket
---------

The primary way to access services is through the WebSocket interface. We have chosen to use the DDP Protocol.

DDP (Distributed Data Protocol, https://github.com/meteor/meteor/blob/devel/packages/ddp/DDP.md) is the stateful websocket protocol to communicate between the client and the server.

Websocket endpoint: /websocket

e.g. ws://freenas.domain/websocket

Connection
~~~~~~~~~~

Client connects to websocket endpoint and sends a `connect` message.

    {
      "msg": "connect",
      "version": "1",
      "support": ["1"]
    }

Server answers with either `connected` or `failed`.

    {
      "msg": "connected",
      "session": "b4a4d164-6bc7-11e6-8a93-00e04d680384"
    }

Authentication
~~~~~~~~~~~~~~

Authentication happens by calling the `auth.login` method.

Request:

    {
      "id": "d8e715be-6bc7-11e6-8c28-00e04d680384",
      "msg": "method",
      "method": "auth.login",
      "params": ["username", "password"]
    }

Response:

    {
      "id": "d8e715be-6bc7-11e6-8c28-00e04d680384",
      "msg": "result",
      "result": true,
    }
