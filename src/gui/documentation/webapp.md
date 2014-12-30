FreeNAS 10 WebApp Architecture
==============================

![A stacked diagram representing the FreeNAS 10 UI's "layers"](images/architecture/freenas_webapp.png)

## Middleware Channels
A key aspect of the FreeNAS 10 Middleware is its use of discrete "channels" for different information. A more traditional web application model might make use of asyncronous AJAX requests with different callbacks, depending on the status of an operation.

FreeNAS 10 uses a persistent WebSocket connection with multiple concurrent "subscriptions", and routes the resulting data through the Flux dispatcher into session-persistent data stores. This is significant for a few reasons:

1. Rather than requesting specific data, the FreeNAS 10 UI is able to request an initial payload of data when subscribing to a "channel", and will then receive subsequent patch updates as they become available.

2. Views are wholly uncoupled from the Middleware Client, and instead subscribe to Flux stores. When the contents of the store are modified, the view (if open) will automatically update its own internal state with the new data, and perform any necessary processing or re-rendering.

3. Because of this granular subscription model, and because views access persistent stores, rather than requesting information when they open and garbage collecting it when they close, views are highly performant, and the architecture avoids a "firehose" design, where all new information is constantly streamed to the UI. A handy side effect is that any view which requires data from an already-initialized store will load with the current contents of that store, and its initial setup operation will be an update, rather than a initialization.

More information on the technical aspects of this architecture is available in ["Understanding the Flux Application Architecture"](flux.md).


## Layers of the UI
The FreeNAS 10 UI is divided into layers, which map well to Middleware channels. In simplest terms, the "wrapper" (persistent toolbars, titlebar, footer) subscribes to general system information (authentication status, events, alerts, uptime, hostname, etc), and then each view will subscribe to a specific and more detailed stream of information (users, network interfaces, volumes) for the duration of its open state, and unsubscribe/garbage collect before unmounting.

This creates a modular and highly composible UI, where individual views and layers are only responsble for subscribing to the Flux store from which they want to receive data, and indicating to the Middleware Client that it should alter a subscription state. It enforces a rigid separation of concerns for data handling as well as conceptually disparate areas of the system.

### Main Mount
The Main Mount is rendered directly into `<body>`, and all other components are descended from it. It is represented by `routes.js`, which handles the client-side routing, including the `FreeNASWebApp` component. `FreeNASWebApp` is the functional "shoebox" wrapper for the application, and subscribes to the general system information channel. It handles authentication, and subscribes to events, alerts, and other notifications.

Each nested route is rendered within its parent, enforcing a strict visual and architectural heirarchy.

### Modal Windows
(TBD)

### Notification Bar
The persistent titlebar in the FreeNAS 10 UI also functions as a kind of notification center, handling the events, alerts, and notifications passed into it from the Main Mount's system-general subscription.

### Navigation
(TBD)

### The Primary View
(TBD)

### Widgets
(TBD)

### Footer and Logs
(TBD)
