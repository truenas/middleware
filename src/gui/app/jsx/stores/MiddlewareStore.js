// Middleware Flux Store
// =====================
// Maintain consistent information about the general state of the middleware
// client, including which channels are connected, pending calls, and blocked operations.

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

var CHANGE_EVENT = "change";

var _rpcServices    = [];
var _rpcMethods     = {};
var _events         = [];
var socketConnected = false;
var reconnectETA    = 0;


var MiddlewareStore = _.assign( {}, EventEmitter.prototype, {

    emitChange: function ( namespace ) {
      this.emit( CHANGE_EVENT, namespace );
    }

  , addChangeListener: function ( callback ) {
      this.on( CHANGE_EVENT, callback );
    }

  , removeChangeListener: function ( callback ) {
      this.removeListener( CHANGE_EVENT, callback );
    }

  // RPC
  , getAvailableRPCServices: function () {
      return _rpcServices;
    }

  , getAvailableRPCMethods: function () {
      return _rpcMethods;
    }

  // hook to get socket state and time to reconnect if not connected
  , getSockState: function () {
      return [ socketConnected, reconnectETA ];
    }

  // EVENTS
  , getEventLog: function () {
      return _events;
    }

});

MiddlewareStore.dispatchToken = FreeNASDispatcher.register( function ( payload ) {
  var action = payload.action;

  switch ( action.type ) {

    case ActionTypes.UPDATE_SOCKET_STATE:
      if ( action.sockState === "connected" ) {
        socketConnected = true;
      } else if ( action.sockState === "disconnected" ) {
        socketConnected = false;
      }
      MiddlewareStore.emitChange();
      break;

    case ActionTypes.UPDATE_RECONNECT_TIME:
      reconnectETA = action.ETA;
      MiddlewareStore.emitChange();
      break;

    case ActionTypes.MIDDLEWARE_EVENT:

      // Prepend latest event to the front of the array
      _events.unshift( action.eventData );
      MiddlewareStore.emitChange( "events" );

      break;

    case ActionTypes.LOG_MIDDLEWARE_TASK_QUEUE:

      // TODO: handle task queue

      MiddlewareStore.emitChange();
      break;

    case ActionTypes.RECEIVE_RPC_SERVICES:
      _rpcServices = action.services;

      MiddlewareStore.emitChange( "services" );
      break;

    case ActionTypes.RECEIVE_RPC_SERVICE_METHODS:
      _rpcMethods[ action.service ] = action.methods;

      MiddlewareStore.emitChange( "methods" );
      break;



    default:
    // No action
  }
});

module.exports = MiddlewareStore;
