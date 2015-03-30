// Webapp Middleware
// =================
// Handles the lifecycle for the websocket connection to the middleware. This is
// a utility class designed to curate general system data, including user login,
// task and event queues, disconnects, and similar events. Calling action
// creators or passing data to specific "channel" stores is out of scope for
// this class.

"use strict";

var _ = require("lodash");

var SubscriptionsStore          = require("../stores/SubscriptionsStore");
var SubscriptionsActionCreators = require("../actions/SubscriptionsActionCreators");

var MiddlewareStore          = require("../stores/MiddlewareStore");
var MiddlewareActionCreators = require("../actions/MiddlewareActionCreators");

var SessionStore = require("../stores/SessionStore");

var myCookies = require("./cookies");

function MiddlewareClient() {

  var DEBUG = function( flag ) {
    if ( typeof window === "undefined" ) {
      return null;
    } else if ( window.DEBUG_FLAGS && window.DEBUG_FLAGS.MIDDLEWARE_CLIENT_DEBUG ) {
      return window.DEBUG_FLAGS.MIDDLEWARE_CLIENT_DEBUG[ flag ];
    }
  };

  var debugCSS = {
      idColor      : "color: rgb(33, 114, 218);"
    , argsColor    : "color: rgb(215, 110, 20); font-style: italic;"
    , errorColor   : "color: rgb(235, 15, 15);"
    , codeStyle    : "color: rgb(62, 28, 86);"
    , defaultStyle : ""
  };

  var socket          = null;
  var requestTimeout  = 10000;
  var queuedLogin     = null;
  var queuedActions   = [];
  var pendingRequests = {};

// UTILITY FUNCTIONS

  // Generates a unique UUID which a client includes with each call (generally
  // within the `pack` function). This ID may then be used to verify either the
  // original client or for the client to verify the middleware's response.
  function generateUUID () {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace( /[xy]/g, function (c) {
        var r = Math.random() * 16 | 0;
        var v = ( c === "x" ) ? r : ( r & 0x3 | 0x8 );

        return v.toString(16);
      }
    );
  }

  // Creates a JSON-formatted object to send to the middleware. Contains the
  // following key-values:
  // "namespace" : The target middleware namespace. (eg. "rpc", "events")
  // "name"      : Name of middleware action within the namespace (eg.
  //               "subscribe", "auth")
  // "args"      : The arguments to be used by the middleware action (eg. username
  //               and password)
  // "id"        : The unique UUID used to identify the origin and response
  //               If left blank, `generateUUID` will be called. This is a
  //               fallback, and will likely result in a "Spurious reply" error
  function pack ( namespace, name, args, id ) {
    if ( DEBUG("packing") ) {
      var validPack = true;

      if ( typeof namespace !== "string" )             { validPack = false; console.warn( "BAD PACK: Provided namespace was not a string for request %c'" + id + "'%c", debugCSS.idColor, debugCSS.defaultStyle ); }
      if ( typeof name !== "string" )                  { validPack = false; console.warn( "BAD PACK: Provided name was not a string for request %c'" + id + "'%c", debugCSS.idColor, debugCSS.defaultStyle ); }
      if ( typeof args === ( "null" || "undefined" ) ) { validPack = false; console.warn( "BAD PACK: Provided args value was null or undefined for request %c'" + id + "'%c", debugCSS.idColor, debugCSS.defaultStyle ); }
      if ( typeof id !== "string" )                    { validPack = false; console.warn( "BAD PACK: UUID %c'" + id + "'%c for '" + namespace + "'" + ( args ? ":" + args : "" ) + " had to be generated because none was provided", debugCSS.idColor, debugCSS.defaultStyle ); }

      if ( validPack ) {
        console.info( "Packed request %c'" + id + "'%c successfully.", debugCSS.idColor, debugCSS.defaultStyle );
      } else {
        console.log( "Dump of bad pack:", {
                        "namespace" : namespace
                      , "name"      : name
                      , "id"        : id
                      , "args"      : args
                    });
      }
    }

    return JSON.stringify({
        "namespace" : namespace
      , "name"      : name
      , "id"        : id
      , "args"      : args
    });
  }

  // Based on the status of the WebSocket connection and the authentication
  // state, either logs and sends an action, or enqueues it until it can be sent
  function processNewRequest ( packedAction, callback, requestID ) {

    if ( socket.readyState === 1 && SessionStore.getLoginStatus() ) {

      if ( DEBUG("logging") ) { console.info( "Logging and sending request %c'" + requestID + "'", debugCSS.idColor, { requestID : packedAction } ); }

      logPendingRequest( requestID, callback, packedAction );
      socket.send( packedAction );

    } else {

      if ( DEBUG("queues") ) { console.info( "Enqueueing request %c'" + requestID + "'", debugCSS.idColor ); }

      queuedActions.push({
          action   : packedAction
        , id       : requestID
        , callback : callback
      });

    }

  }

  // Many views' lifecycle will make a request before the connection is made,
  // and before the login credentials have been accepted. These requests are
  // enqueued by the `login` and `request` functions into the `queuedActions`
  // object and `queuedLogin`, and then are dequeued by this function.
  function dequeueActions () {

    if ( DEBUG("queues") && queuedActions.length ) { console.log( "Attempting to dequeue actions" ); }

    if ( SessionStore.getLoginStatus() ) {
      while ( queuedActions.length ) {
        var item = queuedActions.shift();

        if ( DEBUG("queues") ) { console.log( "Dequeueing %c'" + item.id + "'", debugCSS.idColor ); }

        processNewRequest( item.action, item.callback, item.id );
      }
    } else if ( DEBUG("queues") && queuedActions.length ) { console.info( "Middleware not authenticated, cannot dequeue actions" ); }
  }

  // Records a middleware request that was sent to the server, stored in the
  // private `pendingRequests` object. These are eventually resolved and
  // removed, either by a response from the server, or the timeout set here.
  function logPendingRequest ( requestID, callback, originalRequest ) {
    var request = {
        callback        : callback
      , originalRequest : originalRequest
      , timeout : setTimeout(
          function() {
            handleTimeout( requestID );
          }, requestTimeout
        )
    };

    pendingRequests[ requestID ] = request;

    if ( DEBUG("logging") ) { console.log ( "Current pending requests:", pendingRequests ); }
  }

  // Resolve a middleware request by clearing its timeout, and optionally
  // calling its callback. Callbacks should not be called if the function timed
  // out before a response was received.
  function resolvePendingRequest ( requestID, args, outcome ) {
    clearTimeout( pendingRequests[ requestID ].timeout );

    switch ( outcome ) {
      case "success":
        if ( DEBUG("messages") ) { console.info( "SUCCESS: Resolving request %c'" + requestID + "'", debugCSS.idColor ); }
        executeRequestCallback( requestID, args );
        break;

      case "error":
        var originalRequest;

        try {
          originalRequest = JSON.parse( pendingRequests[ requestID ]["originalRequest"] );
        } catch ( err ) {
          // Don't care about this, I think
        }

        if ( args.message && _.startsWith( args.message, "Traceback" ) ) {
          console.groupCollapsed( "%cRequest %c'" + requestID + "'%c caused a Python traceback", debugCSS.errorColor, debugCSS.idColor, debugCSS.errorColor );
          if ( originalRequest ) {
            console.groupCollapsed( "Original request" );
            console.log( originalRequest );
            console.groupEnd();
          }
          console.groupCollapsed( "Response data" );
          console.log( args );
          console.groupEnd();
          console.log( "%c" + args.message , debugCSS.codeStyle );
          console.groupEnd();
        } else if ( args.code && args.message ){
          console.groupCollapsed( "%cERROR %s: Request %c'%s'%c returned: %s", debugCSS.errorColor, args.code, debugCSS.idColor, requestID, debugCSS.errorColor, args.message );
          if ( originalRequest ) {
            console.groupCollapsed( "Original request" );
            console.log( originalRequest );
            console.groupEnd();
          }
          console.log( args );
          console.groupEnd();
        } else {
          console.groupCollapsed( "%cERROR: Request %c'" + requestID + "'%c returned with an error status", debugCSS.errorColor, debugCSS.idColor, debugCSS.errorColor );
          if ( originalRequest ) {
            console.groupCollapsed( "Original request" );
            console.log( originalRequest );
            console.groupEnd();
          }
          console.log( args );
          console.groupEnd();
        }
        break;

      case "timeout":
        if ( DEBUG("messages") ) { console.warn( "TIMEOUT: Stopped waiting for request %c'" + requestID + "'", debugCSS.idColor ); }
        break;

      default:
        break;
    }

    delete pendingRequests[ requestID ];
  }

  // Executes the specified request callback with the provided arguments. Should
  // only be used in cases where a response has come from the server, and the
  // status is successful in one way or another. Calling this function when the
  // server returns an error could cause strange results.
  function executeRequestCallback( requestID, args ) {
    if ( typeof pendingRequests[ requestID ].callback === "function" ) {
      pendingRequests[ requestID ].callback( args );
    }
  }


// LIFECYCLE FUNCTIONS
// Public methods used to manage the middleware's connection and authentication

  // This method should only be called when there's no existing connection. If for
  // some reason, the existing connection should be ignored and overridden, supply
  // `true` as the `force` parameter.
  this.connect = function ( url, force ) {
    if ( window.WebSocket ) {
      if ( !socket || force ) {

        if ( DEBUG("connection") ) { console.info( "Creating WebSocket instance" ); }
        if ( DEBUG("connection") && force ) { console.warn( "Forcing creation of new WebSocket instance" ); }

        socket = new WebSocket( url );
        socket.onmessage = handleMessage;
        socket.onopen    = handleOpen;
        socket.onerror   = handleError;
        socket.onclose   = handleClose;
      } else if ( DEBUG("connection") ) {
        console.warn( "Attempted to create a new middleware connection while a connection already exists." );
      }
    } else if ( DEBUG("connection") ) {
      console.error( "This browser doesn't support WebSockets." );
      // TODO: Visual error for legacy browsers with links to download others
    }
  };

  // Shortcut method for closing the WebSocket connection. Will also trigger
  // `handleClose` for any cleanup that needs to happen.
  this.disconnect = function ( code, reason ) {
    socket.close( code, reason );
  };

  // Authenticate a user to the middleware. Basically a specialized version of
  // the `request` function with a different payload.
  this.login = function ( auth_type, credentials ) {
    var requestID = generateUUID();
    var rpcName = "auth";
    var payload = {};
    if (auth_type === "userpass") {
      payload = {
          "username" : credentials[0]
        , "password" : credentials[1]
      };
    } else if (auth_type === "token") {
      payload = {
          "token" : credentials
      };
      rpcName = rpcName + "_token";
    }

    var callback = function( response ) {
      // Making a Cookie for token based login for the next time
      // and setting its max-age to the TTL (in seconds) specified by the
      // middleware response. The token value is stored in the Cookie.
      myCookies.add("auth", response[0], response[1]);

      // TODO: Account for any other possible response codes.
      if (response.code === 13){
        MiddlewareActionCreators.receiveAuthenticationChange( "", false );
      } else {
        MiddlewareActionCreators.receiveAuthenticationChange( response[2], true );
      }
    };
    var packedAction = pack( "rpc", rpcName, payload, requestID );

    if ( socket.readyState === 1 ) {

      if ( DEBUG("authentication") ) { console.info( "Socket is ready: Sending login request." ); }

      logPendingRequest( requestID, callback, packedAction );
      socket.send( packedAction );

    } else {

      if ( DEBUG("authentication") ) { console.info( "Socket is NOT ready: Deferring login request." ); }

      queuedLogin = {
          action   : packedAction
        , callback : callback
        , id       : requestID
      };
    }

  };

  this.logout = function () {

    // TODO: Allow logout functionality

  };


// CHANNELS AND REQUESTS

  // Make a request to the middleware, which translates to an RPC call. A
  // unique UUID is generated for each request, and is supplied to
  // `logPendingRequest` as a lookup key for resolving or timing out the
  // request.
  this.request = function ( method, args, callback ) {
    var requestID = generateUUID();
    var payload = {
        "method" : method
      , "args"   : args
    };
    var packedAction = pack( "rpc", "call", payload, requestID );

    processNewRequest( packedAction, callback, requestID );
  };

  // SUBSCRIPTION INTERFACES
  // Generic interface for subscribing to Middleware namespaces. The Middleware
  // Flux store records the number of React components which have required a
  // subscription to a Middleware namespace. This allows the Middleware Client
  // to make intelligent decisions about whether to query a namespace for fresh
  // data, begin or end a subscription, or even garbage collect a Flux store which
  // is no longer being used.

  this.subscribe = function ( masks, componentID ) {

    if ( !_.isArray( masks ) ) {
      console.error( "The first argument in MiddlewareClient.subscribe() must be an array of FreeNAS RPC namespaces." );
      return;
    }

    if ( !_.isString( componentID ) ) {
      console.error( "The second argument in MiddlewareClient.subscribe() must be a string (usually the name of the React component calling it)." );
      return;
    }

    if ( DEBUG("subscriptions") ) { console.log( "Requested: Subscribe to %c'" + ( masks.length > 1 ? masks.splice( masks.length - 1, 0, " and " ).join( ", " ) : masks ) + "'%c events", debugCSS.argsColor, debugCSS.defaultStyle ); }

    _.forEach( masks, function( mask ) {
      if ( SubscriptionsStore.getNumberOfSubscriptionsForMask( mask ) > 0 ) {
        if ( DEBUG("subscriptions") ) { console.info( SubscriptionsStore.getNumberOfSubscriptionsForMask( mask ) + " React components are currently subscribed to %c'" + mask + "'%c events", debugCSS.argsColor, debugCSS.defaultStyle ); }
        if ( DEBUG("subscriptions") ) { console.log( "Increasing subscription count for %c'" + mask + "'", debugCSS.argsColor ); }
      } else {
        if ( DEBUG("subscriptions") ) { console.info( "No React components are currently subscribed to %c'" + mask + "'%c events", debugCSS.argsColor, debugCSS.defaultStyle ); }
        if ( DEBUG("subscriptions") ) { console.log( "Sending subscription request, and setting subscription count for %c'" + mask + "'%c to 1", debugCSS.argsColor, debugCSS.defaultStyle ); }
        var requestID = generateUUID();
        processNewRequest( pack( "events", "subscribe", [ mask ], requestID ), null, requestID );
      }
    });

    SubscriptionsActionCreators.recordNewSubscriptions( masks, componentID );
  };

  this.unsubscribe = function ( masks, componentID ) {

    if ( !_.isArray( masks ) ) {
      console.warn( "The first argument in MiddlewareClient.unsubscribe() must be an array of FreeNAS RPC namespaces." );
      return;
    }

    if ( !_.isString( componentID ) ) {
      console.warn( "The second argument in MiddlewareClient.unsubscribe() must be a string (usually the name of the React component calling it)." );
      return;
    }

    if ( DEBUG("subscriptions") ) { console.log( "Requested: Unsubscribe to %c'" + ( masks.length > 1 ? masks.splice( masks.length - 1, 0, " and " ).join( ", " ) : masks ) + "'%c events", debugCSS.argsColor, debugCSS.defaultStyle ); }

    _.forEach( masks, function( mask ) {
      if ( SubscriptionsStore.getNumberOfSubscriptionsForMask( mask ) === 1 ) {
        if ( DEBUG("subscriptions") ) { console.info( "Only one React component is currently subscribed to %c'" + mask + "'%c events, so the subscription will be removed", debugCSS.argsColor, debugCSS.defaultStyle ); }
        if ( DEBUG("subscriptions") ) { console.log( "Sending unsubscribe request, and deleting subscription count entry for %c'" + mask + "'", debugCSS.argsColor ); }
        var requestID = generateUUID();
        processNewRequest( pack( "events", "unsubscribe", [ mask ], requestID ), null, requestID );
      } else {
        if ( DEBUG("subscriptions") ) { console.info( SubscriptionsStore.getNumberOfSubscriptionsForMask( mask ) + " React components are currently subscribed to %c'" + mask + "'%c events, and one will be unsubscribed", debugCSS.argsColor, debugCSS.defaultStyle ); }
        if ( DEBUG("subscriptions") ) { console.log( "Decreasing subscription count for %c'" + mask + "'", debugCSS.argsColor ); }
      }
    });

    SubscriptionsActionCreators.deleteCurrentSubscriptions( masks, componentID );
  };


// MIDDLEWARE DISCOVERY METHODS
// These are public methods used to gather more information about the Middleware's
// capabilities and overall state. These can be used to return a list of services
// supported by your connection to the middleware, and methods supported by each
// service. (These are helpful wrappers more than core functionality.)

  this.getServices = function() {
    this.request( "discovery.get_services", [], function( services ) {
      MiddlewareActionCreators.receiveAvailableServices( services );
    });
  };

  this.getMethods = function( service ) {
    this.request( "discovery.get_methods", [ service ], function( methods ) {
      MiddlewareActionCreators.receiveAvailableServiceMethods( service, methods );
    });
  };


// SOCKET DATA HANDLERS
// Private methods for handling data from the WebSocket connection

  // Triggered by the WebSocket's onopen event.
  var handleOpen = function () {
    if ( SessionStore.getLoginStatus() === false && queuedLogin ) {
      // If the connection opens and we aren't authenticated, but we have a
      // queued login, dispatch the login and reset its variable.
      if ( DEBUG("queues") ) { console.info( "Resolving queued login %c" + queuedLogin.id, debugCSS.idColor ); }
      if ( DEBUG("queues") ) { console.log({ requestID : queuedLogin.action }); }

      logPendingRequest( queuedLogin.id, queuedLogin.callback );
      socket.send( queuedLogin.action );
      queuedLogin = null;
    }
  };

  // Triggered by the WebSocket's onclose event. Performs any cleanup necessary
  // to allow for a clean session end and prepares for a new session.
  var handleClose = function () {
    socket          = null;
    queuedLogin     = {};
    queuedActions   = [];

    if ( DEBUG("connection") ) { console.warn( "WebSocket connection closed" ); }

    // TODO: restart connection if it unexpectedly closed

  };

  // MESSAGES
  // Triggered by the WebSocket's onmessage event. Parses the JSON from the
  // middleware's response, and then performs followup tasks depending on the
  // message's namespace.
  var handleMessage = function ( message ) {
    var data = JSON.parse( message.data );

    if ( DEBUG("messages") ) { console.log( "Message from Middleware:", data.namespace, message ); }

    switch ( data.namespace ) {

      // A FreeNAS event has occurred
      case "events":
        if ( DEBUG("messages") ) { console.log( "Message contained event data" ); }
        MiddlewareActionCreators.receiveEventData( data );
        break;

      // An RPC call is returning a response
      case "rpc":
        switch ( data.name ) {
          case "response":
            resolvePendingRequest( data.id, data.args, "success" );
            break;

          case "error":
            resolvePendingRequest( data.id, data.args, "error" );
            break;

          default:
            console.warn( "Was sent an rpc message from middleware, the client was unable to identify its purpose:" );
            console.log( message );
            break;
        }
        break;

      // There was an error with a request or with its execution on FreeNAS
      case "error":
        if ( DEBUG("messages") ) { console.error( "Middleware has indicated an error:", data.args ); }
        break;

      // A reply was sent from the middleware with no recognizable namespace
      // This shouldn't happen, and probably indicates a problem with the
      // middleware itself.
      default:
        if ( DEBUG("messages") ) { console.warn( "Spurious reply from Middleware:", message ); }
        // Do nothing
    }
  };

  // CONNECTION ERRORS
  // Triggered by the WebSocket's `onerror` event. Handles errors with the client
  // connection to the middleware.
  var handleError = function ( error ) {
    if ( DEBUG("connection") ) { console.error( "The WebSocket connection to the Middleware encountered an error:", error ); }
  };

  // REQUEST TIMEOUTS
  // Called by a request function without a matching response. Automatically
  // triggers resolution of the request with a "timeout" status.
  var handleTimeout = function ( requestID ) {

    if ( DEBUG("messages") ) { console.warn( "Request %c'" + requestID + "'%c timed out without a response from the middleware", debugCSS.idColor, debugCSS.defaultStyle ); }

    resolvePendingRequest( requestID, null, "timeout" );
  };

  // On a successful login, dequeue any actions which may have been requested
  // either before the connection was made, or before the authentication was
  // complete.
  SessionStore.addChangeListener( dequeueActions );

  // The comment above would have us believe that this listener is just
  // for login happening, which would indicate that the following is not needed.
  // This is just a precaution in case there are hidden assumptions there.
  MiddlewareStore.addChangeListener( dequeueActions );

}

module.exports = new MiddlewareClient();
