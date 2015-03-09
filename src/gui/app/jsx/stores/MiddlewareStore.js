// Middleware Flux Store
// =====================
// Maintain consistent information about the general state of the middleware
// client, including which channels are connected, pending calls, authentication
// status, and blocked operations.

"use strict";

var _            = require("lodash");
var EventEmitter = require("events").EventEmitter;

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes  = FreeNASConstants.ActionTypes;
var CHANGE_EVENT = "change";

var _subscribed    = {};
var _rpcServices   = [];
var _rpcMethods    = {};
var _events        = [];
var _stats         = {};
var _tasks         = {};
var _authenticated = false;


var MiddlewareStore = _.assign( {}, EventEmitter.prototype, {

    emitChange: function( namespace ) {
      this.emit( CHANGE_EVENT, namespace );
    }

  , addChangeListener: function( callback ) {
      this.on( CHANGE_EVENT, callback );
    }

  , removeChangeListener: function( callback ) {
      this.removeListener( CHANGE_EVENT, callback );
    }

  // AUTHENTICAION
  , getAuthStatus: function() {
      return _authenticated;
    }

  // SUBSCRIPTIONS
  , getAllSubscriptions: function() {
      return _subscribed;
    }

  , getNumberOfSubscriptions: function( masks ) {
      return _subscribed[ masks ];
    }

  // RPC
  , getAvailableRPCServices: function() {
      return _rpcServices;
    }

  , getAvailableRPCMethods: function() {
      return _rpcMethods;
    }

  // EVENTS
  , getEventLog: function() {
      return _events;
    }

});

MiddlewareStore.dispatchToken = FreeNASDispatcher.register( function( payload ) {
  var action = payload.action;

  switch( action.type ) {

    // Authentication
    case ActionTypes.UPDATE_AUTH_STATE:
      _authenticated = action.authState;
      MiddlewareStore.emitChange();
      break;


    // Subscriptions
    case ActionTypes.SUBSCRIBE_TO_MASK:
      if ( typeof _subscribed[ action.mask ] === "number" ) {
        _subscribed[ action.mask ]++;
      } else {
        _subscribed[ action.mask ] = 1;
      }

      MiddlewareStore.emitChange("subsctiptions");
      break;

    case ActionTypes.UNSUBSCRIBE_FROM_MASK:
      if ( typeof _subscribed[ action.mask ] === "number" ) {
        if ( _subscribed[ action.mask ] === 1 ) {
          delete _subscribed[ action.mask ];
        } else {
          _subscribed[ action.mask ]--;
        }
      } else {
        console.warn( "Tried to unsubscribe from '" + action.mask + "', but Flux store shows no active subsctiptions.");
      }

      MiddlewareStore.emitChange("subsctiptions");
      break;


    case ActionTypes.MIDDLEWARE_EVENT:

      // Prepend latest event to the front of the array
      _events.unshift( action.eventData );

      MiddlewareStore.emitChange("events");
      break;

    case ActionTypes.LOG_MIDDLEWARE_TASK_QUEUE:

      // TODO: handle task queue

      MiddlewareStore.emitChange();
      break;

    case ActionTypes.RECIEVE_RPC_SERVICES:
      _rpcServices = action.services;

      MiddlewareStore.emitChange("services");
      break;

    case ActionTypes.RECIEVE_RPC_SERVICE_METHODS:
      _rpcMethods[ action.service ] = action.methods;

      MiddlewareStore.emitChange("methods");
      break;



    default:
      // No action
  }
});

module.exports = MiddlewareStore;
