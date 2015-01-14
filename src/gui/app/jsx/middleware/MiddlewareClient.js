// Webapp Middleware
// =================
// Handles the lifecycle for the websocket connection to the middleware. This is
// a utility class designed to curate general system data, including user login,
// task and event queues, disconnects, and similar events. Calling action
// creators or passing data to specific "channel" stores is out of scope for
// this class.

"use strict";

var _ = require("lodash");

var MiddlewareStore          = require("../stores/MiddlewareStore");
var MiddlewareActionCreators = require("../actions/MiddlewareActionCreators");


function MiddlewareClient() {

  // Change DEBUG to `true` to activate verbose console messages
  var DEBUG = false;

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
    if ( typeof id !== "string" ) {
      id = generateUUID();
    }

    return JSON.stringify({
        "namespace" : namespace
      , "id"        : id
      , "name"      : name
      , "args"      : args
    });
  }

  // Sends a packed request to the middleware, while storing its
  function logAndSend ( packedAction, callback, requestID ) {

    if ( DEBUG ) { console.info( "Logging and sending request " + requestID ); }
    if ( DEBUG ) { console.log({ requestID : packedAction }); }

    logPendingRequest( requestID, callback );
    socket.send( packedAction );
  }

  function enqueueAction ( packedAction, callback, requestID ) {

    if ( DEBUG ) { console.info( "Enqueueing request " + requestID ); }

    queuedActions.push({
        action   : packedAction
      , id       : requestID
      , callback : callback
    });
  }

  // Many views' lifecycle will make a request before the connection is made,
  // and before the login credentials have been accepted. These requests are
  // enqueued by the `login` and `request` functions into the `queuedActions`
  // object and `queuedLogin`, and then are dequeued by this function.
  function dequeueActions () {

    if ( DEBUG && queuedActions.length ) { console.info( "Dequeueing actions" ); }

    if ( MiddlewareStore.getAuthStatus() ) {
      while ( queuedActions.length ) {
        var item = queuedActions.shift();

        if ( DEBUG ) { console.info( "Dequeueing " + item.id ); }

        logAndSend( item.action, item.callback, item.id );
      }
    }
  }

  // Records a middleware request that was sent to the server, stored in the
  // private `pendingRequests` object. These are eventually resolved and
  // removed, either by a response from the server, or the timeout set here.
  function logPendingRequest ( requestID, callback ) {
    var request = {
        "callback" : callback
      , "timeout"  : setTimeout(
                       function() {
                         handleTimeout( requestID );
                       }, requestTimeout
                     )
    };

    pendingRequests[ requestID ] = request;
  }

  // Resolve a middleware request by clearing its timeout, and optionally
  // calling its callback. Callbacks should not be called if the function timed
  // out before a response was received.
  function resolvePendingRequest ( requestID, args, outcome ) {
    clearTimeout( pendingRequests[ requestID ].timeout );

    if ( DEBUG && outcome === "success" ) { console.info( "SUCCESS: Resolving request " + requestID ); }
    if ( DEBUG && outcome === "timeout" ) { console.warn( "TIMEOUT: Resolving request " + requestID ); }

    if ( outcome === "success" && pendingRequests[ requestID ].callback ) {
      pendingRequests[ requestID ].callback( args );
    }

    delete pendingRequests[ requestID ];
  }


