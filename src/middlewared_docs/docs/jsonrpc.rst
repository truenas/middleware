JSON-RPC 2.0 over WebSocket API
===============================

Overview
--------

The TrueNAS API implements the `JSON-RPC 2.0 <https://www.jsonrpc.org/specification>`_ protocol over WebSocket for
communication between clients and the TrueNAS server. This allows
real-time interaction, including method calls and event notifications.

JSON-RPC 2.0 Protocol
---------------------

Communication Mechanism
~~~~~~~~~~~~~~~~~~~~~~~

-  Messages are exchanged using the **WebSocket protocol**.
-  The client initiates a WebSocket connection to the TrueNAS API
   endpoint.
-  The API follows the `JSON-RPC 2.0 <https://www.jsonrpc.org/specification>`_ specification for
   request-response messaging.

Request and Response Format
---------------------------

JSON-RPC Request Structure
~~~~~~~~~~~~~~~~~~~~~~~~~~

A typical **method call** request from the client to TrueNAS follows
this structure:

.. code:: json

   {
     "jsonrpc": "2.0",
     "id": 1,
     "method": "<method_name>",
     "params": [<parameters>]
   }

Example Request:
^^^^^^^^^^^^^^^^

Calling the ``system.info`` method:

.. code:: json

   {
     "jsonrpc": "2.0",
     "id": 1,
     "method": "system.info",
     "params": []
   }

JSON-RPC Response Structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The TrueNAS API will respond with a standard JSON-RPC response:

.. code:: json

   {
     "jsonrpc": "2.0",
     "id": 1,
     "result": {<result_data>}
   }

Example Response:
^^^^^^^^^^^^^^^^^

.. code:: json

   {
     "jsonrpc": "2.0",
     "id": 1,
     "result": {
       "version": "TrueNAS-25.04",
       "uptime": "15 days"
     }
   }

Error Response
~~~~~~~~~~~~~~

If an error occurs, the response format is:

.. code:: json

   {
     "jsonrpc": "2.0",
     "id": 1,
     "error": {
       "code": -32001,
       "message": "method call error",
       "data": {<error_details>}
     }
   }

Custom Error Codes
^^^^^^^^^^^^^^^^^^

+---------------+-------------------------------------+----------------+
| Error Code    | Message                             | Description    |
+===============+=====================================+================+
| -32000        | “too many concurrent calls”         | The client has |
|               |                                     | exceeded the   |
|               |                                     | allowed        |
|               |                                     | concurrent     |
|               |                                     | requests.      |
+---------------+-------------------------------------+----------------+
| -32001        | “method call error”                 | There was an   |
|               |                                     | error          |
|               |                                     | executing the  |
|               |                                     | requested      |
|               |                                     | method.        |
+---------------+-------------------------------------+----------------+

Event Notifications
-------------------

If the server needs to notify a connected client of an event, it sends a
**JSON-RPC Notification** message with the ``collection_update`` method.

JSON-RPC Notification Structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: json

   {
     "jsonrpc": "2.0",
     "method": "collection_update",
     "params": [<update_data>]
   }

Example Notification:
^^^^^^^^^^^^^^^^^^^^^

.. code:: json

   {
     "jsonrpc": "2.0",
     "method": "collection_update",
     "params": {
       "collection": "disk.query",
       "event": "CHANGED",
       "fields": {
         "name": "sda",
         "status": "HEALTHY"
       }
     }
   }

Important Notes on Notifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  **No Response Required**: These notifications do not require a
   response from the client.
-  **Event-Driven**: Notifications are used for updates such as status
   changes, new log entries, or alerts.

Limitations
-----------

-  **Batch Requests Are Not Supported**: Each request must be sent
   individually; batch calls are not allowed.
-  **Error Handling**: Custom error codes are provided for handling
   specific issues.
