Understanding the Flux Application Architecture
===============================================


![A high level data flow diagram for FreeNAS 10's UI](images/architecture/flux/freenas_flux.png)


## Flux and FreeNAS 10
The FreeNAS 10 UI is based on [Facebook's React](http://facebook.github.io/react/), a declarative front-end view framework. Because of this, FreeNAS' UI shares many of the same conventions as a standard React application does.

Flux is more of an architectural model than it is a framework. While it does include a Dispatcher module, Flux is primarily focused on enforcing unidirectional data flow, and accomplishes this through strict separation of concerns.

React does not depend on Flux, and vice versa, but between the two ideologies, it's very easy to create a highly composible, declarative UI, with straightforward data flow and clear delegation of responsibilities.


## Flux-Specific Terminology
Some of the terminology Flux employs may be unfamiliar, and it can be difficult to identify various UI modules and understand their relationships without first building the correct vocabulary.

### Flux Store
![Flux Store](images/architecture/flux/store.png)
A Flux store is, at its core, a simple JavaScript object. Stores are exported as singletons, so each store is both a single instance and globally accessible by any other module or view. Stores additionally function as event emitters, and allow views to "subscribe" to the store's "change" event, and register a callback to be run when the store is updated.

```JavaScript

      emitChange: function() {
        this.emit( CHANGE_EVENT );
      }

    , addChangeListener: function( callback ) {
        this.on( CHANGE_EVENT, callback );
      }

    , removeChangeListener: function( callback ) {
        this.removeListener( CHANGE_EVENT, callback );
      }
```

In this way, data upkeep and processing tasks are abstracted out of the view, and the view can rely on always having up-to-date data provided automatically by the store.

Stores also tend to have utility functions for retrieving specific data.

```JavaScript

    // Return a specific user
      getUser: function( key ) {
        return _users[ key ];
      }

    // Return all users
    , getAllUsers: function() {
        return _users;
      }
```

Another unique function of stores is the ability to act syncronously, and delay an update until another store has completed updating. Because each store registers a dispatchToken with the Dispatcher, it's a trivial matter to wait for another store to finish updating, then update the target.

```JavaScript

    case ActionTypes.UPDATE_USERS:

      // waitFor will prevent the user update from occurring until GroupsStore
      // is guaranteed to have updated

      FreeNASDispatcher.waitFor([GroupsStore.dispatchToken]);

      // GroupsStore has been updated, so now we can proceed

      _users = action.rawUsers;
      UsersStore.emitChange();
      break;

```

### Flux Dispatcher
![Flux Dispatcher](images/architecture/flux/dispatcher.png)
The Dispatcher broadcasts payloads to registered callbacks. Essentially, a store will register with the Dispatcher, indicating that it wants to run a callback when the Dispatcher broadcasts data of a certain "action type".

Callbacks are not subscribed to particular events. Each payload is dispatched to all registered callbacks, and it's up to the callback to triage the action type, and decide whether to act.

```JavaScript

    var FreeNASDispatcher = _.assign( new Dispatcher(), {

        handleMiddlewareAction: function( action ) {
          var payload = {
              source : PayloadSources.MIDDLEWARE_ACTION
            , action : action
          };

          this.dispatch( payload );
        }

    });

```

### Action Creators
![Action Creators](images/architecture/flux/actioncreator.png)
Action Creators aren't provided or created by Flux, but they are a necessary abstraction when piping multiple data streams into the same Dispatcher.

Action Creators are simple classes which provide interfaces into more complex Dispatcher functionality. An Action Creator will take input, either from an external resource or a user interaction, and package it for the dispatcher.

While conceptually simple, an Action Creator class is an easy way to segment similar functionality, and route all similar actions through the same Dispatcher function.

In the example below, the Middleware client receieves a list of users, packages them for the handleMiddlewareAction function in FreeNASDispatcher.

```JavaScript

    receiveUsersList: function( rawUsers ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type     : ActionTypes.RECEIVE_RAW_USERS
        , rawUsers : rawUsers
      });
    }

```

The handleMiddlewareAction function then tags the payload with the appropriate source, and dispatches it to all registered callbacks.

```JavaScript

    handleMiddlewareAction: function( action ) {
      var payload = {
          source : PayloadSources.MIDDLEWARE_ACTION
        , action : action
      };

      this.dispatch( payload );
    }

```

While this may seem like redundant separation of concerns, and a lot of overhead for little gain, the increase in complexity is negligible compared to the easily traceable path data takes through the FreeNAS UI. This also allows for simpler debugging, and creates a more extensible and composible platform than just calling `FreeNASDispatcher.dispatch()` directly would.


## FreeNAS 10 UI-Specific Terminology
In addition to the standard Flux language, there are also some terms which are more specific to FreeNAS' application of the architecture.

### Middleware Utility Class
![Middleware Utility Class](images/architecture/flux/utility_class.png)
The Middleware Utility Class is unique to FreeNAS 10. It provides an interface between the React View, the Middleware Client, and the Action Creators. When a user interacts with the FreeNAS 10 UI in a way that will require the Middleware Server to provide new data, the action is handled my the Middleware Utility Class, which calls the Middleware Client's `request()` method with a callback for the appropriate Action Creator.

```JavaScript

    requestUsersList: function() {
      MiddlewareClient.request( "accounts.query_users", null, function ( rawUsersList ) {
        UsersActionCreators.receiveUsersList( rawUsersList );
      });
    }

```

This allows the system to remain fully asyncronous, as the Middleware Client is able to handle its own callbacks, and the stores are independent of the views. Even if a user navigates to another view (which has no relationship with the previous store), the Middleware Client will recieve data from the Middleware Server, call the Action Creator, and the data will be dispatched to the appropriate store, completely asyncronously.

In this way, the architecture ensures that no replies are regarded as spurious by views which should have no knowledge of them, and the entire application maintains consistent state.

### Middleware Client
![Middleware Client](images/architecture/flux/middleware_client.png)
The FreeNAS 10 UI uses a fully asyncronous WebSocket connection for communication with the hardware backend. The [Middleware Client](../app/jsx/middleware/MiddlewareClient.js) is a simple WebSocket client which handles the connection lifecycle, as well as the packaging, identification, transmission, and (initial) receipt of data.

It exposes public methods for connecting/disconnecting, logging in/out, subscribing/unsubscribing from event types, and making specific requests.

The Middleware Client should not be accessed directly from a view. Rather, it should have a Middleware Utility Class set up to handle the interface, with an appropriate set of Action Creators ready to handle the data returned.

### Middleware Server
![Middleware Server](images/architecture/flux/middleware_server.png)
The Middleware Server is a WebSocket server running on the same hardware as the core FreeNAS 10 OS. It collects and disburses system data requested by a Middleware Client.

### FreeNAS 10 Base OS
![FreeNAS 10 Base OS](images/architecture/flux/freenas10_base.png)
The core operating system. Out of scope for any UI work, and shown in the above diagram only to describe its exact relationship to the rest of the system.