// LIFECYCLE FUNCTIONS
// Public methods used to manage the middleware's connection and authentication

  // This method should only be called when there's no existing connection. If for
  // some reason, the existing connection should be ignored and overridden, supply
  // `true` as the `force` parameter.
  this.connect = function ( url, force ) {
    if ( window.WebSocket ) {
      if ( !socket || force ) {

        if ( DEBUG ) { console.info( "Creating WebSocket instance" ); }
        if ( DEBUG && force ) { console.warn( "Forcing creation of new WebSocket instance" ); }

        socket = new WebSocket( url );
        socket.onmessage = handleMessage;
        socket.onopen    = handleOpen;
        socket.onerror   = handleError;
        socket.onclose   = handleClose;
      } else if ( DEBUG ) {
        console.warn( "Attempted to create a new middleware connection while a connection already exists." );
      }
    } else if ( DEBUG ) {
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
  this.login = function ( username, password ) {
    var requestID = generateUUID();
    var payload = {
        "username" : username
      , "password" : password
    };
    var callback = function() {
      MiddlewareActionCreators.receiveAuthenticationChange( true );
    };
    var packedAction = pack( "rpc", "auth", payload, requestID );

    if ( socket.readyState === 1 ) {

      if ( DEBUG ) { console.info( "Socket is ready: Sending login request." ); }

      logAndSend( packedAction, callback, requestID );
    } else {

      if ( DEBUG ) { console.info( "Socket is NOT ready: Deferring login request." ); }

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

    if ( socket.readyState === 1 && MiddlewareStore.getAuthStatus() ) {
      logAndSend( packedAction, callback, requestID );
    } else {
      enqueueAction( packedAction, callback, requestID );
    }

  };

  this.subscribe = function ( namespace, masks ) {

    // TODO: Indicate event to action creator

    socket.send( pack( namespace, "subscribe", masks ) );
  };

  this.unsubscribe = function ( namespace, masks ) {

    // TODO: Indicate event to action creator

    socket.send( pack( namespace, "unsubscribe", masks ) );
  };


// SOCKET DATA HANDLERS
// Private methods for handling data from the WebSocket connection

  // Triggered by the WebSocket's onopen event.
  var handleOpen = function () {
    if ( MiddlewareStore.getAuthStatus() === false && queuedLogin ) {
    // If the connection opens and we aren't authenticated, but we have a
    // queued login, dispatch the login and reset its variable.
      logAndSend(
          queuedLogin.action
        , queuedLogin.callback
        , queuedLogin.id
      );
      queuedLogin = null;
    }
  };

  // Triggered by the WebSocket's onclose event. Performs any cleanup necessary
  // to allow for a clean session end and prepares for a new session.
  var handleClose = function () {
    socket          = null;
    queuedLogin     = {};
    queuedActions   = [];
    pendingRequests = {};

    // TODO: restart connection if it unexpectedly closed

  };

  // Triggered by the WebSocket's onmessage event. Parses the JSON from the
  // middleware's response, and then performs followup tasks depending on the
  // message's namespace.
  var handleMessage = function ( message ) {
    var data = JSON.parse( message.data );

    switch ( data.namespace ) {

      // A FreeNAS event has occurred
      case "events":

        // TODO: Send event to action creator

        break;

      // An RPC call is returning a response
      case "rpc":
        if ( data.name === "response" ) {
          resolvePendingRequest( data.id, data.args, "success" );
        } else {
          console.warn( "Was sent an rpc message from middleware, but it did not contain a response:" );
          console.log( message );
        }
        break;

      // There was an error with a request or with its execution on FreeNAS
      case "error":
        console.error( "Middleware has indicated an error:" );
        console.log( data.args );
        break;

      // A reply was sent from the middleware with no recognizable namespace
      // This shouldn't happen, and probably indicates a problem with the
      // middleware itself.
      default:
        console.warn( "Spurious reply from Middleware:" );
        console.log( message );
        // Do nothing
    }
  };

  // Triggered by the WebSocket's `onerror` event. Handles errors with the client
  // connection to the middleware.
  var handleError = function ( error ) {
    if ( DEBUG ) {
      console.error( "The WebSocket connection to the Middleware encountered an error:" );
      console.log( error );
    }
  };

  // Called by a request function without a matching response. Automatically
  // triggers resolution of the request with a "timeout" status.
  var handleTimeout = function ( requestID ) {

    if ( DEBUG ) { console.error( "Request " + requestID + " timed out without a response from the middleware" ); }

    resolvePendingRequest( requestID, null, "timeout" );
  };

// FLUX STORE HOOKS

  // On a successful login, dequeue any actions which may have been requested
  // either before the connection was made, or before the authentication was
  // complete.
  MiddlewareStore.addChangeListener( dequeueActions );

}

module.exports = new MiddlewareClient();
