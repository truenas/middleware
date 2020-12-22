## Websocket Protocol

TrueNAS uses DDP: https://github.com/meteor/meteor/blob/devel/packages/ddp/DDP.md .

DDP (Distributed Data Protocol) is the stateful websocket protocol to communicate between the client and the server.

Websocket endpoint: `/websocket`

e.g. `ws://truenas.domain/websocket`

### Example of connection

#### Client connects to websocket endpoint and sends a `connect` message.

    :::javascript
    {
      "msg": "connect",
      "version": "1",
      "support": ["1"]
    }

#### Server answers with either `connected` or `failed`.

    :::javascript
    {
      "msg": "connected",
      "session": "b4a4d164-6bc7-11e6-8a93-00e04d680384"
    }

### Authentication

Authentication happens by calling the `auth.login` method.

Request:

    :::javascript
    {
      "id": "d8e715be-6bc7-11e6-8c28-00e04d680384",
      "msg": "method",
      "method": "auth.login",
      "params": ["username", "password"]
    }

Response:

    :::javascript
    {
      "id": "d8e715be-6bc7-11e6-8c28-00e04d680384",
      "msg": "result",
      "result": true,
    }
