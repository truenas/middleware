General architecture
====================

FreeNAS 10 middleware is organized as a set of services (daemons) performing
various configuration and management tasks. These services talk to each other
using unified RPC protocol. Services can expose their public interfaces
(RPC server), call other services (RPC client) and broadcast asynchronous
events.

These RPC calls and event notifications are routed using central server called
dispatcher. Dispatcher exposes WebSocket endpoint where middleware clients
(like GUI, CLI or scripts) can connect, issue management commands and listen
for events.

In addition to routing RPC calls and events, dispatcher itself holds actual
"business logic" through plugin interface. Each plugin, contained in single
Python source file, can expose it's RPC interfaces, event sources and
task handlers.