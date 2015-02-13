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
