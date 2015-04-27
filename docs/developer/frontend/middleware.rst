.. highlight:: javascript
   :linenothreshold: 5

.. _Middleware Client:

Middleware Client
=================

Middleware Channels
-------------------

A key aspect of the FreeNAS 10 Middleware is its use of discrete
"channels" for different information. A more traditional web application
model might make use of asyncronous AJAX requests with different
callbacks, depending on the status of an operation.

FreeNAS 10 uses a persistent WebSocket connection with multiple
concurrent "subscriptions", and routes the resulting data through the
Flux dispatcher into session-persistent data stores. This is significant
for a few reasons:

1. Rather than requesting specific data, the FreeNAS 10 UI is able to
   request an initial payload of data when subscribing to a "channel",
   and will then receive subsequent patch updates as they become
   available.

2. Views are wholly uncoupled from the Middleware Client, and instead
   subscribe to Flux stores. When the contents of the store are
   modified, the view (if open) will automatically update its own
   internal state with the new data, and perform any necessary
   processing or re-rendering.

3. Because of this granular subscription model, and because views access
   persistent stores, rather than requesting information when they open
   and garbage collecting it when they close, views are highly
   performant, and the architecture avoids a "firehose" design, where
   all new information is constantly streamed to the UI. A handy side
   effect is that any view which requires data from an
   already-initialized store will load with the current contents of that
   store, and its initial setup operation will be an update, rather than
   a initialization.

More information on the technical aspects of this architecture is
available in `"Understanding the Flux Application
Architecture" <flux.md>`__.

.. _Public Facing Middleware Client Functions:

Public-Facing Middleware Client Functions
-----------------------------------------

These are the Middleware Client functions that are intended to be consumed by
other parts of the FreeNAS 10 webapp.

* :ref:`connect`: Establish a connection to the FreeNAS server.

* :ref:`disconnect`: Sever a connection with the FreeNAS server.

* :ref:`login`: Authenticate a user with the FreeNAS server.

* :ref:`logout`: Not implemented, and may be combined with ``disconnect`` in the future.

* :ref:`request`: Sumbit an RPC call to the FreeNAS server.

* :ref:`subscribe`: Subscribe a component to one or more event masks.

* :ref:`unsubscribe`: Unsubscribe a component from one or more event masks.

* :ref:`renewSubscriptions`: Renew all subscriptions known to the FreeNAS webapp.

* :ref:`unsubscribeAll`: Remove all subscriptions known to the FreeNAS webapp.

* :ref:`getServices`: Populate a list of all the services available from the FreeNAS server.

* :ref:`getMethods`: Populate a list of all the methods available from a given service.

.. _connect:

connect
~~~~~~~

``MiddlewareClient.connect( url, force )``

``connect`` attempts to open a connection to the FreeNAS server. It creates a WebSocket
with the following eventListeners:

* ``onmessage``: ``MiddlewareClient.handleMessage``: Parses the JSON from the response
  and performs followup tasks as appropriate based on the namespace and error
  status of the response.

* ``onopen``: ``MiddlewareClient.handleOpen``: Checks auth status and automatically logs
  back in if possible. Renews all subscriptions. If successfully logged in, attempts
  to re-submit any queued tasks.

* ``onerror``: ``MiddlewareClient.handleError``: Logs the error to the console.

* ``onclose``: ``MiddlewareClient.onclose``: Logs the user out. Begins a loop preparing
  for a new connection.

``connect`` should be called with the following arguments:

* ``url`` - a string representing the url of the freenas server.

* ``force`` - a boolean. If ``true`` is submitted, a connection attempt will be made
  even if there is an existing connection.

.. _disconnect:

disconnect
~~~~~~~~~~

``disconnect( code, reason )``

``disconnect`` closes the connection with the FreeNAS server.

.. note:: This function is not yet ready for use.

.. _login:

login
~~~~~

``login( auth_type, credentials )``

``login`` attempts to authenticate a user with the FreeNAS server. The callback
it submits to the server creates a cookie to allow automatic login. Upon success,
it calls ``MiddlewareClient.receiveAuthenticationChange`` with the username of the
logged-in and ``true`` to represent a successful login. If the login fails,
``resolvePendingRequest``, an internal function, will instead detect the error code
and submit a call to `MiddlewareClient.receiveAuthenticationChange`` with "" as the
username and ``false`` as the login state.

* ``auth_type`` - a string representing a valid authentication type, either "token" or "userpass".

* ``credentials`` - credentials appropriate to the type of authentication being submitted.
  For userpass, it's an array containing two strings: the username and the password.

.. warning:: At this time the password is sent in plain text over an unencrypted connection.

.. _logout:

logout
~~~~~~

.. note:: logout functionality is not implemented as of this writing. This function may or may not exist in the future.

.. _request:

request
~~~~~~~

``request( method, args, successCallback, errorCallback )``

``request`` sends an RPC call to the FreeNAS Server.

* ``method`` - a string representing the name of an extant middleware method.
  The available methods are documented at [FreeNAS Appliance IP]:8180/apidoc/rpc.

* ``args`` - the desired array of args to be submitted with the call.

* ``successCallback`` - the function which should be executed if the call is
  successful. successCallback will be called with TODO: DETERMINE EXACT ARGS.

* ``failureCallback`` - the function which should be executed if the call
  fails. failureCallback will be called with TODO: DETERMINE EXACT ARGS.

.. note:: errorCallback behavior is not yet implemented.

.. _subscribe:

subscribe
~~~~~~~~~

``subscribe( masks, componentID )``

``subscribe`` registers a subscription to one or more event masks for a React component.

* ``masks`` - an array of strings, each representing a valid event mask. Event masks
  can be specific events (like "users.changed"), or entire namespaces
  (like "system.*"). Leading and trailing spaces should not be included. The list of
  namespaces and events is available at [FreeNAS Appliance IP]:8180/apidoc/events.

* ``componentID`` - the unique string representing the component that should be
  subscribed.

.. note:: The events are not fully documented at this time.

.. _unsubscribe:

unsubscribe
~~~~~~~~~~~

``unsubscribe( masks, componentID )``

``unsubscribe`` removes the subscriptions to the supplied masks for the supplied
component.

* ``masks`` - an array of strings, each representing an event mask to which the
  component is subscribed.

* ``componentID`` - the unique string representing the component that should be
  unsubscribed.

.. _renewSubscriptions:

renewSubscriptions
~~~~~~~~~~~~~~~~~~

``renewSubscriptions()``

``renewSubscriptions`` re-submits all subscriptions known to the FreeNAS Webapp.
Intended for debugging and reconnection purposes.

.. _unsubscribeAll:

unsubscribeAll
~~~~~~~~~~~~~~

``unsubscribeAll()``

``unsubscribeAll`` removes all subscriptions known to the FreeNAS WebApp. Intended
for debugging and disconnection purposes.

.. _getServices:

getServices
~~~~~~~~~~~

``getServices()``

``getServices`` populates the list of all available services for the FreeNAS WebApp.
Intended for use at first connection and in case services have changed, such as after
a software update.

.. _getMethods:

getMethods
~~~~~~~~~~

``getMethods( service )``

``getMethods`` populates the list of methods available from a given service.

* ``service`` - a string representing a service known to the FreeNAS webapp
