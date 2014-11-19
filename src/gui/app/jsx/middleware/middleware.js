// Middleware Connection
// ---------------------
// Establishes a websocket connection to the FreeNAS server, providing a
// consistent UUID for the session.

"use strict";

var _ = require("lodash");

// Middleware object inherits event system from EventEmitter
var EventEmitter = require("wolfy87-eventemitter");

// Generate a unique UUID used to identify the client connection
function uuid() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace( /[xy]/g, function (c) {
      var r = Math.random() * 16 | 0;
      var v = ( c === "x" ) ? r : ( r & 0x3 | 0x8 );

      return v.toString(16);
    }
  );
}

function Middleware() {
  this.socket       = null;
  this.rpcTimeout   = 10000;
  this.pendingCalls = {};

  // Connect to FreeNAS middleware
  this.connect = function( url ) {
    var self = this;
    this.socket = new WebSocket(url);
    this.socket.onmessage = function(msg) {
      console.log("Message from server: ");
      console.log(msg);
      self.onMessage(msg.data);
    };
    this.socket.onopen    = function() {
      self.emitEvent("connected");
    };
  };

  // Create a correctly formatted JSON object to send to the middleware
  this.pack = function( namespace, name, args, id ) {
    return JSON.stringify({
        "namespace" : namespace
      , "id"        : id || uuid()
      , "name"      : name
      , "args"      : args
    });
  };

  // Authenticate a connection to the middleware
  this.login = function( username, password ) {
    var self = this;
    var id   = uuid();

    var payload = {
        "username" : username
      , "password" : password
    };

    console.log(this.pendingCalls[id]);

    this.pendingCalls[id] = {
        "callback": function() {
          console.log("emitting event");
          this.emitEvent("login");
        }
      , "timeout": setTimeout(function() {
          self.onRPCTimeout(id);
        }
      , this.rpcTimeout )
    };

    console.log("login");
    console.log(this.pendingCalls[id]);

    this.socket.send( this.pack( "rpc", "auth", payload, id ) );
  };

  // Subscribe to events based on a mask
  this.subscribe = function( eventMasks ) {
    this.socket.send( this.pack( "events", "subscribe", eventMasks ) );
  };

  // Unsubscribe to events based on a mask
  this.unsubscribe = function( eventMasks ) {
    this.socket.send( this.pack( "events", "unsubscribe", eventMasks ) );
  };


  this.call = function( method, args, callback ) {
      var self = this;
      var id = uuid();
      var payload = {
          "method": method,
          "args": args,
      };

      this.pendingCalls[id] = {
          "method": method,
          "args": args,
          "callback": callback,
          "timeout": setTimeout(function() {
              self.onRPCTimeout(id);
          }, this.rpcTimeout)
      };

      this.socket.send( this.pack( "rpc", "call", payload, id ) );
  };

  this.onRPCTimeout = function( data ) {
    // TODO: Implement RPC Timeout
  };

  this.onMessage = function( msg ) {
    console.log("onMessage");
    var data = JSON.parse( msg );
    var call;

    if ( data.namespace === "events" && data.name === "event" ) {
      this.emitEvent( "event", data.args );
    }

    if ( data.namespace === "rpc" ) {
      if ( data.name === "response" ) {
        if ( data.id in this.pendingCalls ) {
          call = this.pendingCalls[ data.id ];
          call.callback( data.args );
          clearTimeout( call.timeout );
          delete this.pendingCalls[ data.id ];
        } else {
          /* Spurious reply, just ignore it */
          return;
        }
      }

      if (data.name === "error") {
        this.emitEvent("error", data.args);
      }
    }
  };
}

Middleware.prototype = _.create( EventEmitter.prototype );

module.exports = new Middleware();